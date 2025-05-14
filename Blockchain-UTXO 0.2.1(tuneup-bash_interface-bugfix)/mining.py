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
LAST_TIME = int(time.time())
TRANSACTION_COUNT_LIMIT = 10

class MiningModule:
    """配备挖矿、难度调整算法"""

    def __init__(self, difficulty=DIFFICULTY, last_block_hash='0'*64, last_timestamp=LAST_TIME, mining_reward = MINE_SUBSIDY*UNIT_OFFSET):
        self.difficulty = difficulty
        self.last_block_hash = last_block_hash
        self.last_timestamp = last_timestamp
        self.mining_reward = mining_reward
        self.chain_height = 0
        self.mempool = None

        # 寻找有效nonce
        # 为了在本机的不同进程当中更好地随机区分挖矿速度，采用方式如下
        # python实现生成1~100的数列，然后对该数列进行完全随机打乱返回新数列，按顺序作为增量的依据
        import random
        # 生成 0~9999 的数列
        numbers = list(range(0, 10000))
        # 随机打乱（原地修改）
        random.shuffle(numbers)
        self.number_list = numbers

    def reset_difficulty(self, difficulty):
        """更新数据"""
        self.difficulty = difficulty

    def get_difficulty(self):
        """获取挖矿难度"""
        return self.difficulty

    def reset_last_block_hash(self, last_block_hash):
        """更新数据"""
        self.last_block_hash = last_block_hash

    def reset_last_timestamp(self, last_timestamp):
        """更新数据"""
        self.last_timestamp = last_timestamp

    def get_mining_reward(self):
        """获取挖矿奖励便于调整奖励"""
        return self.mining_reward

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

    # 块注释
    # 以下3个函数全为挖矿前更新
    # update_chain_height, update_chain_lasthash, update_mempool
    def update_chain_height(self, _height):
        self.chain_height = _height

    def update_chain_lasthash(self, _last_hash):
        self.reset_last_block_hash(_last_hash)

    def update_mempool(self, _mempool):
        self.mempool = _mempool

    def mine_block(self, miner_address):
        """工作量证明挖矿"""

        # 动态难度调整
        self._adjust_difficulty(self.chain_height + 1)

        # 构造只包含coinbase交易的完整区块
        coinbase_tx = Transaction.create_coinbase_Tx(
            self.chain_height + 1,
            miner_address,
            self.mining_reward  # 默认值500 * 10 ** 6 ，当前区块奖励
        )

        # 获取待打包交易
        candidate_txs = self.mempool.get_top_transactions(TRANSACTION_COUNT_LIMIT - 1)

        # 检查双花问题
        used_utxos = set()  # 记录已使用的UTXO
        valid_txs = [coinbase_tx]  # 有效交易列表

        for tx in candidate_txs:
            # 跳过coinbase交易
            from transactions import CoinbaseScript
            if CoinbaseScript.is_coinbase(tx.generate_self_script()):
                continue

            # 检查交易输入是否已被使用
            conflict = False
            for vin in tx.vins:
                utxo_key = (vin.txid, vin.referid)
                if utxo_key in used_utxos:
                    print(f"\033[93m检测到双花交易 txid: {tx.Txid[:8]}... 已丢弃，尝试使用已花费的UTXO-key {utxo_key}\033[0m")
                    conflict = True
                    break

            if not conflict:
                # 验证交易有效性
                if self.mempool._validate_transaction(tx):
                    # 记录使用的UTXO
                    for vin in tx.vins:
                        used_utxos.add((vin.txid, vin.referid))
                    valid_txs.append(tx)
                else:
                    print(f"\033[93m交易验证失败 txid: {tx.Txid[:8]}... 已丢弃\033[0m")

        merkle_root = MiningModule._calculate_merkle_root([tx.Txid for tx in valid_txs])  # 计算默克尔根
        # 构造区块头
        print(f"\033[96m>>> 当前挖矿难度: {self.difficulty}\033[0m")  # 输出青色文本
        block_header = BlockHeader(self.chain_height+1, int(time.time()), self.last_block_hash, self.difficulty, merkle_root, 0)


        _nonce = 0
        target = '0' * self.difficulty
        # 寻找有效nonce
        # 为了在本机的不同进程当中更好地随机区分挖矿速度，采用方式如下
        # python实现生成1~100的数列，然后对该数列进行完全随机打乱返回新数列，按顺序作为增量的依据
        _len = len(self.number_list)
        _base = 0
        _pnt = 0
        _mining_start_time = time.time()
        while True:
            _nonce = _base + self.number_list[_pnt]
            block_header.nonce = _nonce
            block_hash = block_header.calculate_blockheader_hash()
            if block_hash.startswith(target):
                break

            _pnt += 1
            if _pnt == _len:
                _pnt = 0
                _base += _len
        print(f">>> 挖矿所用时间: {time.time() - _mining_start_time : .1f}", "sec")

        mined_block = Block(
            index=block_header.index,
            timestamp=block_header.timestamp,
            prev_hash=block_header.prev_hash,
            difficulty=block_header.difficulty,
            merkle_root=block_header.merkle_root,
            nonce=block_header.nonce,
            txs_data=valid_txs
        )

        return mined_block, self.difficulty

    def _adjust_difficulty(self, new_chain_height):
        """动态难度调整算法"""
        # 简单实现：每5个区块调整一次
        if new_chain_height % 5 == 1:
            time_diff = time.time() - self.last_timestamp
            self.last_timestamp = int(time.time())
            target_time = 300  # 5个块的时间目标，这里随意定（近似于比特币开始标准的600sec / 10个块）
            if time_diff < target_time * 0.9:
                self.difficulty += 1
            elif time_diff > target_time * 1.1:
                self.difficulty = max(1, self.difficulty - 1)


if __name__ == "__main__":
    pass