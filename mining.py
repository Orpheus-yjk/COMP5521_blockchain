"""
存放和挖矿有关的函数

挖矿支持：
实现动态难度PoW算法
自动构建Merkle树
区块头哈希计算优化
"""

__author__ = 'YJK developer'
__date__ = '2025-04'

import time
import hashlib
from typing import List

from transactions import Transaction
from blockchain import BlockHeader, Block

__all__ = ['MiningModule']

CRYPTO_NAME = "YJK"  # 换算关系：1 YJK = 10^6 最小单位
UNIT_OFFSET = 1000000
MINE_SUBSIDY = 500  # 单位 YJK；开采一个区块的奖励

DIFFICULTY = 4
LAST_BLOCK_HASH = '0'*64
LAST_BLOCK_TIME = time.time()
TRANSACTION_COUNT_LIMIT = 10

class MiningModule:
    """配备挖矿、难度调整算法"""

    def __init__(self, difficulty=DIFFICULTY, last_block_hash=time.time(), last_block_time=LAST_BLOCK_TIME, mining_reward = MINE_SUBSIDY*UNIT_OFFSET):
        self.difficulty = difficulty
        self.last_block_hash = last_block_hash
        self.last_block_time = last_block_time
        self.mining_reward = mining_reward

    def reset_difficulty(self, difficulty):
        """更新数据"""
        self.difficulty = difficulty

    def reset_last_block_hash(self, last_block_hash):
        """更新数据"""
        self.last_block_hash = last_block_hash

    def reset_last_block_time(self, last_block_time):
        """更新数据"""
        self.last_block_time = last_block_time

    def reset_mining_reward(self, mining_reward):
        """更新数据"""
        self.mining_reward = mining_reward

    @staticmethod
    def _calculate_merkle_root(txids: List[str]) -> str:
        """计算Merkle树根"""
        if not txids:
            return hashlib.sha256(b'').hexdigest()

        while len(txids) > 1:
            if len(txids) % 2 != 0:
                txids.append(txids[-1])  # 修复方案: 复制最后一个元素（比特币的 Merkle 树实现方式）
            txids = [hashlib.sha256((txids[i] + txids[i + 1]).encode()).hexdigest()
                     for i in range(0, len(txids), 2)]
        return txids[0]

    def mine_block(self, mempool, blockchain, miner_address):
        """工作量证明挖矿"""

        # 构造只包含coinbase交易的完整区块
        coinbase_tx = Transaction.create_coinbase_Tx(
            blockchain.height()+1,
            miner_address,
            self.mining_reward  # 默认值500 * 10 ** 6 ，当前区块奖励
        )
        txs = [coinbase_tx] + mempool.get_top_transactions(TRANSACTION_COUNT_LIMIT)  # 选择高优先级交易
        merkle_root = MiningModule._calculate_merkle_root([tx.Txid for tx in txs])  # 计算默克尔根
        # 构造区块头
        block_header = BlockHeader(blockchain.height()+1, time.time(), self.last_block_hash, self.difficulty, merkle_root, 0)

        nonce = 0
        target = '0' * self.difficulty

        # 动态难度调整
        self._adjust_difficulty(blockchain)

        # 寻找有效nonce
        while True:
            block_header.nonce = nonce
            block_hash = block_header.calculate_blockheader_hash()
            if block_hash.startswith(target):
                break
            nonce += 1

        mined_block = Block(
            index=block_header.index,
            timestamp=block_header.timestamp,
            prev_hash=block_header.prev_hash,
            difficulty=block_header.difficulty,
            merkle_root=block_header.merkle_root,
            nonce=block_header.nonce,
            txs_data=txs
        )

        return mined_block

    def _adjust_difficulty(self, blockchain):
        """动态难度调整算法"""
        # 简单实现：每10个区块调整一次
        if blockchain.height() % 10 == 0:
            time_diff = time.time() - self.last_block_time
            self.last_block_time = time.time()
            target_time = 600  # 10分钟目标
            if time_diff < target_time * 0.9:
                self.difficulty += 1
            elif time_diff > target_time * 1.1:
                self.difficulty = max(1, self.difficulty - 1)


if __name__ == "__main__":
    pass
