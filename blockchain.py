# -*- coding: utf-8 -*-

"""区块链结构原型包含以下基本内容。a) 索引：当前区块的高度。b) 时间戳。c) 上一个区块哈希。d) 当前区块哈希。e) 难度：区块哈希开头的位数，动态变化。f) 随机数：用于计算区块哈希的随机数。g) 交易的Merkle根。h) 数据：交易。

block.py里面定义了block_header和Block类。
block_header包含区块的元数据，比如索引、时间戳、前一个区块的哈希值、难度、默克尔根和随机数。
Block类则组合了block_header和交易数据，并计算区块的哈希值。
Blochcain类包含区块链的链式数据结构。

Blochcain类的validate_blockchain函数的步骤包括：
1. 检查区块链中每个区块的索引是否连续，确保没有缺失或重复的区块。
2. 验证每个区块的prev_hash是否与前一个区块的哈希一致，确保链条的正确连接。
3. 调用每个区块的validate_block方法，确保区块自身的数据（如哈希计算）是正确的。
4. 验证每个区块的工作量证明，即区块哈希是否满足当时的难度要求（以指定数量的前导零开头）。
5. 检查Merkle根是否正确，确保交易数据没有被篡改。
6. 可能需要验证区块中的交易，比如检查交易签名和UTXO是否有效，但根据现有代码，这部分可能在mempool或网络层处理，暂时不在此函数中实现。
实现步骤：
- 遍历区块链中的所有区块。
- 对于每个区块，检查其索引是否为前一个区块索引+1。
- 检查prev_hash是否等于前一个区块的哈希。
- 调用block.validate_block()验证区块哈希的正确性。
- 检查区块哈希是否以正确数量的前导零开头（根据该区块的难度）。
- 重新计算Merkle根，确保与区块头中的一致。
"""

__author__ = 'YJK developer'
__date__ = '2025-04'

import json
import hashlib
import logging
import copy

from transactions import Transaction
from db_module import LevelDBModule

__all__ = ['BlockHeader', 'Block', 'Blockchain']

TRANSACTION_LIMIT = 1024

class BlockHeader:
    """包含区块元数据。
    Attributes:
        index: 索引号
        timestamp: 时间戳
        prev_hash: 前区块哈希
        difficulty: 挖矿难度
        nonce: 随机数
        merkle_root: 默克尔根（交易指纹）

    Methods:
        calculate_blockheader_hash(): 计算当前区块头哈希
    """
    def __init__(self, index=0, timestamp=0, prev_hash="0", difficulty=0, merkle_root=0, nonce=0):
        self.index = index
        self.timestamp = timestamp
        self.prev_hash = prev_hash
        self.difficulty = difficulty
        self.nonce = nonce
        self.merkle_root = merkle_root

    def calculate_blockheader_hash(self):
        """计算当前区块头哈希"""
        block_header_string = json.dumps(self.__dict__, sort_keys=True)  # json序列化
        return hashlib.sha256(hashlib.sha256(block_header_string.encode()).hexdigest().encode()).hexdigest()  # 经过两次 SHA-256 计算生成，返回str

class Block():
    """完整的区块结构。

    其他未列明Attributes：
    Magic no： value always 0xD9B4BEF9（主网。比特币测试网：0x0709110B）；Magic Num 的核心作用是网络标识和数据验证
    Version： Block version number；协议升级（软分叉/硬分叉），节点根据 Version 决定如何解析区块（旧节点可能忽略新规则，而新节点支持新特性）
    Block size： number of bytes following up to end of block；位置：通常不在区块头内部，而是作为区块元数据的一部分（如比特币的区块存储格式）
    Transaction counter： Positive integer, number of Transactions
    Transactions Fee
    Output Total
    Block Reward

    头部信息 + 交易数据 + 自动计算区块哈希（双重SHA-256加密）。类似"账本的一页纸"，记录交易信息，供Transaction查询使用。
    """
    def __init__(self, index=0, timestamp=0, prev_hash="0", difficulty=0, merkle_root=0, nonce=0, txs_data=None):
        """
        :param index: 索引号
        :param timestamp: 时间戳
        :param prev_hash: 前区块哈希
        :param difficulty: 挖矿难度
        :param merkle_root: 默克尔根（交易指纹）
        :param nonce: 随机数
        :param txs_data: 该区块搭载的成功交易的信息（transactions, txs）
        """
        txs_data = txs_data if txs_data else []
        if len(txs_data)>TRANSACTION_LIMIT:
            logging.warning(f"Block contains too many Transactions(more than {TRANSACTION_LIMIT}) and may not be accept by validators.")
        self.header=BlockHeader(
            index=index, timestamp=timestamp, prev_hash=prev_hash,
            difficulty=difficulty, merkle_root=merkle_root, nonce=nonce
        )

        block_hash_data = "HASH LIST:" + self.header.calculate_blockheader_hash()  # 当前区块头哈希
        for tx in txs_data:
            block_hash_data += str(tx.serialize())  # 序列化信息
        self.block_hash = hashlib.sha256(hashlib.sha256(block_hash_data.encode()).hexdigest().encode()).hexdigest()  # 返回值str
        self.txs_data = copy.deepcopy(txs_data)  # 该区块搭载的成功的交易数据，即Tx[]（==Txs，交易数据列表）
        # TODO：it is recommended for merchants to wait for a minimum of 6 confirmations

    def validate_block(self):
        """验证block哈希。"""
        block_hash_data_new = "HASH LIST:" + self.header.calculate_blockheader_hash()
        for tx in self.txs_data:
            block_hash_data_new += str(tx.serialize())
        block_hash_new = hashlib.sha256(hashlib.sha256(block_hash_data_new.encode()).hexdigest().encode()).hexdigest()
        if block_hash_new != self.block_hash: return False
        else:return True

    def serialize(self):
        return {
            'header': {
                'index': self.header.index,
                'prev_hash': self.header.prev_hash,
                'merkle_root': self.header.merkle_root,
                'timestamp': self.header.timestamp,
                'difficulty': self.header.difficulty,
                'nonce': self.header.nonce
            },
            'transactions': [tx.serialize() for tx in self.txs_data],
        }

    @classmethod
    def deserialize(cls, data):
        header = BlockHeader(
            index=data['header']['index'],
            prev_hash=data['header']['prev_hash'],
            merkle_root=data['header']['merkle_root'],
            timestamp=data['header']['timestamp'],
            difficulty=data['header']['difficulty'],
            nonce=data['header']['nonce']
        )
        txs = [Transaction.deserialize(tx) for tx in data['transactions']]
        return cls(
            index=header.index,
            prev_hash=header.prev_hash,
            merkle_root=header.merkle_root,
            timestamp=header.timestamp,
            difficulty=header.difficulty,
            nonce=header.nonce,
            txs_data=txs
        )

class Blockchain:
    """区块链数据结构

    处理分叉场景的流程
        1.发现分叉
        节点A发现节点B的链高度更高或累计难度更大时，请求完整链数据。

        2.验证新链
        检查每个区块的连续性（prev_hash匹配）
        验证所有区块的PoW和交易有效性
        计算整条链的累计难度

        3.链切换决策
        最长链原则：选择高度更高的链
        最大难度原则：如果高度相同，选择累计难度更大的链
        回滚本地链：如果接受新链，需：
            清空当前未确认交易池（mempool）
            重新计算UTXO集

        4.广播新链
            节点A切换成功后，向邻居广播自己的新链状态。
    """
    def __init__(self, p2p_port, db=None):
        self.blockchain = []
        self.p2p_port = p2p_port

        if db:
            self.db = db    # 初始化LevelDB，将区块链数据持久化到LevelDB
        else:
            try:
                self.db = LevelDBModule(db_name="blockchain_rawdata_port_" + str(p2p_port))
            except:
                self.db = None
                logging.error("区块链无法连接到LevelDB")

    def height(self):
        """返回区块链高度"""
        return len(self.blockchain)

    def calculate_chain_difficulty(self) -> float:
        """计算链的总难度（用于最长链原则）"""
        return sum(block.header.difficulty for block in self.blockchain)

    def add_block(self, block):
        """添加区块"""
        self.blockchain.append(block)
        # 存储到LevelDB
        self.db.save_block(block.block_hash, block.serialize())

    def reload_blockchain(self, one_Blockchain) -> bool:
        """重载区块链"""
        if self.validate_blockchain(one_Blockchain):
            # 清空本地 LevelDB 数据
            if self.is_db_connected():
                try:
                    # 遍历删除所有区块
                    for key, _ in self.db._db:
                        self.db._db.delete(key)
                    logging.info("已清空本地 LevelDB 数据")
                except Exception as e:
                    logging.error(f"清空 LevelDB 失败: {str(e)}")
                    return False

            # 更新内存中的区块链数据
            self.blockchain = copy.deepcopy(one_Blockchain.blockchain)

            # 重新保存所有区块到 LevelDB
            for block in self.blockchain:
                self.db.save_block(block.block_hash, block.serialize())
            return True

        return False

    @staticmethod
    def validate_blockchain(one_Blockchain) -> bool:
        """验证区块链的完整性和有效性  关键改进说明：

        1.区块哈希验证
        调用每个区块的validate_block()方法，确保区块数据未被篡改。

        2.工作量证明（PoW）验证
        检查区块哈希是否满足该区块难度要求（前导零数量）。

        3.Merkle根验证
        重新计算交易的Merkle根，确保交易数据完整性。

        4.链式结构验证

        5.检查前哈希（prev_hash）的连续性

        6.检查索引号的递增性

        7.创世区块前哈希必须为"0"

        8.高度一致性验证
        确保区块链长度与高度值一致（高度=长度）。
        """
        if not one_Blockchain.blockchain:
            return True  # 空链视为有效

        previous_block = None
        for block in one_Blockchain.blockchain:
            # 1. 验证区块自身哈希有效性
            if not block.validate_block():
                # logging.error(f"区块 {block.header.index} 哈希验证失败")
                return False

            # 2. 验证工作量证明（难度目标）
            target = '0' * block.header.difficulty
            current_hash = block.header.calculate_blockheader_hash()
            if not current_hash.startswith(target):
                # logging.error(f"区块 {block.header.index} PoW验证失败，难度不匹配")
                return False

            # 3. 验证Merkle根
            from mining import MiningModule  # 延迟导入避免循环依赖
            txids = [tx.Txid for tx in block.txs_data]
            calculated_merkle = MiningModule._calculate_merkle_root(txids)
            if calculated_merkle != block.header.merkle_root:
                # logging.error(f"区块 {block.header.index} Merkle根不匹配")
                return False

            # 4. 验证链式连接性
            if previous_block:
                if block.header.prev_hash != previous_block.block_hash:
                    # logging.error(f"区块 {block.header.index} 前哈希不匹配")
                    return False
                if block.header.index != previous_block.header.index + 1:
                    # logging.error(f"区块索引不连续，当前索引 {block.header.index}")
                    return False
            else:
                # 创世区块特殊检查
                if not all(c == '0' for c in block.header.prev_hash):
                    # logging.error(f"创世区块前哈希不为0 {block.header.prev_hash}")
                    return False

            previous_block = block

        # 5. 区块链高度一致性验证
        if len(one_Blockchain.blockchain) != one_Blockchain.height():
            # logging.error("区块链高度与区块数量不一致")
            return False

        return True

    def is_db_connected(self) -> bool:
        """检查LevelDB连接是否正常"""
        try:
            return self.db is not None and hasattr(self.db, '_db')
        except:
            return False

    def load_chaindata_from_db(self):
        """从LevelDB加载区块链数据"""
        if self.is_db_connected():
            try:
                all_blocks = self.db.get_all_blocks()
                if all_blocks:
                    self.blockchain = [Block.deserialize(block_data) for block_data in all_blocks.values()]
            except:
                pass

    def serialize(self):
        """序列化整个区块链"""
        return {
            'blockchain': [block.serialize() for block in self.blockchain],
            # 'p2p_port': self.p2p_port  # 不传递port信息
        }

    @classmethod
    def deserialize(cls, data, local_p2p_port, db=None):
        """反序列化区块链"""
        chain = cls(local_p2p_port, db)  # 如果提供了现有数据库连接，使用它
        if not chain.db:
            try:
                chain.db = LevelDBModule(db_name="blockchain_rawdata_port_" + str(local_p2p_port))
            except:
                logging.warning("LevelDB数据库连接已存在")
                pass
        # 优先从LevelDB加载
        sidechain = [Block.deserialize(block_data) for block_data in data['blockchain']]
        chain.blockchain = sidechain
        if_data_correct = Blockchain.validate_blockchain(chain)
        if chain.db:
            all_blocks = chain.db.get_all_blocks()
            if all_blocks:
                chain.blockchain = [Block.deserialize(block_data) for block_data in all_blocks.values()]
        if Blockchain.validate_blockchain(chain):
            if not (if_data_correct and len(sidechain)>chain.height()):
                return chain
        # 其次从参数读取
        chain.blockchain = sidechain
        return chain

if __name__ == "__main__":
    pass
