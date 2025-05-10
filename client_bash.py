# -*- coding: utf-8 -*-
"""
区块链命令行客户端，支持P2P网络通信、挖矿、交易等操作
运行方式: python client.py [--port P2P_PORT] [--api-port API_PORT] [--peer PEER_IP:PORT]
"""

__author__ = 'YJK developer'
__date__ = '2025-04'

import time
import json
import logging
import argparse
from blockchain import Blockchain
from mempool import Mempool
from mining import MiningModule
from network import NetworkInterface

# 默认配置
DEFAULT_P2P_PORT = 5000
DEFAULT_API_PORT = 5001

GENESIS_BLOCK_HASH = '0'*64
MINING_REWARD = 500000000


class BlockchainClient:
    """区块链命令行bash界面管理器"""

    def __init__(self, p2p_port: int, api_port: int):
        try:
            self.p2p_port = p2p_port
            self.api_port = api_port

            # 初始化矿工模块
            self.miner = MiningModule()

            # 初始化网络接口，启动网络服务进程，清理邻居。同步区块链和内存池数据到网络端（后续也需要定期同步）
            self.network = NetworkInterface(
                p2p_port = p2p_port,
                api_port = api_port,
                blockchain = Blockchain(p2p_port=p2p_port),  # 初始化区块链
                mempool = Mempool(p2p_port = p2p_port)  # 初始化内存池， 连接Redis数据库和UTXO MongoDB数据库
            )

            self.network.verify_db_connections()
            self.network.reset_mongodb()
            # 询问blockchain是否从LevelDB加载数据
            if_load_from_db = input("是否从LevelDB加载区块链数据？(y/n): ").strip().lower() == 'y'
            if not if_load_from_db:
                print("清空LevelDB数据库...")
                self.network.clear_leveldb()
            else:
                self.network.blockchain.load_chaindata_from_db()  # 这里blockchain要从LevelDB中重载数据
            if_clear_neighbor = input("是否清空redis数据库中余留的本节点邻居数据？(y/n): ").strip().lower() == 'y'
            if if_clear_neighbor:
                print("清空redis数据库中余留的本节点邻居数据...")
                self.network.P2P_neighbor = {}
                self.network.redis.del_all_hash("neighbors")

        except Exception as e:
            self.network.cleanup_resources()
            raise RuntimeError(f"初始化client失败: {str(e)}")

    def add_peer(self, address):
        """添加邻居节点"""
        self.network.add_neighbor(address)
        print(f"已添加邻居节点: {address}")

    def mine_block(self, miner_address):
        """挖矿"""
        try:
            getbkh = self.network.blockchain.blockchain[-1].block_hash  # 有前面的块
        except:
            getbkh = '0'*64  # 没有前面的块
        self.miner.update_chain_lasthash(getbkh)  # 更改前哈希值
        self.miner.update_chain_height(self.network.blockchain.height())  # 更改链长度
        self.miner.update_mempool(self.network.mempool)  # 更改内存池
        new_block, new_difficulty = self.miner.mine_block(miner_address=miner_address)
        if self.network.validate_and_add_one_block(new_block):
            self.network.broadcast_block(new_block)
            self.network.redis.save_var("difficulty", int(new_difficulty))  # 更新本地Redis难度
            print(f"成功挖到区块 #{new_block.header.index}")
        else:
            print("挖矿失败，区块验证未通过")

    def sync_blocks(self):
        self.network._sync_blockchain()

    def print_blockchain_info(self):
        """打印区块链简要信息"""
        print("\n>>> 当前区块链状态:")
        print(f"区块高度: {self.network.blockchain.height()}")
        try:
            print(f"最新区块哈希: {self.network.blockchain.blockchain[-1].block_hash[:16]}...")
        except:
            pass
        print(f"邻居节点数: {len(self.network.P2P_neighbor)}\n")

    def print_blockchain_details(self):
        """打印区块链的详细信息"""
        print("\n>>> 当前区块链的详细信息:")
        try:
            _index = 0
            for block in self.network.blockchain.blockchain:
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
        if not self.network.blockchain.is_db_connected():
            print("LevelDB连接不可用")
            return

        try:
            all_blocks = self.network.blockchain.db.get_all_blocks()
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
            tx_count = len(self.network.mempool.transactions)
            mempool_size = sum(tx.calculate_raw_size() for tx in self.network.mempool.transactions.values())
            print(f"交易数量: {tx_count}")
            print(f"内存占用: {mempool_size} bytes")
            print(f"最大容量: {self.network.mempool.max_size} bytes")
        except Exception as e:
            # 输出红色文本
            print(f"\033[91m获取mempool信息失败: {str(e)}\033[0m")

    def print_mempool_details(self):
        """打印本地mempool的详细信息"""
        print("\n>>> 当前本地mempool的详细信息:")
        try:
            for txid, tx in self.network.mempool.transactions.items():
                print(f"\033[96m>>> Transaction ID: {txid[:16]}...\033[0m")
                print(tx.serialize())
        except Exception as e:
            # 输出红色文本
            print(f"\033[91m获取mempool详细信息失败: {str(e)}\033[0m")

    def print_mempool_Redis(self):
        """打印redis当中mempool的详细信息"""
        print("\n>>> 从redis中查看当前本地mempool的详细信息:")
        if not hasattr(self.network.mempool, 'redis'):
            print("Redis连接不可用")
            return

        try:
            tx_list = self.network.mempool.redis.get_list("transactions")
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
            for tx in self.network.mempool.utxo_monitor.utxos.values():
                for vout in tx.values():
                    addresses.add(vout[1])

            # 打印每个地址的余额
            for addr in addresses:
                balance = self.network.mempool.utxo_monitor.get_balance(addr)
                print(f"地址 {addr}: {balance} YJK_satoshis")
        except Exception as e:
            # 输出红色文本
            print(f"\033[91m获取钱包余额失败: {str(e)}\033[0m")

    def print_utxo_MongoDB(self):
        """从MongoDB当中打印utxo"""
        print("\n>>> 从MongoDB中查看当前所有地址的余额:")
        if not hasattr(self.network.mempool.utxo_monitor, 'db'):
            print("MongoDB连接不可用")
            return

        try:
            utxos = self.network.mempool.utxo_monitor.db.get_utxos_by_address("*")
            for utxo in utxos:
                print(f"\033[96m>>> UTXO: {utxo['txid'][:8]}...:{utxo['vout_index']}\033[0m")
                print(f"金额: {utxo['amount']}")
                print(f"地址: {utxo['address']}")
                print(f"状态: {'已花费' if utxo['spent'] else '未花费'}")
        except Exception as e:
            # 输出红色文本
            print(f"\033[91m从MongoDB获取UTXO数据失败: {str(e)}\033[0m")

    def call_wallet(self, privkey_hex):
        """钱包功能"""
        privkey = bytes.fromhex(privkey_hex)
        # 生成地址
        from math_util import GenerateKeysUtils
        pubkey = GenerateKeysUtils.private_key_to_public_key(privkey)
        address = GenerateKeysUtils.public_key_to_public_address(pubkey)
        print(f"私钥登录地址: {address}")
        # 查询余额
        balance = self.network.mempool.utxo_monitor.get_balance(address)
        print(f"当前余额: {balance} YJK_satoshis")

    def call_transfer(self, privkey_hex, recipient, amount, fee_rate):
        """端到端转账"""
        from math_util import GenerateKeysUtils
        privkey = bytes.fromhex(privkey_hex)
        pubkey = GenerateKeysUtils.private_key_to_public_key(privkey)
        address = GenerateKeysUtils.public_key_to_public_address(pubkey)  # 发送方的公钥哈希（即地址）

        # 1. 选择UTXO
        utxos = []  # 格式: [(txid, vout_idx, amount)]
        total = 0
        for txid, outputs in self.network.mempool.utxo_monitor.utxos.items():
            for vout_idx, (amt, addr) in outputs.items():
                if addr == address and not self.network.mempool.utxo_monitor.is_spent(txid, vout_idx):
                    utxos.append((txid, vout_idx, amt))
                    total += amt
                    if total >= amount:
                        break
            if total >= amount:
                break

        if total < amount:
            print("UTXO不足")
            return

        # 2. 构造交易输入和输出
        from transactions import txInput, txOutput, Transaction
        inputs = []
        for txid, vout_idx, amt in utxos:
            # 获取UTXO对应的交易输出
            utxo_tx = self.network.mempool.utxo_monitor.utxos[txid][vout_idx]

            # 构造锁定脚本 (P2PKH格式)
            locking_script = f"OP_DUP OP_HASH160 {address} OP_EQUALVERIFY OP_CHECKSIG"

            # 构造交易数据
            tx_data = {
                "version": 1,
                "locktime": 0,
                "vins": [{
                    "txid": txid,
                    "referid": vout_idx,
                    "scriptSig": "",  # 签名时填充
                    "sequence": 0xFFFFFFFF
                }],
                "vouts": [{
                    "value": amount,
                    "script_pubkey_hash": recipient
                }]
            }

            # 如果总输入大于转账金额，需要找零
            if total > amount:
                tx_data["vouts"].append({
                    "value": total - amount,
                    "script_pubkey_hash": address
                })

            # 签名交易
            tx_input, tx_output, signature = Transaction.payer_sign(
                private_key=privkey,
                receiver_address=recipient,
                Tx_data=tx_data,
                txid=txid,
                referid=vout_idx
            )

            inputs.append(txInput(
                txid=txid,
                referid=vout_idx,
                pubkey=pubkey,
                signature=signature.hex()
            ))

        # 3. 构造交易输出
        outputs = [
            txOutput(amount, recipient)
        ]
        # 添加找零输出（如果有）
        if total > amount:
            outputs.append(txOutput(total - amount - fee_rate, address))

        # 4. 创建交易
        tx = Transaction.create_normal_tx(inputs, outputs, nlockTime=0)
        tx.fee = fee_rate  # 设置手续费

        # 5. 添加到内存池并广播
        if self.network.mempool.add_transaction(tx):
            self.network.broadcast_tx(tx)
            print(f"转账成功，交易ID: {tx.Txid}")
            print(f"发送方: {address}")
            print(f"接收方: {recipient}")
            print(f"金额: {amount} YJK_satoshis")
            print(f"手续费: {fee_rate} YJK_satoshis")
            if total > amount:
                print(f"找零: {total - amount - fee_rate} YJK_satoshis")
        else:
            print("交易无效或添加失败")


    def __del__(self):
        """清理资源"""
        self.network.cleanup_resources()

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
        cmd = input("\n\033[37;44m请输入命令 (view/addpeer/mine/continuous_mine/transfer/sync/exit/standby) >>>\033[0m\n").strip().lower()  # 白字蓝底
        if cmd == "view":
            order = input("请选择查看的信息 (\033[93mhelp/blockchain_info/blockchain_details/blockchain_LevelDB/mempool_info/"
                          "mempool_details/mempool_Redis/neighbor/neighbor_Redis/wallet/utxo_MongoDB\033[0m) >>>\n")  # 输出中间内容黄色文本
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

            elif order == "blockchain_info":
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
            address = input("\033[37;44m请输入矿工地址 >>>\033[0m\n")  # 白字蓝底
            client.mine_block(address)
            client.print_blockchain_info()

        elif cmd == "continuous_mine":
            block_num= int(input("\033[37;44m请输入挖矿个数 >>>\033[0m\n"),0)  # 白字蓝底
            address = "18QJhgS3DkPJGiSaFkNZMoe9Nsq1bv4eHH"  # 任意地址1
            # address = "18n3kQHq2nUf1LkJwpo3ZzK5kQqnY4LGey"  # 任意地址2
            for i in range(block_num):
                client.mine_block(address)
                client.print_blockchain_info()
                time.sleep(3)

        elif cmd == 'addpeer':
            peer = input("\033[37;44m请输入邻居节点地址 (IP:PORT) >>>\033[0m\n")  # 白字蓝底
            client.add_peer(peer)

        elif cmd == "transfer":
            try:
                # 输入私钥
                privkey_hex = input("\033[37;44m请输入私钥（16进制格式）>>>\033[0m\n").strip()  # 白字蓝底
                client.call_wallet(privkey_hex)
                # 输入转账信息
                recipient = input("\033[37;44m请输入收款地址（公钥哈希，16进制格式，1开头）>>>\033[0m\n").strip()
                amount = int(input("\033[37;44m请输入转账金额（satoshi）:\033[0m\n"))
                fee_rate = int(input("\033[37;44m请输入手续费率（YJK_satoshi/字节）>>>\033[0m\n"))
                client.call_transfer(privkey_hex, recipient, amount, fee_rate)
            except Exception as e:
                logging.error(f"\033[93m转账失败。原因：{str(e)}\033[0m")  # 输出黄色文本

        elif cmd == 'sync':
            print("已触发区块同步")
            client.sync_blocks()
            client.print_blockchain_info()

        elif cmd == "standby":
            while True:
                print("Standby node...")
                time.sleep(3600)
                pass  # 进入standby模式，只显示输出不操作

        elif cmd == 'exit':
            print("\033[37;44m退出系统\033[0m")  # 白字蓝底
            break

        else:
            print("\033[93m无效命令，可用命令: view/addpeer/mine/continuous_mine/transfer/sync/exit/standby \033[0m")  # 输出黄色文本

if __name__ == "__main__":
    main()
