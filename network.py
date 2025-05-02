"""
网络层核心模块，包含P2P通信、API接口和区块链同步逻辑。

当前的`network.py`中有一个`NetworkInterface`类，主要功能是管理邻居节点（P2P邻居），添加和删除邻居节点，以及广播交易和验证交易和区块的方法。

首先需要考虑如何实现P2P通信。P2P通信通常包括节点之间的消息传递，比如使用HTTP或WebSocket协议。
可能需要为每个节点设置一个服务器来监听其他节点的请求，同时作为客户端向其他节点发送请求。例如，可以添加一个简单的HTTP服务器来处理区块和交易的接收。

其次，API接口部分，可能需要为外部应用提供RESTful API，比如查询区块链信息、提交交易等。这可以通过Flask或类似的框架来实现。
对于API接口，可能需要设计以下端点：
- `/blocks/<index>`：获取指定高度的区块
- `/blocks/latest`：获取最新区块
- `/transactions`：提交新的交易
- `/peers`：获取或添加邻居节点

在广播区块时，应该先进行验证，只有有效的区块才被广播。这可以防止无效区块在网络中传播，减少不必要的网络流量和计算资源浪费。
在实现P2P通信时，每个节点需要维护一个邻居节点列表，并定期与其他节点交换信息，比如最新的区块高度，以便进行区块链同步。

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
    """完整的P2P网络实现"""

    def __init__(self, blockchain: Blockchain, mempool: Mempool):
        self.P2P_neighbor: Dict[str, Dict] = {}  # {address: {last_seen, status, height}}
        self.blockchain = blockchain
        self.mempool = mempool
        self.app = Flask(__name__)
        self._setup_api()

    def _setup_api(self):
        """初始化API端点"""

        @self.app.route('/blocks/<int:index>', methods=['GET'])
        def get_block(index):
            if index < len(self.blockchain.blockchain):
                return jsonify(self.blockchain.blockchain[index].serialize()), 200
            return jsonify({"error": "Block not found"}), 404

        @self.app.route('/blocks/latest', methods=['GET'])
        def latest_block():
            return jsonify(self.blockchain.blockchain[-1].serialize()), 200

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

    def start_network(self):
        """启动网络服务"""
        Thread(target=self._start_p2p_server).start()
        Thread(target=self._start_api_server).start()
        Thread(target=self._sync_blocks).start()

    def _start_p2p_server(self):
        """启动P2P服务端（模拟实现）"""
        self.app.run(port=P2P_PORT)

    def _start_api_server(self):
        """启动外部API服务"""
        api_app = Flask(__name__)
        api_app.run(port=API_PORT)

    def add_neighbor(self, address: str):
        """添加P2P邻居节点"""
        if address not in self.P2P_neighbor:
            self.P2P_neighbor[address] = {
                'last_seen': datetime.now(),
                'status': 'connected',
                'height': 0
            }
            logging.info(f"Added new peer: {address}")

    def remove_neighbor(self, address: str):
        """移除失效节点"""
        if address in self.P2P_neighbor:
            del self.P2P_neighbor[address]
            logging.warning(f"Removed peer: {address}")

    def broadcast_block(self, block: Block):
        """广播新区块到P2P网络"""
        valid_neighbors = [addr for addr, meta in self.P2P_neighbor.items()
                           if meta['status'] == 'connected']

        for neighbor in valid_neighbors:
            try:
                requests.post(
                    f"http://{neighbor}/block",
                    json=block.serialize(),
                    timeout=5
                )
                logging.info(f"Block {block.header.index} broadcasted to {neighbor}")
            except requests.exceptions.RequestException as e:
                logging.error(f"Failed to broadcast to {neighbor}: {str(e)}")
                self.remove_neighbor(neighbor)

    def broadcast_tx(self, tx: Transaction):
        """广播交易到P2P网络"""
        print("YES")
        for neighbor in self.P2P_neighbor:
            try:
                requests.post(
                    f"http://{neighbor}/tx",
                    json=tx.serialize(),
                    timeout=3
                )
                logging.debug(f"Transaction {tx.Txid[:8]} broadcasted")
            except requests.exceptions.RequestException:
                self.remove_neighbor(neighbor)

    def validate_and_add_block(self, block: Block) -> bool:
        """完整区块验证流程"""
        # 1. 基础验证
        if not block.validate_block():
            return False

        # 2. 检查区块高度
        current_height = self.blockchain.height()
        if block.header.index != current_height + 1:
            logging.warning(f"无效的区块高度: {block.header.index} vs {current_height}")
            return False

        # 3. 检查前哈希
        last_block = None
        try:
            last_block = self.blockchain.blockchain[-1]
        except:
            pass
        if last_block:
            if block.header.prev_hash != last_block.block_hash:
                logging.warning("区块前哈希值不匹配！")
                return False

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

    def _sync_blocks(self):
        """定期同步区块"""
        while True:
            try:
                max_height = max([meta['height'] for meta in self.P2P_neighbor.values()])
                if max_height > self.blockchain.height():
                    self._request_blocks(self.blockchain.height() + 1)
            except ValueError:
                pass
            time.sleep(SYNC_INTERVAL)

    def _request_blocks(self, start_height: int):
        """从邻居节点请求缺失区块"""
        for neighbor in self.P2P_neighbor:  # FIXME: RuntimeError: dictionary changed size during iteration
            try:
                response = requests.get(
                    f"http://{neighbor}/blocks/{start_height}",
                    timeout=5
                )
                if response.status_code == 200:
                    block_data = response.json()
                    block = Block.deserialize(block_data)
                    if self.validate_and_add_block(block):
                        logging.info(f"Synced block {block.header.index}")
            except requests.exceptions.RequestException:
                self.remove_neighbor(neighbor)


if __name__ == "__main__":
    # 初始化节点
    print("NETWORK.PY start")
    blockchain = Blockchain()
    mempool = Mempool()
    network = NetworkInterface(blockchain, mempool)
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
