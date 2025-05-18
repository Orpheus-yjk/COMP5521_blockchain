"""
区块链网络层核心模块 - P2P通信与API服务

本模块实现了区块链节点的核心网络功能，包括P2P通信、区块链同步和RESTful API服务。

=== API 接口文档 ===

P2P 服务端口 (默认:5000):
----------------------------
[区块相关]
POST /block
- 功能: 接收新区块
- 请求体: 区块序列化数据
- 返回: 200成功/400无效数据/500服务器错误

GET /blocks/<int:index>
- 功能: 查询指定高度区块
- 参数: 区块高度
- 返回: 区块序列化数据/404未找到

GET /blocks/latest
- 功能: 获取最新区块
- 返回: 最新区块数据/404未找到

GET /blocks/full
- 功能: 获取完整区块链
- 返回: 整个区块链序列化数据

GET /blocks/height
- 功能: 获取区块链高度
- 返回: {"height": 当前高度}/404错误

GET /blocks/total_difficulty
- 功能: 获取区块链累计难度
- 返回: {"total_difficulty": 总难度}/404错误

[交易相关]
POST /tx
- 功能: 接收新交易
- 请求体: 交易序列化数据
- 返回: 200成功/400无效交易/500服务器错误

[节点管理]
GET /peers
- 功能: 获取邻居节点列表
- 返回: 邻居节点地址列表

POST /peers
- 功能: 添加新邻居节点
- 请求体: {"address": "ip:port"}
- 返回: 201成功/400无效地址

POST /peers/remove
- 功能: 移除邻居节点
- 请求体: {"address": "ip:port"}
- 返回: 200成功/404未找到

API 服务端口 (默认:5001):
----------------------------
(提供与P2P端口相同的接口，供外部用户访问)

=== 核心功能 ===
1. P2P节点通信:
   - 节点发现与邻居管理
   - 区块/交易广播
   - 心跳检测与失效节点清理

2. 区块链同步:
   - 定时同步机制(默认2分钟)
   - 最长链共识
   - 全量/增量同步
   - 并行验证加速

3. 安全机制:
   - 全链路数据验证
   - 防双花检测
   - PoW难度验证
   - 请求超时处理

=== 架构设计 ===
- 双端口服务: P2P端口(节点间通信) + API端口(外部访问)
- 动态邻居管理: 自动维护节点状态
- 数据持久化: 使用Redis存储网络状态
- 容错机制: 自动重试/优雅降级

=== 典型工作流 ===
1. 节点启动 → 监听端口 → 加入网络
2. 接收交易 → 验证 → 广播 → 进入内存池
3. 挖矿成功 → 区块验证 → 全网广播
4. 定时同步 → 链状态维护 → 共识达成
"""

__author__ = 'YJK developer'
__date__ = '2025-04'

import time
import json
import logging
import requests
from flask import Flask, jsonify, request
from threading import Thread
from typing import Dict

from transaction_script import CoinbaseScript
from transactions import Transaction
from mempool import Mempool
from blockchain import Block, Blockchain
from mining import MiningModule
from db_module import RedisModule

__all__ = ['NetworkInterface']

# PORT 端口
P2P_PORT = 5000
API_PORT = 5001
DEFAULT_SYNC_INTERVAL = 120  # 系统默认两分钟同步一次
DEFUALT_RECOVERY_INTERVAL = 60  # 系统默认crush恢复时间等待


class NetworkInterface:
    """P2P网络接口实现

    Attributes：
        P2P_neighbor (Dict): 邻居节点字典，格式为 {address: {last_seen, status, height}}
        blockchain (Blockchain): 区块链实例
        mempool (Mempool): 交易池实例
        app (Flask): P2P服务端应用实例
    """

    def __init__(self, p2p_port: int, api_port: int, blockchain: Blockchain, mempool: Mempool, default_sync_time):
        try:
            self.p2p_port = int(p2p_port)
            self.api_port = int(api_port)
            self._system_default_synchronized_time = default_sync_time if default_sync_time else DEFAULT_SYNC_INTERVAL
            if not (1024 <= self.p2p_port <= 65535) or not (1024 <= self.api_port <= 65535):
                raise ValueError("Port must be between 1024 and 65535")

            self.P2P_neighbor: Dict[str, Dict] = {}
            self.blockchain = blockchain
            self.mempool = mempool
            self.redis = RedisModule(db_name="blockchain_state_port_"+str(p2p_port))  # 区块链状态存储到Redis
            self._load_network_state()

            try:
                self.app = Flask(__name__)
                self._setup_api()
                self._start_sync_daemon()
                self.start_network()  # 新增：自动启动服务
            except Exception as e:
                logging.error(f"Failed to initialize Flask app: {str(e)}")
            time.sleep(1)  # 等待服务启动

        except Exception as e:
            logging.critical(f"NetworkInterface initialization failed: {str(e)}")

    def _load_network_state(self):
        """从Redis加载网络状态"""
        neighbor_data = self.redis.get_hash("neighbors") or {}
        self.P2P_neighbor = {}
        invalid_neighbors = []

        # 反序列化嵌套字典
        for addr, meta_str in neighbor_data.items():
            try:
                # 尝试解析邻居数据
                if not isinstance(meta_str, str):
                    raise ValueError("Invalid metadata format")
                import datetime
                meta = eval(meta_str)
                self.P2P_neighbor[addr] = meta
                try:
                    if self.P2P_neighbor[addr]['status'] == "connected":
                        height_resp = requests.get(
                            f"http://{addr}/blocks/height",  # 获取最新块高并刷新
                            timeout=2
                        )
                        if height_resp.status_code == 200:
                            self.P2P_neighbor[addr]['height'] = height_resp.json().get('height', 0)
                except:
                    self.P2P_neighbor[addr]['status'] = "disconnected"

            except (json.JSONDecodeError, ValueError) as e:
                logging.warning(f"无法解析邻居节点数据: {addr}, 错误: {str(e)}")
                invalid_neighbors.append(addr)

        # 删除无法解析的邻居节点数据
        if invalid_neighbors:
            try:
                self.redis.del_bulk_hash("neighbors", invalid_neighbors)
                logging.warning(f"已从 Redis 中删除无效邻居节点: {invalid_neighbors}")
            except Exception as e:
                logging.error(f"删除无效邻居节点失败: {str(e)}")

        self.difficulty = int(self.redis.get_var("difficulty", 4))

    def _save_network_state(self):
        """保存网络状态到Redis"""
        neighbor_data = {
            addr: str(meta)
            for addr, meta in self.P2P_neighbor.items()
        }
        self.redis.del_all_hash("neighbors")  # 先删再添加
        self.redis.save_hash("neighbors", neighbor_data)
        self.redis.save_var("difficulty", self.difficulty)

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
            """收到网络传递的区块时的处理"""
            try:
                sender_ip = request.remote_addr
                if not sender_ip:
                    raise ValueError("Invalid sender IP")

                sender_port = request.headers.get('X-P2P-Port', str(P2P_PORT))
                if not sender_port.isdigit():
                    sender_port = str(P2P_PORT)

                sender_address = f"{sender_ip}:{sender_port}"

                block_data = request.get_json()
                if not block_data:
                    return jsonify({"error": "Empty block data"}), 400

                block = Block.deserialize(block_data)
                if not block:
                    return jsonify({"error": "Invalid block data"}), 400

                # 更新发送方的高度
                if sender_address in self.P2P_neighbor:
                    from datetime import datetime
                    self.P2P_neighbor[sender_address].update({
                        'height': block.header.index,
                        'last_seen': datetime.now()
                    })

                if self.validate_and_add_one_block(block):
                    logging.info(f"Block #{block.header.index} accepted from {sender_address}")
                    return jsonify({"message": "Block accepted"}), 200

                return jsonify({"error": "Invalid block"}), 400

            except Exception as e:
                logging.error(f"Error in receive_block: {str(e)}", exc_info=True)
                return jsonify({"error": "Internal server error"}), 500

        @self.app.route('/blocks/<int:index>', methods=['GET'])
        def get_block(index):
            """按照indeix查询一个指定高度区块的数据（序列化数据）"""
            if index <= len(self.blockchain.blockchain) and index > 0:
                return jsonify(self.blockchain.blockchain[index-1].serialize()), 200
            return jsonify({"error": "Block not found"}), 404

        @self.app.route('/blocks/latest', methods=['GET'])
        def latest_block():
            """获取最近的一个区块的数据（序列化数据）"""
            try:
                return jsonify(self.blockchain.blockchain[-1].serialize()), 200
            except:
                return jsonify({"error": "Previous block not found"}), 404

        @self.app.route('/tx', methods=['POST'])
        def receive_transaction():
            """接收并验证交易"""
            try:
                tx_data = request.get_json()
                if not tx_data:
                    return jsonify({"error": "Empty transaction data"}), 400

                tx = Transaction.deserialize(tx_data)
                if not tx:
                    return jsonify({"error": "Invalid transaction data"}), 400

                # 验证交易
                if self.mempool.add_transaction(tx):
                    # 更新UTXO
                    self._update_utxo_for_received_tx(tx)
                    logging.info(f"Transaction {tx.Txid[:8]} accepted")
                    return jsonify({"txid": tx.Txid}), 200
                else:
                    return jsonify({"error": "Transaction validation failed"}), 400

            except Exception as e:
                logging.error(f"Error processing transaction: {str(e)}")
                return jsonify({"error": "Internal server error"}), 500

        @self.app.route('/peers', methods=['GET'])
        def list_peers():
            """获取节点列表。后续可做节点发现和共识层"""
            return jsonify(list(self.P2P_neighbor.keys())), 200

        @self.app.route('/peers', methods=['POST'])
        def add_peer():
            """调用对方扩展对方的邻居列表，双向连接时用到"""
            peer = request.json.get('address')
            self.add_neighbor(peer)
            return jsonify({"message": f"Added peer {peer}"}), 201

        @self.app.route('/blocks/full', methods=['GET'])
        def get_full_chain():
            """返回完整的区块链序列化数据"""
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

        @self.app.route('/peers/remove', methods=['POST'])
        def handle_peer_removal():
            """处理其他节点发起的断开请求"""
            peer_address = request.json.get('address')
            if peer_address in self.P2P_neighbor:
                del self.P2P_neighbor[peer_address]
                return jsonify({"status": "removed"}), 200
            return jsonify({"error": "peer not found"}), 404

    def start_network(self):
        """启动网络服务线程

        启动三个并行线程：
        1. P2P服务端监听（端口5000）
        2. API服务端监听（端口5001）
        3. 区块同步定时任务
        """
        Thread(target=self._start_p2p_server).start()
        Thread(target=self._start_api_server).start()
        Thread(target=self._start_sync_daemon).start()

    def _start_p2p_server(self):
        """启动P2P服务端（HTTP协议）

        监听配置的P2P端口，处理其他节点的:
        - 区块推送(/block)
        - 区块请求(/blocks/*)
        - 交易广播(/tx)
        """
        self.app.run(port=self.p2p_port)

    def _start_api_server(self):
        """启动外部API服务（HTTP协议）

        提供用户可访问的REST接口：
        - 区块链数据查询
        - 交易提交
        - 网络状态查看
        """
        api_app = Flask(__name__)
        api_app.run(port=self.api_port)

    def _request_full_chain(self, peer_address: str):
        """从指定节点请求完整区块链并验证"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                logging.info(f"Requesting full chain from {peer_address} (attempt {attempt + 1})")

                response = requests.get(
                    f"http://{peer_address}/blocks/full",
                    timeout=10 + attempt * 5  # 递增超时
                )

                if response.status_code != 200:
                    self.P2P_neighbor[peer_address]['status'] = 'disconnected'
                    raise Exception(f"HTTP {response.status_code}")

                chain_data = response.json()
                if not chain_data:
                    raise ValueError("Empty chain data")

                new_chain = Blockchain.deserialize(chain_data, self.p2p_port, self.blockchain.db)
                if not new_chain:
                    raise ValueError("Invalid chain data")

                if not self._is_chain_valid(new_chain):  # 不使用new_chain本身的validate_chain方法是出于安全考虑
                    raise ValueError("Chain validation failed")

                # 验证通过后替换本地链
                self.blockchain.reload_blockchain(new_chain)
                self.mempool.rebuild_utxo_from_all_blocks(self.blockchain.db.get_all_blocks())
                self.mempool.transactions.clear()  # 清空交易池
                logging.info(f"Accepted new chain from {peer_address} (height: {new_chain.height()})")
                return True

            except Exception as e:
                logging.warning(f"Attempt {attempt + 1} failed for {peer_address}: {str(e)}")
                if attempt == max_retries - 1:
                    logging.error(f"Giving up on {peer_address} after {max_retries} attempts")
                time.sleep(1)

        return False

    def _calculate_local_difficulty(self) -> float:
        """计算本地链的总难度"""
        return sum(block.header.difficulty for block in self.blockchain.blockchain)

    @staticmethod
    def _is_chain_valid(chain: Blockchain) -> bool:
        """简易验证整条链的连续性、PoW和交易有效性
        完整验证建议from blockchain import Blockchain; 用Blockchain.validate_blockchain(chain)"""
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

    def sync_blockchain(self):
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
            self._save_network_state()

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
            # 如果对方链更长或难度更高，请求同步
            if best_peer[1] > self.blockchain.height() or \
                    (best_peer[1] == self.blockchain.height() and best_peer[
                        2] > self._calculate_local_difficulty()):
                self._request_full_chain(best_peer[0])

                print(f"\033[96m>>> 最高区块链的来源、高度、总难度: {best_peer}  同步完成\033[0m")  # 输出青色文本
                # 实际测试中发现会重入风险，输出两次一样内容，不过没有关系，在函数内部进行判断防范

        except Exception as e:
            logging.error(f"同步出错: {str(e)}")
        finally:
            self._save_network_state()

    def _sync_p2p_neighbor(self):
        """同步本地P2P信息"""
        for neighbor, meta in list(self.P2P_neighbor.items()):
            if meta.get('status') != 'connected':
                continue
            try:
                height_resp = requests.get(
                    f"http://{neighbor}/blocks/height",  # 获取最新块高并刷新
                    timeout=2
                )
                if height_resp.status_code == 200:
                    self.P2P_neighbor[neighbor]['height'] = height_resp.json().get('height', 0)
            except:
                pass
        self._save_network_state()

    def sync_loop(self):
        """网络层邻居节点同步-守护线程使用-重要

        内容：同步邻居区块链（最长链和最大难度原则）
            同步更新邻居P2P_neighbor信息
            时间间隔为SYNC_INTERVAL（一般为30秒）
        """
        while True:
            try:
                start_time = time.time()
                self.sync_blockchain()
                self._sync_p2p_neighbor()
                elapsed = int(time.time() - start_time)

                # 动态调整sleep时间，确保总间隔接近~self._system_default_synchronized_time
                sleep_time = max(0, self._system_default_synchronized_time - elapsed)
                time.sleep(sleep_time)

            except Exception as e:
                logging.error(f"Sync loop error: {str(e)}", exc_info=True)
                time.sleep(min(DEFUALT_RECOVERY_INTERVAL, self._system_default_synchronized_time * 2))  # 错误时短暂等待

    def _start_sync_daemon(self):
        """启动sync_loop守护进程"""
        try:
            Thread(
                target=self.sync_loop,
                daemon=True,
                name=f"NetworkSyncDaemon_p2p-port_{str(self.p2p_port)}"
            ).start()
            logging.info("Block sync daemon started")
        except Exception as e:
            logging.critical(f"Failed to start sync daemon: {str(e)}")

    def add_neighbor(self, address: str):
        """添加新的邻居节点（本实现单向添加，不通知对方）

        流程：
        1. 检查节点是否已存在
        2. 主动获取对方最新区块高度
        3. 添加到邻居列表
        """

        if not address or ':' not in address:
            logging.warning(f"Invalid neighbor address format: {address}")
            self._save_network_state()  # 保存网络状态到Redis
            return False

        try:
            ip, port = address.split(':')
            if not (1 <= int(port) <= 65535):
                raise ValueError("Invalid port number")
        except ValueError as e:
            logging.warning(f"Invalid neighbor address {address}: {str(e)}")
            self._save_network_state()  # 保存网络状态到Redis
            return False

        if address in self.P2P_neighbor:
            logging.debug(f"Neighbor {address} already exists")
            self._save_network_state()  # 保存网络状态到Redis
            return True

        try:
            # 验证节点可达性
            response = requests.get(
                f"http://{address}/blocks/latest",
                timeout=3
            )
            height = response.json().get('header', {}).get('index', 0) if response.status_code == 200 else 0
        except Exception as e:
            logging.warning(f"Failed to connect to neighbor {address}: {str(e)}")
            height = 0

        try:
            from datetime import datetime
            self.P2P_neighbor[address] = {
                'last_seen': datetime.now(),
                'status': 'connected',
                'height': height,
                'retry_count': 0
            }
            logging.info(f"Added new peer: {address} (height: {height})")
            self._save_network_state()  # 保存网络状态到Redis
            return True
        except Exception as e:
            logging.error(f"Failed to add neighbor {address}: {str(e)}")
            self._save_network_state()  # 保存网络状态到Redis
            return False

    def remove_neighbor(self, address: str, bidirectional=False) -> bool:
        """
        删除指定邻居节点（可选双向断开）

        Args:
            address: 目标节点地址 (ip:port)
            bidirectional: 是否通知对方也断开连接

        Returns:
            bool: 是否成功删除
        """
        if address not in self.P2P_neighbor:
            logging.warning(f"邻居节点不存在: {address}")
            return False

        try:
            # 可选：通知对方删除本节点（双向断开）
            if bidirectional:
                try:
                    requests.post(
                        f"http://{address}/peers/remove",
                        json={"address": f"127.0.0.1:{self.p2p_port}"},
                        timeout=3
                    )
                except Exception as e:
                    logging.warning(f"无法通知对方断开连接: {str(e)}")

            # 从本地邻居列表删除
            del self.P2P_neighbor[address]
            self._save_network_state()

            # 从Redis同步删除
            self.redis.del_hash("neighbors", address)

            logging.info(f"已删除邻居节点: {address}")
            return True

        except Exception as e:
            logging.error(f"删除邻居节点失败: {str(e)}")
            return False

    def remove_all_self_neighbor(self, address: str):
        """ 移除本地所有邻居节点"""
        if address in self.P2P_neighbor:
            # del self.P2P_neighbor[address]
            self.remove_neighbor(address, False)
            logging.warning(f"Removed peer: {address}")
        self._save_network_state()  # 保存邻居状态到Redis

    def broadcast_tx(self, tx: Transaction) -> bool:
        """广播交易到P2P网络（至少需要有1个节点应答成功广播）"""
        success_count = 0
        for neighbor, meta in list(self.P2P_neighbor.items()):
            if meta.get('status') != 'connected':
                continue

            try:
                response = requests.post(
                    f"http://{neighbor}/tx",  # 广播交易信息
                    json=tx.serialize(),
                    timeout=3
                )
                if response.status_code == 200:
                    success_count += 1
                    logging.info(f"Transaction {tx.Txid[:8]} broadcast to {neighbor} successfully")
                else:
                    raise Exception(f"HTTP {response.status_code}")
            except requests.exceptions.RequestException as e:
                logging.warning(f"Transaction {tx.Txid[:8]}  failed to broadcast to {neighbor}: {str(e)}")
                raise
        return success_count > 0

    def _update_utxo_for_received_tx(self, tx: Transaction):
        """处理新交易对UTXO的影响"""
        # 标记输入为已花费
        for vin in tx.vins:
            if not CoinbaseScript.is_coinbase(tx.generate_self_script()):
                self.mempool.utxo_monitor.mark_spent(vin.txid, vin.referid)

        # 添加新UTXO
        for idx, vout in enumerate(tx.vouts):
            self.mempool.utxo_monitor.add_utxo(
                tx.Txid,
                idx,
                vout.value,
                vout.pubkey_hash,
                f"OP_DUP OP_HASH160 {vout.pubkey_hash} OP_EQUALVERIFY OP_CHECKSIG"
            )

    def broadcast_block(self, block: Block) -> bool:
        """广播新区块到所有邻居节点（至少需要有1个节点应答成功广播）

        流程：
        1. 筛选有效邻居节点
        2. 通过HTTP POST发送区块数据
        3. 记录广播结果
        """
        if not block or not isinstance(block, Block):
            logging.error("Invalid block object for broadcasting")
            return False

        success_count = 0
        failed_neighbors = []

        for neighbor, meta in list(self.P2P_neighbor.items()):
            # if meta.get('status') != 'connected':
            #     continue
            # 无论如何试一试通讯
            try:
                # 发送区块
                headers = {'X-P2P-Port': str(self.p2p_port)}
                response = requests.post(
                    f"http://{neighbor}/block",  # 对用对方的receive_block，广播区块
                    json=block.serialize(),
                    headers=headers,
                    timeout=5
                )

                if response.status_code == 200:
                    # 如果对方更新成功，则更新本地记录当中的邻居高度
                    # 其他条件下程序也会主动更新邻居高度（守护进程中），确保最新值
                    try:
                        height_resp = requests.get(
                            f"http://{neighbor}/blocks/height",
                            timeout=3
                        )
                        if height_resp.status_code == 200:
                            self.P2P_neighbor[neighbor]['height'] = height_resp.json().get('height', 0)
                    except:
                        pass

                    success_count += 1
                    logging.info(f"Block {block.header.index} broadcast to {neighbor}")
                    self.P2P_neighbor[neighbor]['status'] = "connected"
                    self.P2P_neighbor[neighbor]['retry_count'] = 0
                else:
                    raise Exception(f"HTTP {response.status_code}")

            except Exception as e:
                logging.warning(f"Failed to broadcast block to {neighbor}: {str(e)}")
                failed_neighbors.append(neighbor)
                self.P2P_neighbor[neighbor]['retry_count'] = meta.get('retry_count', 0) + 1

                # 超过重试次数则标记为断开
                if self.P2P_neighbor[neighbor]['retry_count'] > 3:
                    self.P2P_neighbor[neighbor]['status'] = 'disconnected'
                    logging.warning(f"Marked neighbor {neighbor} as disconnected")

        # 清理长期断开的节点
        self._cleanup_disconnected_neighbors_after_broadcast()

        return success_count > 0

    def _cleanup_disconnected_neighbors_after_broadcast(self):
        """清理长期断开的邻居节点"""
        from datetime import datetime
        now = datetime.now()
        to_remove = []

        for address, meta in self.P2P_neighbor.items():
            if meta.get('status') == 'disconnected':
                last_seen = meta.get('last_seen')
                if last_seen and (now - last_seen).total_seconds() > 3600:  # 断开状态超过1小时
                    to_remove.append(address)

        for address in to_remove:
            try:
                del self.P2P_neighbor[address]
                logging.info(f"Removed disconnected neighbor: {address}")
            except Exception as e:
                logging.warning(f"Failed to remove neighbor {address}: {str(e)}")
        self._save_network_state()

    def validate_and_add_one_block(self, block: Block) -> bool:
        """完整单个区块验证流程

        验证步骤：
        1. 基础结构验证
        2. 区块高度连续性检查
        3. 前哈希匹配验证
        4. 交易有效性验证
        5. PoW难度验证
        6. Coinbase交易验证
        7. Merkle根验证
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
            if not self.mempool.validate_transaction(tx):
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
        if MiningModule.calculate_merkle_root(txids) != block.header.merkle_root:
            logging.warning("默克尔根不匹配！")
            return False

        # 5. 添加区块到链
        self.blockchain.add_block(block)
        self.mempool.update_utxo(block_transactions=block.txs_data)
        return True

    def cleanup_resources(self):
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

    # 以下函数是人工操作，用于调试或立即同步场景：
    # hsync_one_block() 是增量同步一次，_request_one_block是辅助
    # hsync_one_blockchain() 全量同步一次
    # verify_db_connections() init验证所有数据库连接
    # reset_mongodb() init清空并重建MongoDB UTXO数据（mempool中）
    # clear_leveldb() 清空LevelDB数据库

    def _request_one_block(self, start_height: int):
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
                    if self.validate_and_add_one_block(block):
                        logging.info(f"成功同步区块 {block.header.index}")
            except Exception as e:
                logging.error(f"从节点 {neighbor} 同步失败: {str(e)}")
                # self.remove_all_self_neighbor(neighbor)

    def hsync_one_block(self):
        """手动触发单区块增量同步（可能因为局部最优而失败）"""

        try:
            max_height = max([meta['height'] for meta in self.P2P_neighbor.values()])
            if max_height > self.blockchain.height():
                self._request_one_block(self.blockchain.height() + 1)
                print(f"\033[96m>>> SYNC —— {max_height} vs {self.blockchain.height()}\033[0m")  # 输出青色文本
            else:
                print(f"\033[96m>>> SYNC already finished —— {max_height} vs {self.blockchain.height()}\033[0m")  # 输出青色文本
        except ValueError:
            print(f"\033[93m>>> SYNC failed for some reason\033[0m")  # 输出黄色文本

    def hsync_one_blockchain(self):
        """手动触发全量区块链增量同步"""
        self.sync_blockchain()

    def verify_db_connections(self):
        """验证所有数据库连接"""
        db_checks = [
            hasattr(self.blockchain, 'db'),
            hasattr(self.mempool, 'redis'),
            hasattr(self.mempool.utxo_monitor, 'db')
        ]  # 确保3个数据库（LevelDB/Redis/MongoDB）连接正常

        if not all(db_checks):
            raise RuntimeError("数据库连接未正确初始化")

    def reset_mongodb(self):
        """清空并重建MongoDB UTXO数据（mempool中）"""
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
        else:
            logging.error(f"重置MongoDB失败：数据库未连接")

    def clear_leveldb(self):
        """清空LevelDB数据库"""
        if self.blockchain.is_db_connected():
            try:
                # 遍历删除所有区块
                self.blockchain.db.clear_all()
            except Exception as e:
                logging.error(f"清空LevelDB失败: {str(e)}")
                raise

if __name__ == "__main__":
    # 初始化节点
    print("------------------NETWORK.PY start------------------")
    blockchain = Blockchain(p2p_port=5000)
    mempool = Mempool(p2p_port=5000)
    mempool.utxo_monitor.load_utxos()
    mempool.flush_current_size()
    network = NetworkInterface(5000, 5001, blockchain, mempool, None)
    miner = MiningModule()

    # 添加初始节点
    network.add_neighbor("192.168.1.2:5000")
    network.add_neighbor("10.0.0.3:6000")

    # 挖到新区块后广播
    new_block = miner.mine_block(
        miner_address="17LVrmuCzzibuQUJ265CUdVk6h6inrTJKV"
    )
    if network.validate_and_add_one_block(new_block):
        network.broadcast_block(new_block)
