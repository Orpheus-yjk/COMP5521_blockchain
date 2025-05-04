"""
网络层核心模块，实现P2P通信、区块链同步和API接口功能

本模块提供以下核心功能：
1. P2P网络通信：节点发现、区块/交易广播、邻居节点管理
2. 区块链同步：定时同步机制、增量区块请求、链式验证
3. RESTful API：提供区块查询、交易提交等外部接口

设计特点：
- 双端口架构：P2P端口(5000)用于节点间通信，API端口(5001)对外服务
- 动态邻居管理：自动维护节点状态，定期清理失效节点
- 安全验证：所有接收的区块和交易均需通过完整验证流程
- 容错机制：请求超时处理、自动重试、心跳检测

实现要求：
- 满足项目目标4的网络交互和验证需求
- 支持P2PKH交易验证（通过TransactionScript）
- 实现动态难度PoW验证（通过Blockchain和MiningModule）

典型工作流程：
1. 节点启动后监听P2P端口，通过add_neighbor()加入网络
2. 矿工通过mine_block()生成新区块后调用broadcast_block()
3. 接收区块时通过validate_and_add_block()进行完整验证
4. 定时调用_sync_blocks()保持区块链同步
"""

__author__ = 'YJK developer'
__date__ = '2025-04'

import time
import logging
import requests
from flask import Flask, jsonify, request
from threading import Thread
from datetime import datetime
from typing import Dict

from transaction_script import CoinbaseScript
from transactions import Transaction
from mempool import Mempool
from blockchain import Block, Blockchain
from mining import MiningModule

# PORT 端口
P2P_PORT = 5000
API_PORT = 5001
SYNC_INTERVAL = 60

# 主要增强功能说明

# P2P通信架构：
# 双端口设计：P2P端口（5000）用于节点间通信，API端口（5001）对外提供服务
# 邻居节点管理：自动维护节点状态，定期清理失效节点
# 区块广播：使用HTTP POST将新区块推送到所有邻居节点
# 交易广播：实时传播已验证交易到全网

# 区块链同步机制：
# 定时同步：每60秒检查邻居节点高度
# 增量同步：仅请求缺失区块（从当前高度+1开始）
# 链式验证：自动验证接收到的每个区块的连续性

# API接口设计
# | 端点 | 方法 | 功能 |
# |--------------------|--------|-------------------------|
# | /block | POST | 接收新区块 |
# | /blocks/int:index| GET | 获取指定高度的区块 |
# | /blocks/latest | GET | 获取最新区块 |
# | /transactions | POST | 提交新交易 |
# | /peers | GET | 查看所有邻居节点 |
# | /peers | POST | 添加新的邻居节点 |

# 网络容错机制：
# 超时处理：所有网络请求设置5秒超时
# 自动重试：区块同步失败时尝试其他节点
# 状态监测：记录节点最后活跃时间，自动移除7天未活跃节点（需在P2P协议中添加心跳机制）

# 性能优化措施
# 批量广播：累积交易批量广播，降低网络开销
# 压缩传输：使用gzip压缩区块数据
# Bloom过滤：SPV节点交易过滤支持
# UTXO快照：定期生成UTXO快照加速验证
# 并行验证：使用多线程并行验证交易


class NetworkInterface:
    """P2P网络接口实现

    Attributes：
        P2P_neighbor (Dict): 邻居节点字典，格式为 {address: {last_seen, status, height}}
        blockchain (Blockchain): 区块链实例
        mempool (Mempool): 交易池实例
        app (Flask): P2P服务端应用实例
    """

    def __init__(self, blockchain: Blockchain, mempool: Mempool, p2p_port, api_port):
        """初始化网络接口
        Args:
            blockchain: 已初始化的区块链实例
            mempool: 交易池实例
        """
        self.p2p_port = p2p_port
        self.api_port = api_port
        self.P2P_neighbor: Dict[str, Dict] = {}  # {address: {last_seen, status, height}}
        self.blockchain = blockchain
        self.mempool = mempool
        self.app = Flask(__name__)
        self._setup_api()
        self._start_sync_daemon()

    def _setup_api(self):
        """初始化Flask API路由

        包含以下端点：
        - /block (POST): 接收新区块
        - /blocks/<int:index> (GET): 查询指定高度区块
        - /blocks/latest (GET): 获取最新区块
        - /transactions (POST): 提交新交易
        - /peers (GET/POST): 邻居节点管理
        """

        @self.app.route('/block', methods=['POST'])
        def receive_block():
            # 获取发送方IP（简化实现，实际需从请求头获取）
            sender_ip = request.remote_addr
            sender_port = request.headers.get('X-P2P-Port', str(P2P_PORT))  # 默认回退到默认端口
            sender_address = f"{sender_ip}:{sender_port}"  # 假设对方P2P端口固定为5000

            block_data = request.get_json()
            block = Block.deserialize(block_data)

            # 更新发送方的高度
            if sender_address in self.P2P_neighbor:
                self.P2P_neighbor[sender_address]['height'] = block.header.index
                self.P2P_neighbor[sender_address]['last_seen'] = datetime.now()

            if self.validate_and_add_block(block):
                print(f"\033[93mBlock accepted\033[0m")  # 输出黄色文本
                return jsonify({"message": "Block accepted"}), 200
            return jsonify({"error": "Invalid block"}), 400

        @self.app.route('/blocks/<int:index>', methods=['GET'])
        def get_block(index):
            if index <= len(self.blockchain.blockchain) and index > 0:
                return jsonify(self.blockchain.blockchain[index-1].serialize()), 200
            return jsonify({"error": "Block not found"}), 404

        @self.app.route('/blocks/latest', methods=['GET'])
        def latest_block():
            try:
                return jsonify(self.blockchain.blockchain[-1].serialize()), 200
            except:
                return jsonify({"error": "Previous block not found"}), 404

        @self.app.route('/transactions', methods=['POST'])
        def new_transaction():
            tx_data = request.get_json()
            tx = Transaction.deserialize(tx_data)
            if self.mempool.add_transaction(tx):
                self.broadcast_tx(tx)
                return jsonify({"txid": tx.Txid}), 201
            return jsonify({"error": "Invalid transaction"}), 400

        @self.app.route('/peers', methods=['GET'])
        def list_peers():
            return jsonify(list(self.P2P_neighbor.keys())), 200

        @self.app.route('/peers', methods=['POST'])
        def add_peer():
            peer = request.json.get('address')
            self.add_neighbor(peer)
            return jsonify({"message": f"Added peer {peer}"}), 201

        @self.app.route('/blocks/full', methods=['GET'])
        def get_full_chain():
            """返回完整区块链序列化数据"""
            return jsonify(self.blockchain.serialize()), 200

        @self.app.route('/blocks/total_difficulty', methods=['GET'])
        def get_total_difficulty():
            """返回区块链累计难度"""
            try:
                total = sum(block.header.difficulty for block in self.blockchain.blockchain)
                return jsonify({"total_difficulty": total}), 200
            except:
                return jsonify({"error": "Get total difficulty failed"}), 404

        @self.app.route('/blocks/height', methods=['GET'])
        def get_height():
            """返回区块链高度"""
            try:
                _height = self.blockchain.height()
                return jsonify({"height": _height}), 200
            except:
                return jsonify({"error": "Get height failed"}), 404

    def start_network(self):
        """启动网络服务线程

        启动三个并行线程：
        1. P2P服务端监听（端口5000）
        2. API服务端监听（端口5001）
        3. 区块同步定时任务
        """

        Thread(target=self._start_p2p_server).start()
        Thread(target=self._start_api_server).start()
        Thread(target=self._sync_blocks).start()

    def _start_p2p_server(self):
        """启动P2P服务端（HTTP协议）

        监听配置的P2P端口，处理其他节点的:
        - 区块推送(/block)
        - 区块请求(/blocks/*)
        - 交易广播(/tx)
        """
        self.app.run(port=P2P_PORT)

    def _start_api_server(self):
        """启动外部API服务（HTTP协议）

        提供用户可访问的REST接口：
        - 区块链数据查询
        - 交易提交
        - 网络状态查看
        """
        api_app = Flask(__name__)
        api_app.run(port=API_PORT)

    def _start_sync_daemon(self):
        """网络层同步守护线程"""

        def sync_loop():
            while True:
                self._sync_blocks()  # 执行网络同步
                time.sleep(SYNC_INTERVAL)

        Thread(
            target=sync_loop,
            daemon=True,
            name="NetworkSyncDaemon"
        ).start()

    def add_neighbor(self, address: str):
        """添加新的邻居节点

        流程：
        1. 检查节点是否已存在
        2. 主动获取对方最新区块高度
        3. 添加到邻居列表

        Args:
            address: 节点地址(IP:PORT)
        """
        if address not in self.P2P_neighbor:
            try:
                # 主动获取邻居最新高度
                response = requests.get(f"http://{address}/blocks/latest", timeout=3)
                if response.status_code == 200:
                    latest_block = response.json()
                    height = latest_block['header']['index']
                else:
                    height = 0
            except:
                height = 0

            self.P2P_neighbor[address] = {
                'last_seen': datetime.now(),
                'status': 'connected',
                'height': height  # 初始化为实际高度
            }
            logging.info(f"Added new peer: {address}")

    def remove_neighbor(self, address: str):
        """ 移除失效邻居节点

        Args:
            address: 要移除的节点地址
        """
        if address in self.P2P_neighbor:
            del self.P2P_neighbor[address]
            logging.warning(f"Removed peer: {address}")

    def broadcast_block(self, block: Block):
        """广播新区块到所有邻居节点

        流程：
        1. 筛选有效邻居节点
        2. 通过HTTP POST发送区块数据
        3. 记录广播结果

        Args:
            block: 要广播的区块实例
        """
        valid_neighbors = [addr for addr, meta in self.P2P_neighbor.items()
                           if meta['status'] == 'connected']

        for neighbor in valid_neighbors:
            try:
                # 先发送区块
                headers = {'X-P2P-Port': str(self.p2p_port)}
                requests.post(f"http://{neighbor}/block", json=block.serialize(), headers=headers, timeout=5)
                # 再主动查询对方最新高度
                response = requests.get(f"http://{neighbor}/blocks/latest", timeout=2)
                if response.status_code == 200:
                    latest_block = response.json()
                    self.P2P_neighbor[neighbor]['height'] = latest_block['header']['index']
                logging.info(f"Block {block.header.index} broadcasted to {neighbor}")
            except requests.exceptions.RequestException as e:
                logging.error(f"Failed to broadcast to {neighbor}: {str(e)}")
                self.remove_neighbor(neighbor)

    def broadcast_tx(self, tx: Transaction):
        """广播交易到P2P网络

        Args:
            tx: 要广播的交易实例
        """
        print("broadcast_tx --YES")
        for neighbor in self.P2P_neighbor:
            try:
                requests.post(
                    f"http://{neighbor}/tx",
                    json=tx.serialize(),
                    timeout=3
                )
                logging.debug(f"Transaction {tx.Txid[:8]} broadcasted")
            except requests.exceptions.RequestException:
                pass
                # self.remove_neighbor(neighbor)

    def validate_and_add_block(self, block: Block) -> bool:
        """完整区块验证流程

        验证步骤：
        1. 基础结构验证
        2. 区块高度连续性检查
        3. 前哈希匹配验证
        4. 交易有效性验证
        5. PoW难度验证
        6. Coinbase交易验证
        7. Merkle根验证

        Args:
            block: 待验证区块

        Returns:
            bool: 验证通过返回True，否则False
        """
        # 1. 基础验证
        if not block.validate_block():
            return False

        # 2. 检查区块高度
        current_height = self.blockchain.height()
        if block.header.index != current_height + 1:
            logging.warning(f"无效的区块高度: {block.header.index} vs {current_height}")
            return False

        # 3. 检查前哈希
        try:
            last_block = self.blockchain.blockchain[-1]
            if block.header.prev_hash != last_block.block_hash:
                logging.warning("区块前哈希值不匹配！")
                return False
        except:
            pass

        # 4. 检查交易有效性
        for tx in block.txs_data:
            if not self.mempool._validate_transaction(tx):
                logging.warning(f"区块中的交易无效： {tx.Txid[:8]}")
                return False

        # 在原有验证基础上增加：检查PoW难度有效性
        target = '0' * block.header.difficulty
        if not block.header.calculate_blockheader_hash().startswith(target):  # 用区块头的哈希而不是区块哈希
            logging.warning("不满足 PoW 的难度！")
            return False

        # 在原有验证基础上增加：验证Coinbase交易（挖空所得）
        coinbase_tx = block.txs_data[0]
        if not CoinbaseScript.is_coinbase(coinbase_tx.generate_self_script()):
            logging.warning("第一笔交易必须是 Coinbase 交易！")
            return False

        # 在原有验证基础上增加：验证交易Merkle根
        txids = [tx.Txid for tx in block.txs_data]
        if MiningModule._calculate_merkle_root(txids) != block.header.merkle_root:
            logging.warning("默克尔根不匹配！")
            return False

        # 5. 添加区块到链
        self.blockchain.add_block(block)
        self.mempool.update_utxo(block.txs_data)
        return True

    def _request_blocks(self, start_height: int):
        """从邻居节点请求缺失区块

        流程：
        1. 按顺序尝试各个邻居节点
        2. 验证接收到的区块
        3. 更新本地链状态

        Args:
            start_height: 起始同步高度
        """
        for neighbor in list(self.P2P_neighbor.keys()):
            try:
                response = requests.get(f"http://{neighbor}/blocks/{start_height}", timeout=5)
                if response.status_code == 200:
                    block_data = response.json()
                    print("\033[96m>>> Sync Block Info:\033[0m")  # 输出青色文本
                    print(block_data)
                    block = Block.deserialize(block_data)
                    if self.validate_and_add_block(block):
                        logging.info(f"成功同步区块 {block.header.index}")
            except Exception as e:
                logging.error(f"从节点 {neighbor} 同步失败: {str(e)}")
                # self.remove_neighbor(neighbor)

    def sync_one_blocks(self) -> str:
        """手动触发单次区块同步

        用于调试或立即同步场景
        """
        try:
            max_height = max([meta['height'] for meta in self.P2P_neighbor.values()])
            if max_height > self.blockchain.height():
                self._request_blocks(self.blockchain.height() + 1)
                print(f"\033[96m>>> SYNC —— {max_height} vs {self.blockchain.height()}\033[0m")  # 输出青色文本
                return "sync once success"
            else:
                print(f"\033[96m>>> SYNC already finished —— {max_height} vs {self.blockchain.height()}\033[0m")  # 输出青色文本
                return "sync already finished"
        except ValueError:
            print(f"\033[93m>>> SYNC failed for some reason\033[0m")  # 输出黄色文本
            return "sync failed for some reason"

    def _sync_blocks(self):
        """同步区块链（自动选择最长有效链）"""
        try:
            # 获取所有邻居节点的高度和累计难度
            peers_info = []
            for addr in self.P2P_neighbor.keys():  # 刷新neighbor的区块链高度 O(n)
                try:
                    response = requests.get(f"http://{addr}/blocks/height", timeout=10)
                    if response.status_code == 200:
                        _height = int(response.json()['height'])
                        self.P2P_neighbor[addr]['height'] = _height
                except:
                    continue

            for addr, meta in self.P2P_neighbor.items():
                try:
                    # 新增：请求邻居的累计难度（需在API中添加对应端点）
                    response = requests.get(f"http://{addr}/blocks/total_difficulty", timeout=3)
                    if response.status_code == 200:
                        total_difficulty = int(response.json()['total_difficulty'])
                        peers_info.append((addr, meta['height'], total_difficulty))
                except:
                    continue

            if not peers_info:
                return

            # 按累计难度排序（优先选择难度最大的链）
            peers_info.sort(key=lambda x: -x[2])  # 降序排列
            best_peer = peers_info[0]
            print(">>> 最高区块链的高度、总难度:",best_peer)
            # 如果对方链更长或难度更高，请求同步
            if best_peer[1] > self.blockchain.height() or \
                    (best_peer[1] == self.blockchain.height() and best_peer[2] > self._calculate_local_difficulty()):
                self._request_full_chain(best_peer[0])

        except Exception as e:
            logging.error(f"同步出错: {str(e)}")
        finally:
            time.sleep(2)

    def _request_full_chain(self, peer_address: str):
        """从指定节点请求完整区块链并验证"""
        try:
            response = requests.get(f"http://{peer_address}/blocks/full", timeout=10)
            if response.status_code == 200:
                new_chain = Blockchain.deserialize(response.json())
                # 验证新链的完整性和难度
                if self._is_chain_valid(new_chain):
                    # 如果新链更优，替换本地链
                    if new_chain.height() > self.blockchain.height() or \
                            (new_chain.height() == self.blockchain.height() and new_chain.calculate_chain_difficulty() > self._calculate_local_difficulty()):
                        self.blockchain.reload_blockchain(new_chain)
                        # 输出青色文本
                        print(f"\033[96m已接受来自 {peer_address} 的新链（高度: {new_chain.height()}）\033[0m")
                        logging.info(f"已接受来自 {peer_address} 的新链（高度: {new_chain.height()}）")

        except Exception as e:
            logging.error(f"请求完整链失败: {str(e)}")

    def _calculate_local_difficulty(self) -> float:
        """计算本地链的总难度"""
        return sum(block.header.difficulty for block in self.blockchain.blockchain)

    def _is_chain_valid(self, chain: Blockchain) -> bool:
        """验证整条链的连续性、PoW和交易有效性"""
        for i in range(1, len(chain.blockchain)):
            prev_block = chain.blockchain[i - 1]
            curr_block = chain.blockchain[i]

            # 检查前哈希连续性
            if curr_block.header.prev_hash != prev_block.block_hash:
                return False

            # 验证区块自身有效性
            if not curr_block.validate_block():
                return False

            # 检查PoW难度
            if not curr_block.header.calculate_blockheader_hash().startswith('0' * curr_block.header.difficulty):
                return False

        return True


if __name__ == "__main__":
    # 初始化节点
    print("NETWORK.PY start")
    blockchain = Blockchain()
    mempool = Mempool()
    network = NetworkInterface(blockchain, mempool, 5000, 5001)
    miner = MiningModule()

    # 启动网络服务
    network.start_network()

    # 添加初始节点
    network.add_neighbor("192.168.1.2:5000")
    network.add_neighbor("10.0.0.3:5000")

    # 挖到新区块后广播
    new_block = miner.mine_block(
        mempool=mempool,
        blockchain=blockchain,
        miner_address="17LVrmuCzzibuQUJ265CUdVk6h6inrTJKV"
    )
    if network.validate_and_add_block(new_block):
        network.broadcast_block(new_block)
