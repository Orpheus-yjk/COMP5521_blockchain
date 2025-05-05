# -*- coding: utf-8 -*-
"""
区块链命令行客户端，支持P2P网络通信、挖矿、交易等操作
运行方式: python client.py [--port P2P_PORT] [--api-port API_PORT] [--peer PEER_IP:PORT]
"""

import time
import json
import logging
import argparse
import threading
from flask import Flask
from blockchain import Blockchain
from mempool import Mempool
from mining import MiningModule
from network import NetworkInterface

# 默认配置
DEFAULT_P2P_PORT = 5000
DEFAULT_API_PORT = 5001


class BlockchainClient:
    def __init__(self, p2p_port, api_port):
        try:

            # 初始化区块链数据库
            self.blockchain = Blockchain(p2p_port)

            # 询问是否从LevelDB加载数据
            load_from_db = input("是否从LevelDB加载区块链数据？(y/n): ").strip().lower() == 'y'

            if not load_from_db:
                print("清空LevelDB数据库...")
                self._clear_leveldb()

                # 初始化内存池和UTXO数据库
            self.mempool = Mempool(p2p_port=p2p_port)

            # 初始化内存池和UTXO数据库
            self.mempool = Mempool(p2p_port = p2p_port)

            # 初始化矿工模块
            self.miner = MiningModule()

            # 初始化网络接口
            self.network = NetworkInterface(
                self.blockchain,
                self.mempool,
                p2p_port,
                api_port
            )

            # 确保数据库连接正常
            self._verify_db_connections()

            self.p2p_port = p2p_port
            self.api_port = api_port

            self._reset_mongodb()  # 清空并重建MongoDB UTXO数据

            # 清理无效的Redis邻居节点
            self._clean_redis_neighbors()

            # 启动网络服务
            threading.Thread(target=self._start_servers).start()
            time.sleep(1)  # 等待服务启动

        except Exception as e:
            self._cleanup_resources()
            raise RuntimeError(f"初始化失败: {str(e)}")

    def _clear_leveldb(self):
        """清空LevelDB数据库"""
        if self.blockchain.is_db_connected():
            try:
                # 遍历删除所有区块
                for key, _ in self.blockchain.db._db:
                    self.blockchain.db._db.delete(key)
                logging.info("已清空LevelDB数据")
            except Exception as e:
                logging.error(f"清空LevelDB失败: {str(e)}")
                raise

    def _reset_mongodb(self):
        """清空并重建MongoDB UTXO数据"""
        if hasattr(self.mempool.utxo_monitor, 'db'):
            try:
                # 清空现有UTXO数据
                self.mempool.utxo_monitor.db.utxo_collection.delete_many({})

                # 从本地区块链重建UTXO
                for block in self.blockchain.blockchain:
                    self.mempool.update_utxo(block.txs_data)
                logging.info("已重建MongoDB UTXO数据")
            except Exception as e:
                logging.error(f"重置MongoDB失败: {str(e)}")
                raise

    def _clean_redis_neighbors(self):
        """清理无效的Redis邻居节点"""
        if hasattr(self.network, 'redis'):
            try:
                neighbors = self.network.redis.get_hash("neighbors")
                for addr, meta_str in list(neighbors.items()):
                    try:
                        meta = json.loads(meta_str)
                        if meta.get('status') == 'disconnected':
                            self.network.redis.client.hdel("neighbors", addr)
                    except (json.JSONDecodeError, ValueError):
                        self.network.redis.client.hdel("neighbors", addr)
                logging.info("已清理无效Redis邻居节点")
            except Exception as e:
                logging.error(f"清理Redis邻居节点失败: {str(e)}")

    def _verify_db_connections(self):
        """验证所有数据库连接"""
        db_checks = [
            hasattr(self.blockchain, 'db'),
            hasattr(self.mempool, 'redis'),
            hasattr(self.mempool.utxo_monitor, 'db')
        ]

        if not all(db_checks):
            raise RuntimeError("数据库连接未正确初始化")

    def _cleanup_resources(self):
        """清理资源"""
        resources = [
            getattr(self.blockchain, 'db', None),
            getattr(self.mempool, 'redis', None),
            getattr(getattr(self.mempool, 'utxo_monitor', None), 'db', None)
        ]

        for resource in resources:
            if resource is not None:
                try:
                    resource.close()
                except Exception as e:
                    logging.error(f"关闭数据库连接时出错: {str(e)}")

    def _start_servers(self):
        """启动P2P和API服务"""
        self.network.app.run(port=self.p2p_port)
        api_app = Flask(__name__)
        api_app.run(port=self.api_port)

    def add_peer(self, address):
        """添加邻居节点"""
        self.network.add_neighbor(address)
        print(f"已添加邻居节点: {address}")

    def mine_block(self, miner_address):
        """挖矿"""
        try:
            getbkh = self.blockchain.blockchain[-1].block_hash  # 有前面的块
        except:
            getbkh = '0'*64  # 没有前面的块
        self.miner.reset_last_block_hash(getbkh)  # 更改前哈希值
        new_block = self.miner.mine_block(
            mempool=self.mempool,
            blockchain=self.blockchain,
            miner_address=miner_address
        )
        if self.network.validate_and_add_block(new_block):
            self.network.broadcast_block(new_block)
            print(f"成功挖到区块 #{new_block.header.index}")
        else:
            print("挖矿失败，区块验证未通过")

    def sync_per_block(self):
        """手动触发区块同步"""
        max_retry = 3  # 失败最多3次
        while True:
            result = self.network.sync_one_blocks()
            if result == "sync once success": continue
            elif result == "sync already finished": break
            elif result == "sync failed for some reason":
                max_retry -= 1
                if max_retry == 0: break
                time.sleep(1)

    def sync_blocks(self):
        self.network._sync_blocks()

    def print_blockchain_info(self):
        """打印区块链简要信息"""
        print("\n>>> 当前区块链状态:")
        print(f"区块高度: {self.blockchain.height()}")
        try:
            print(f"最新区块哈希: {self.blockchain.blockchain[-1].block_hash[:16]}...")
        except:
            pass
        print(f"邻居节点数: {len(self.network.P2P_neighbor)}\n")

    def print_blockchain_details(self):
        """打印区块链的详细信息"""
        print("\n>>> 当前区块链的详细信息:")
        try:
            _index = 0
            for block in self.blockchain.blockchain:
                _index += 1
                print(f"\033[96m>>> Block: {_index} Block hash: {block.block_hash}\033[0m")  # 输出青色文本
                print(block.serialize())
            print("\n当前区块链的详细信息打印完毕")
        except:
            # 输出红色文本
            print("\n\033[91m当前区块链的详细信息打印失败\033[0m")

    def print_blockchain_LevelDB(self):
        """从LevelDB当中打印区块链的详细信息"""
        print("\n>>> 从LevelDB中查看当前区块链的详细信息:")
        if not self.blockchain.is_db_connected():
            print("LevelDB连接不可用")
            return

        try:
            all_blocks = self.blockchain.db.get_all_blocks()
            if not all_blocks:
                print("LevelDB中没有区块数据")
                return

            _index = 0
            for block_hash, block_data in all_blocks.items():
                _index += 1
                print(f"\033[96m>>> Block: {_index} Block Hash: {block_hash[:16]}...\033[0m")
                print(block_data)
        except Exception as e:
            # 输出红色文本
            print(f"\033[91m从LevelDB获取数据失败: {str(e)}\033[0m")

    def print_mempool_info(self):
        """打印本地mempool的简要信息"""
        print("\n>>> 当前本地mempool状态:")
        try:
            tx_count = len(self.mempool.transactions)
            mempool_size = sum(tx.calculate_raw_size() for tx in self.mempool.transactions.values())
            print(f"交易数量: {tx_count}")
            print(f"内存占用: {mempool_size} bytes")
            print(f"最大容量: {self.mempool.max_size} bytes")
        except Exception as e:
            # 输出红色文本
            print(f"\033[91m获取mempool信息失败: {str(e)}\033[0m")

    def print_mempool_details(self):
        """打印本地mempool的详细信息"""
        print("\n>>> 当前本地mempool的详细信息:")
        try:
            for txid, tx in self.mempool.transactions.items():
                print(f"\033[96m>>> Transaction ID: {txid[:16]}...\033[0m")
                print(tx.serialize())
        except Exception as e:
            # 输出红色文本
            print(f"\033[91m获取mempool详细信息失败: {str(e)}\033[0m")

    def print_mempool_Redis(self):
        """打印redis当中mempool的详细信息"""
        print("\n>>> 从redis中查看当前本地mempool的详细信息:")
        if not hasattr(self.mempool, 'redis'):
            print("Redis连接不可用")
            return

        try:
            tx_list = self.mempool.redis.get_list("transactions")
            for tx_data in tx_list:
                tx = json.loads(tx_data)
                print(f"\033[96m>>> Transaction ID: {tx['Txid'][:16]}...\033[0m")
                print(tx)
        except Exception as e:
            # 输出红色文本
            print(f"\033[91m从Redis获取mempool数据失败: {str(e)}\033[0m")

    def print_neighbor(self):
        """打印邻居节点的信息"""
        print("当前p2p邻居列表：")
        for _key, _val in self.network.P2P_neighbor.items():
            print(f"\033[96m>>> 邻居节点: {_key}\033[0m")
            print(_val)
        print("p2p邻居打印完毕")

    def print_neighbor_Redis(self):
        """从redis当中打印邻居节点的信息"""
        print("\n>>> 从redis中查看当前邻居节点的信息:")
        if not hasattr(self.network, 'redis'):
            print("Redis连接不可用")
            return

        try:
            neighbors = self.network.redis.get_hash("neighbors")
            for addr, meta in neighbors.items():
                print(f"\033[96m>>> 邻居节点: {addr}\033[0m")
                print(meta)
        except Exception as e:
            # 输出红色文本
            print(f"\033[91m从Redis获取邻居节点信息失败: {str(e)}\033[0m")

    def print_wallet(self):
        """查看utxo并打印所有地址的余额"""
        print("\n>>> 当前所有地址的余额:")
        try:
            # 获取所有地址
            addresses = set()
            for tx in self.mempool.utxo_monitor.utxos.values():
                for vout in tx.values():
                    addresses.add(vout[1])

            # 打印每个地址的余额
            for addr in addresses:
                balance = self.mempool.utxo_monitor.get_balance(addr)
                print(f"地址 {addr}: {balance} satoshis")
        except Exception as e:
            # 输出红色文本
            print(f"\033[91m获取钱包余额失败: {str(e)}\033[0m")

    def print_utxo_MongoDB(self):
        """从MongoDB当中打印utxo"""
        print("\n>>> 从MongoDB中查看当前所有地址的余额:")
        if not hasattr(self.mempool.utxo_monitor, 'db'):
            print("MongoDB连接不可用")
            return

        try:
            utxos = self.mempool.utxo_monitor.db.get_utxos_by_address("*")
            for utxo in utxos:
                print(f"\033[96m>>> UTXO: {utxo['txid'][:8]}...:{utxo['vout_index']}\033[0m")
                print(f"金额: {utxo['amount']}")
                print(f"地址: {utxo['address']}")
                print(f"状态: {'已花费' if utxo['spent'] else '未花费'}")
        except Exception as e:
            # 输出红色文本
            print(f"\033[91m从MongoDB获取UTXO数据失败: {str(e)}\033[0m")

    def __del__(self):
        """清理资源"""
        if hasattr(self.blockchain, 'db'):
            self.blockchain.db.close()
        if hasattr(self.mempool, 'redis'):
            self.mempool.redis.close()
        if hasattr(self.mempool.utxo_monitor, 'db'):
            self.mempool.utxo_monitor.db.close()

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='区块链客户端')
    parser.add_argument('--port', type=int, default=DEFAULT_P2P_PORT, help='P2P端口')
    parser.add_argument('--api-port', type=int, default=DEFAULT_API_PORT, help='API端口')
    parser.add_argument('--peer', help='初始邻居节点地址 (IP:PORT)')
    args = parser.parse_args()

    # 初始化客户端
    client = BlockchainClient(args.port, args.api_port)

    # 添加初始邻居节点
    if args.peer:
        client.add_peer(args.peer)

    # 命令行交互
    while True:
        cmd = input("\n请输入命令 (view/addpeer/mine/continuous_mine_20/continuous_mine_100/sync/exit/standby) >>>\n").strip().lower()
        if cmd == "view":
            order = input("请选择查看的信息 (help/blockchain_info/blockchain_details/blockchain_LevelDB/mempool_info/mempool_details/mempool_Redis/neighbor/neighbor_Redis/wallet/utxo_MongoDB) >>>\n")
            if order == "help":
                print(">>> 命令提示")
                print(">>> blockchain_info : 打印区块链简要信息")
                print(">>> blockchain_details : 打印区块链的详细信息")
                print(">>> blockchain_LevelDB : 从LevelDB当中打印区块链的详细信息")
                print(">>> mempool_info : 打印本地mempool的简要信息")
                print(">>> mempool_details : 打印本地mempool的详细信息")
                print(">>> mempool_Redis : 打印redis当中mempool的详细信息")
                print(">>> neighbor : 打印邻居节点的地址信息")
                print(">>> neighbor_Redis : 打印redis当中mempool的详细信息")
                print(">>> wallet : 查看utxo并打印所有地址的余额")
                print(">>> utxo_MongoDB : 从MongoDB当中打印utxo")
                print()

            elif order == "print_blockchain_info":
                client.print_blockchain_info()

            elif order == "blockchain_details":
                client.print_blockchain_details()

            elif order == "blockchain_LevelDB":
                client.print_blockchain_LevelDB()

            elif order == "mempool_info":
                client.print_mempool_info()

            elif order == "mempool_details":
                client.print_mempool_details()

            elif order == "mempool_Redis":
                client.print_mempool_Redis()

            elif order == "neighbor":
                client.print_neighbor()

            elif order == "neighbor_Redis":
                client.print_neighbor_Redis()

            elif order == "wallet":
                client.print_wallet()

            elif order == "utxo_MongoDB":
                client.print_utxo_MongoDB()

            else:
                print("无效命令")

        elif cmd == 'mine':
            address = input("请输入矿工地址 >>>\n")
            client.mine_block(address)
            client.print_blockchain_info()

        elif cmd == "continuous_mine_20":
            address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"  # 任意地址
            for i in range(20):
                client.mine_block(address)
                client.print_blockchain_info()
                time.sleep(20)
        elif cmd == "continuous_mine_100":
            address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"  # 任意地址
            for i in range(100):
                client.mine_block(address)
                client.print_blockchain_info()
                time.sleep(10)

        elif cmd == 'addpeer':
            peer = input("请输入邻居节点地址 (IP:PORT) >>>\n")
            client.add_peer(peer)

        elif cmd == 'sync':
            print("已触发区块同步")
            client.sync_blocks()
            client.print_blockchain_info()

        elif cmd == 'exit':
            print("退出系统")
            break

        elif cmd == "standby":
            while True:
                print("Standby node...")
                time.sleep(3600)
                pass  # 进入standby模式，只显示输出不操作

        else:
            print("无效命令，可用命令: view/addpeer/mine/continuous_mine_20/continuous_mine_100/sync/exit/standby")

if __name__ == "__main__":
    main()
