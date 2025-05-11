"""
在 Python 中设计一个 Mempool（内存池）类，可以模拟区块链节点中待处理交易的存储和管理机制。以下是完整的设计方案，包含交易存储、验证、优先级排序、内存限制等功能。

关键设计点：
    1. 交易存储
        使用字典 {txid: Transaction} 快速查找和去重。
        记录内存占用，防止溢出。
    2. 交易验证
        检查双花（输入是否已被使用）。
        支持自定义验证规则（如签名校验）。
    3. 优先级排序
        按 fee 降序排列，矿工优先打包高手续费交易。
    4. 内存管理
        超过限制时淘汰低手续费交易（模拟真实节点行为）。
    5. RBF 支持
        允许替换未确认交易（需提高手续费）。
"""

__author__ = 'YJK developer'
__date__ = '2025-04'

import time
import json
import logging
from typing import List
from threading import Lock

from transactions import Transaction
from math_util import VerifyHashAndSignatureUtils
from blockchain import Block
from db_module import MongoDBModule
from db_module import RedisModule


class UTXOManager:
    """UTXO状态跟踪器

    并发问题场景：当多个线程或进程同时尝试修改UTXO集合时（例如区块同步和交易处理同时进行），可能导致UTXO状态不一致。
    表现：UTXO添加失败
    解决方案：在UTXOManager类中对关键操作（如add_utxo、mark_spent）加锁

    数据库连接问题场景：MongoDB连接超时或断开，导致add_utxo操作失败。
    表现：日志中显示MongoDB操作异常（如超时、连接重置）。
    解决方案：增加重试机制
    """
    def __init__(self, p2p_port):
        self.lock = Lock()  # 初始化锁
        self.utxos = {}  # {txid: {vout_index: (amount, address)}}
        self.spent_outputs = set()  # {(txid, vout_index)}
        self.db = MongoDBModule(db_name="utxo_db_port_"+str(p2p_port))
        self._load_utxos()  # 使用MongoDB存储UTXO

    def _load_utxos(self):
        """从MongoDB加载UTXO"""
        self.utxos = {}
        utxos = self.db.get_utxos_by_address("*")  # 获取所有UTXO
        for utxo in utxos:
            if utxo['txid'] not in self.utxos:
                self.utxos[utxo['txid']] = {}
            self.utxos[utxo['txid']][utxo['vout_index']] = (
                utxo['amount'], utxo['address'])

    def add_utxo(self, txid: str, vout_index: int, amount: int, address: str, script_pubkey: str, max_retries=3):
        """添加UTXO"""
        for attempt in range(max_retries):
            try:
                with self.lock:  # 加锁
                    if txid in self.utxos and vout_index in self.utxos[txid]:
                        logging.warning(f"UTXO已存在: {txid}:{vout_index}")
                        return False
                    if txid not in self.utxos:
                        self.utxos[txid] = {}
                    self.utxos[txid][vout_index] = (amount, address)
                    self.db.add_utxo(txid, vout_index, amount, address, script_pubkey)
                    return True
            except Exception as e:
                if attempt == max_retries - 1:
                    logging.error(f"UTXO添加失败（最终尝试）: {str(e)}")
                    return False
                time.sleep(1)

    # 因为区块链是不允许修改的，所以不能这么写del_utxo。UTXO实际上不会删除使用过的交易；而是通过标记输入为已花费。除非重新加载区块链
    # def del_utxo(self, txid: str, vout_index: int):
    #     if txid not in self.utxos:
    #         raise ValueError("UTXO当中没有这个交易ID！")
    #     del self.utxos[txid][vout_index]

    def mark_spent(self, txid: str, vout_index: int):
        """标记使用过的UTXO"""
        self.spent_outputs.add((txid, vout_index))
        # 更新MongoDB
        self.db.mark_as_spent(txid, vout_index)

    def is_spent(self, txid: str, vout_index: int) -> bool:
        """判断是否使用过"""
        return (txid, vout_index) in self.spent_outputs

    def get_balance(self, address: str) -> int:
        """获取指定地址的可用余额（未被花费的UTXO总额）"""
        balance = 0
        for txid, vouts in self.utxos.items():
            for vout_index, (amount, addr) in vouts.items():
                if addr == address and not self.is_spent(txid, vout_index):
                    balance += amount
        return balance

    def flush_data(self) -> bool:
        """清除MongoDB utxo数据及内存中的UTXO状态

        Returns:
            bool: 是否成功清空所有数据
        """
        try:
            # 清空MongoDB数据
            result = self.db.utxo_collection.delete_many({})

            # 清空内存中的UTXO状态
            with self.lock:
                self.utxos = {}
                self.spent_outputs = set()

            logging.info(f"成功清空UTXO数据，删除记录数: {result.deleted_count}")
            return True

        except Exception as e:
            logging.error(f"UTXO清理失败 - {str(e)}")
            return False


class Mempool:
    """Mempool 类设计：包含 增删改查

    核心功能：
        存储未确认交易（txid 作为键，交易数据作为值）。
        验证交易有效性（防止双花、签名错误等）。
        按手续费（fee）排序，优先打包高手续费交易。
        内存限制管理（防止内存溢出）。
        支持交易替换（RBF, Replace-by-Fee）。

    Mempool类具有对外来Transaction的独立基础验证能力。
    """

    def __init__(self, max_size_mb: int = 10, p2p_port = 5000):
        """
        Args:
            max_size_mb: 最大内存（默认10MB）
            p2p_port: 网络接口
        """
        self.transactions = {}  # {txid: Transaction} ； self.transactions: Dict[str, Transaction]。优化UTXO交易查询放在程序运行堆栈当中
        self.redis = RedisModule(db_name="mempool_db_port_"+str(p2p_port))
        self._load_transactions()
        self.utxo_monitor = UTXOManager(p2p_port)  # UTXO状态跟踪
        self.p2p_port = p2p_port
        self.max_size = max_size_mb * 1024 * 1024
        self.current_size = 0  # 当前内存占用
        self.last_block_time = time.time()
        self.difficulty = 4  # 初始难度（前导零个数）

    def _load_transactions(self, max_retries=3):
        """从Redis加载交易，带重试机制"""
        for attempt in range(max_retries):
            try:
                tx_list = self.redis.get_list("transactions")
                for tx_data in tx_list:
                    tx = Transaction.deserialize(json.loads(tx_data))
                    self.transactions[tx.Txid] = tx
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    raise RuntimeError(f"从Redis加载交易失败：{str(e)}")
                time.sleep(1)

    def _save_transactions(self):
        """保存交易到Redis"""
        tx_list = [json.dumps(tx.serialize()) for tx in self.transactions.values()]
        self.redis.push_list("transactions", *tx_list)

    def add_transaction(self, tx: Transaction) -> bool:
        """添加交易到 Mempool，返回是否成功

        问题场景：无效交易（如双花）被尝试添加到UTXO集合。
        表现：交易验证失败后仍尝试添加UTXO。
        解决方案：在add_transaction中提前严格验证交易有效性
        """
        # 1. 基础检查
        if tx.Txid in self.transactions:
            return False

        # 2. 验证交易有效性
        if not self._validate_transaction(tx):
            logging.warning(f"交易验证失败: txid: {tx.Txid}")
            return False

        # 3. 内存管理
        tx_size = tx.calculate_raw_size()
        while self.current_size + tx_size > self.max_size:
            if not self._evict_low_fee_tx():
                return False

        # 加入mempool
        self.transactions[tx.Txid] = tx
        self._save_transactions()
        return True

    def remove_transaction(self, txid: str):
        """移除交易（例如被打包进区块后）"""
        if txid in self.transactions:
            tx = self.transactions[txid]
            self.current_size -= len(tx.data) if tx.data else 100
            del self.transactions[txid]
            self._save_transactions()

    def _validate_transaction(self, tx: Transaction) -> bool:
        """完整交易验证流程"""
        print("\n--- 交易验证详细信息 ---")
        print(f"交易ID: {tx.Txid}")
        print("输入详情:")
        for i, vin in enumerate(tx.vins):
            print(f"输入{i}:")
            print(f"  txid: {vin.txid}")
            print(f"  referid: {vin.referid}")
            print(f"  pubkey: {vin.pubkey.hex() if isinstance(vin.pubkey, bytes) else vin.pubkey}")
            print(f"  signature: {vin.signature.hex() if isinstance(vin.signature, bytes) else vin.signature}")
        # 1. 验证输入有效性
        total_input = 0
        for vin in tx.vins:
            print("vin: ",vin.serialize())
            # 检查UTXO是否存在且未花费
            is_coinbase = tx.is_coinbase(tx.generate_self_script())
            print(is_coinbase)
            if self.utxo_monitor.is_spent(vin.txid, vin.referid):
                logging.warning(f"双花检测: {vin.txid}:{vin.referid}")
                return False
            elif vin.txid not in self.utxo_monitor.utxos.keys() and not is_coinbase:
                logging.warning(f"未收到有关交易的任何信息，故无法使用: {vin.txid}:{vin.referid}")
                return False

            if is_coinbase:
                total_input += tx.vouts[0].value
                continue
            utxo = self.utxo_monitor.utxos.get(vin.txid, {}).get(vin.referid)
            # 验证引用是否正确
            if not utxo:
                logging.warning(f"未引用正确的tx在tx_input中: {vin.txid}:{vin.referid}")
                return False

            message = tx.get_signature_message()
            public_key = bytes.fromhex(vin.pubkey) if isinstance(vin.pubkey, str) else vin.pubkey
            signature = bytes.fromhex(vin.signature) if isinstance(vin.signature, str) else vin.signature

            if not VerifyHashAndSignatureUtils.verify_signature(
                    public_key=public_key,
                    signature=signature,
                    message=message
            ):
                print("验证失败详细信息:")
                print("Public Key:", public_key.hex())
                print("Signature:", signature.hex())
                print("Message:", message.hex())
                logging.warning("签名验证失败")
                return False
            total_input += utxo[0]

        # 2. 验证输出有效性和手续费检查
        total_output = sum(vout.value for vout in tx.vouts)
        if total_output + tx.fee > total_input:
            logging.warning("所需金额（含手续费）超过输入金额")
            return False

        return True

    def update_utxo(self, block_transactions: List[Transaction]):
        """区块确认后更新UTXO"""

        for tx in block_transactions:
            # 标记输入为已花费
            for vin in tx.vins:
                self.utxo_monitor.mark_spent(vin.txid, vin.referid)

            # 添加新UTXO
            for idx, vout in enumerate(tx.vouts):
                self.utxo_monitor.add_utxo(tx.Txid, idx, vout.value, vout.pubkey_hash, "OP_DUP OP_HASH160 {} OP_EQUALVERIFY OP_CHECKSIG".format(vout.pubkey_hash))

    def get_top_transactions(self, n: int) -> List[Transaction]:
        """获取手续费最高的前n笔交易（矿工调用）"""
        if n>len(self.transactions):
            logging.warning("调取超过UTXO栈高数量的交易进行区块打包。已自动截断。")
            n = len(self.transactions)
        return sorted(
            self.transactions.values(),
            key=lambda x: -x.fee
        )[:n]

    def _evict_low_fee_tx(self) -> bool:
        """淘汰低费率交易"""
        if not self.transactions:
            return False

        tx = min(self.transactions.values(),
                 key=lambda x: x.fee / x.calculate_raw_size())  # lambda排序
        self.current_size -= tx.calculate_raw_size()
        del self.transactions[tx.Txid]
        return True

    def replace_transaction(self, old_Txid: str, new_Tx: Transaction) -> bool:
        """替换交易（RBF机制，资金发起人调用）"""
        if old_Txid not in self.transactions:
            return False

        old_Tx = self.transactions[old_Txid]
        if new_Tx.fee <= old_Tx.fee:
            print("新交易手续费必须高于旧交易")
            return False

        # 替换交易
        self.current_size -= len(old_Tx.data) if old_Tx.data else 100
        self.add_transaction(new_Tx)
        return True

    def rebuild_utxo_from_all_blocks(self, all_blocks):
        """当区块链被替换时，重置UTXO和交易池

        问题场景：区块链发生分叉后重组，UTXO状态需要回滚，但部分交易未被正确处理。
        表现：UTXO添加失败，且日志中出现区块高度不一致的警告。
        解决方案：在rebuild_utxo_from_all_blocks方法中确保UTXO完全重置
        """
        with self.utxo_monitor.lock:  # 加锁
            self.utxo_monitor = UTXOManager(self.p2p_port)  # 完全重建UTXO集
            # can_flush_db == False 是增量构建，如果中间经过了竞争挖矿导致的换链，会保留原来区块链废弃的块，一般不用
            can_flush_db = True
            if can_flush_db:
                self.utxo_monitor.flush_data()  # 清理废旧的utxo数据
            for block_data in all_blocks.values():
                block = Block.deserialize(block_data)
                self.update_utxo(block.txs_data)

    def reload_mempool_from_DB(self):
        """从数据库恢复类的所有数据"""
        pass
        # TODO: 从内存数据库中恢复数据

    def __repr__(self):
        return f"Mempool(交易数={len(self.transactions)}, " \
               f"占用内存={self.current_size}/{self.max_size} bytes({self.current_size / self.max_size:.2%}))"


# 使用示例
if __name__ == "__main__":
    # 初始化组件
    mempool = Mempool(p2p_port = 5000)

    # 创建测试交易
    tx1 = Transaction.create_coinbase_Tx(0, "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa", 625000000)
    tx2 = Transaction.create_coinbase_Tx(0, "1HGUt8BThQAjLtmqKAaRF4cHt5ia22HKsp", 625000000)

    # （1）添加交易
    try:
        mempool.add_transaction(tx1)  # True
        mempool.add_transaction(tx2)  # True
        print(mempool)
    except:
        logging.warning("test 1 failed")
    # 输出: Mempool(交易数=2, 占用内存=200/1048576 bytes)

    # (2) 获取高优先级交易（矿工打包）
    try:
        top_txs = mempool.get_top_transactions(1)
        print(f"手续费最高的交易: {top_txs[0].Txid}")
    except:
        logging.warning("test 2 failed")
    # 输出: 手续费最高的交易: tx2_data的哈希值

    # (3) 替换交易（RBF）
    try:
        tx1_new = Transaction.create_coinbase_Tx(0, "1Fz7YmTxTV1jFG8k9PPfsS8vqRfR68D8hD", 625000000)
        mempool.replace_transaction(tx1.txid, tx1_new)  # True
    except:
        logging.warning("test 3 failed")

    # (4) 交易被打包后移除
    try:
        mempool.remove_transaction(tx2.txid)
        print(repr(mempool))
    except:
        logging.warning("test 4 failed")
    # 输出: Mempool(交易数=1, 占用内存=100/1048576 bytes)
