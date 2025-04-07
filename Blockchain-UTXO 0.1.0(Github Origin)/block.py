# -*- coding: utf-8 -*-

"""区块链结构原型包含以下基本内容。a) 索引：当前区块的高度。b) 时间戳。c) 上一个区块哈希。d) 当前区块哈希。e) 难度：区块哈希开头的位数，动态变化。f) 随机数：用于计算区块哈希的随机数。g) 交易的Merkle根。h) 数据：交易。

block.py里面定义了block_header和Block类。
block_header包含区块的元数据，比如索引、时间戳、前一个区块的哈希值、难度、默克尔根和随机数。
Block类则组合了block_header和交易数据，并计算区块的哈希值。
"""

__author__ = 'COMP5521_YJK\'s_Team'
__date__ = '2023-12-6'

import json
from hashlib import sha256

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
        calculate_block_hash(): 计算当前区块（头）哈希
    """
    def __init__(self, index=0, timestamp=0.0, prev_hash="0", difficulty=0, merkle_root=0, nonce=0):
        self.index = index
        self.timestamp = timestamp  # float32
        self.prev_hash = prev_hash
        self.difficulty = difficulty
        self.nonce = nonce
        self.merkle_root = merkle_root

    def calculate_block_hash(self):
        """计算当前区块（头）哈希"""
        block_header_string = json.dumps(self.__dict__, sort_keys=True)  # json序列化
        return sha256(sha256(block_header_string.encode()).hexdigest().encode()).hexdigest()  # 经过两次 SHA-256 计算生成

class Block():
    """完整的区块结构。

    头部信息 + 交易数据 + 自动计算区块哈希（双重SHA-256加密）。类似"账本的一页纸"，记录交易信息，供Transaction查询使用。
    """
    def __init__(self, index=0, timestamp=0, prev_hash="0", difficulty=0, merkle_root=0, nonce=0, data=[]):
        """
        :param index: 索引号
        :param timestamp: 时间戳
        :param prev_hash: 前区块哈希
        :param difficulty: 挖矿难度
        :param merkle_root: 默克尔根（交易指纹）
        :param nonce: 随机数
        :param data: 该区块搭载的成功交易的信息（Transactions, Txs）
        """
        self.header=BlockHeader(
            index=index, timestamp=timestamp, prev_hash=prev_hash,
            difficulty=difficulty, merkle_root=merkle_root, nonce=nonce
        )

        self.hash = self.header.calculate_block_hash()  # 当前区块哈希
        self.data = data.copy()  # 该区块搭载的成功的交易数据，即Tx[]（==Txs，交易数据列表）
