# -*- coding: utf-8 -*-

"""
说明：和blockchain.py中的mine方法有重复，未被实际使用，已经被整合到Blockchain类中。
"""
__author__ = 'COMP5521_YJK\'s_Team'
__date__ = '2023-12-6'

import hashlib
import time
import json
import block as block

MAX_NONCE = 2**32  # 潜在 Nonces 的上界

DIFFICULTY_ADJUST_BLOCK = 100  # 每隔 n 块调整难度

AVERAGE_MINING_TIME = 10 * 1000  # 挖掘一个新区块的平均时间（毫秒）

# perform PoW in a iteration manner
def proof_of_work(block_header, difficulty_bits):
    """动态难度算法，proof_of_work，根据难度位计算难度目标。
        :param block_header：区块头
        :param difficulty_bits: 难度位
        :return: the nonce which satisfies the target
    """

    target = 2**(256 - difficulty_bits)
    # 进行迭代，直到找到满足目标要求的nonce
    for nonce in range(MAX_NONCE):
        hash_result = hashlib.sha256(
            (str(block_header) + str(nonce)).encode()).hexdigest()
        hash_res = hashlib.sha256(
            str(hash_result).encode('utf-8')).hexdigest()
        if int(hash_res, 16) < target:
            print(f'success with nonce {nonce}\n')
            print(f'hash is:\t\t {hash_res}')
            return nonce
    # 即使遍历所有nonces，也无法满足目标要求
    print(f'failed after {MAX_NONCE} tries\n')
    return MAX_NONCE

def update_difficulty(blockchain, difficulty):
    """每隔 DIFFICULTY_ADJUST_BLOCK 个区块更新难度
        :return: new difficulty
    """
    R = blockchain.last_block().timestamp - blockchain.the_last_n_block(DIFFICULTY_ADJUST_BLOCK).timestamp
    new_difficulty = difficulty * DIFFICULTY_ADJUST_BLOCK * AVERAGE_MINING_TIME / R
    return new_difficulty



def update_utxo_list():
    # 待实现
    return

def main(block_header, difficulty_bits):
    print(f'difficulty:\t\t {2**difficulty_bits} ({difficulty_bits} bits)\n')
    print('starting search ...')

    start_time = time.time()
    nonce = proof_of_work(block_header, difficulty_bits)
    end_time = time.time()

    elapsed_time = end_time - start_time
    print(f'elapsed time:\t {elapsed_time:.4f} seconds')
    print(f'hashrate:\t\t {float(int(nonce) / elapsed_time):.4f} hash/s')


if __name__ == '__main__':
    textBlock = block.Block()
    # content = 'This content should be a BLOCK HEADER, just replace me by that!'
    difficulty_bits = 20
    block_string = json.dumps(textBlock.__dict__, sort_keys=True)
    main(block_string, difficulty_bits)
