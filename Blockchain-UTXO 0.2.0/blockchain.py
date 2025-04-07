# -*- coding: utf-8 -*-

"""区块链结构原型包含以下基本内容。a) 索引：当前区块的高度。b) 时间戳。c) 上一个区块哈希。d) 当前区块哈希。e) 难度：区块哈希开头的位数，动态变化。f) 随机数：用于计算区块哈希的随机数。g) 交易的Merkle根。h) 数据：交易。

block.py里面定义了block_header和Block类。
block_header包含区块的元数据，比如索引、时间戳、前一个区块的哈希值、难度、默克尔根和随机数。
Block类则组合了block_header和交易数据，并计算区块的哈希值。
Blochcain类包含区块链的链式数据结构。

Blochcain类的validate_blockchain函数的步骤可能包括：
1. 检查区块链中每个区块的索引是否连续，确保没有缺失或重复的区块。
2. 验证每个区块的prev_hash是否与前一个区块的哈希一致，确保链条的正确连接。
3. 调用每个区块的validate_block方法，确保区块自身的数据（如哈希计算）是正确的。
4. 验证每个区块的工作量证明，即区块哈希是否满足当时的难度要求（以指定数量的前导零开头）。
5. 检查Merkle根是否正确，确保交易数据没有被篡改。
6. 可能需要验证区块中的交易，比如检查交易签名和UTXO是否有效，但根据现有代码，这部分可能在mempool或网络层处理，暂时不在此函数中实现。
可能的实现步骤：
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
    def __init__(self, index=0, timestamp=0.0, prev_hash="0", difficulty=0, merkle_root=0, nonce=0):
        self.index = index
        self.timestamp = timestamp  # float32类型
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
    def __init__(self, index=0, timestamp=0, prev_hash="0", difficulty=0, merkle_root=0, nonce=0, txs_data=[]):
        """
        :param index: 索引号
        :param timestamp: 时间戳
        :param prev_hash: 前区块哈希
        :param difficulty: 挖矿难度
        :param merkle_root: 默克尔根（交易指纹）
        :param nonce: 随机数
        :param txs_data: 该区块搭载的成功交易的信息（transactions, txs）
        """
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
            'hash': self.block_hash
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
            header=header,
            txs_data=txs,
            block_hash=data['hash']
        )

class Blockchain:
    """区块链数据结构"""
    def __init__(self):
        self.blockchain = []

    def height(self):
        """返回区块链高度"""
        return len(self.blockchain)-1

    def add_block(self, block):
        """添加区块"""
        self.blockchain.append(block)

    def reload_blockchain(self, one_blockchain) -> bool:
        """因为区块链共识的原因需要重载blockchain。区块验证在network中做"""
        if self.validate_blockchain(one_blockchain):
            self.blockchain = copy.deepcopy(one_blockchain)
            return True
        else: return False

    def validate_blockchain(self, one_blockchain) -> bool:
        """验证区块链的完整性和有效性  关键改进说明：

        区块哈希验证
        调用每个区块的validate_block()方法，确保区块数据未被篡改。

        工作量证明（PoW）验证
        检查区块哈希是否满足该区块难度要求（前导零数量）。

        Merkle根验证
        重新计算交易的Merkle根，确保交易数据完整性。

        链式结构验证

        检查前哈希（prev_hash）的连续性

        检查索引号的递增性

        创世区块前哈希必须为"0"

        高度一致性验证
        确保区块链长度与高度值一致（高度=长度-1）。
        """
        previous_block = None
        for block in one_blockchain.blockchain:
            # 1. 验证区块自身哈希有效性
            if not block.validate_block():
                logging.error(f"区块 {block.header.index} 哈希验证失败")
                return False

            # 2. 验证工作量证明（难度目标）
            target = '0' * block.header.difficulty
            current_hash = block.block_hash
            if not current_hash.startswith(target):
                logging.error(f"区块 {block.header.index} PoW验证失败，难度不匹配")
                return False

            # 3. 验证Merkle根
            from mining import MiningModule  # 延迟导入避免循环依赖
            txids = [tx.Txid for tx in block.txs_data]
            calculated_merkle = MiningModule._calculate_merkle_root(txids)
            if calculated_merkle != block.header.merkle_root:
                logging.error(f"区块 {block.header.index} Merkle根不匹配")
                return False

            # 4. 验证链式连接性
            if previous_block:
                if block.header.prev_hash != previous_block.block_hash:
                    logging.error(f"区块 {block.header.index} 前哈希不匹配")
                    return False
                if block.header.index != previous_block.header.index + 1:
                    logging.error(f"区块索引不连续，当前索引 {block.header.index}")
                    return False
            else:
                # 创世区块特殊检查
                if block.header.prev_hash != "0":
                    logging.error("创世区块前哈希不为0")
                    return False

            previous_block = block

        # 5. 区块链高度一致性验证
        if len(one_blockchain.blockchain) != one_blockchain.height() + 1:
            logging.error("区块链高度与区块数量不一致")
            return False

        return True


if __name__ == "__main__":
    pass