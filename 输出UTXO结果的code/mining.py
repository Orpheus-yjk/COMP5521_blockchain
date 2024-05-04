import hashlib
import time
import json
import block as block

# the upper bound of all potential nonces
MAX_NONCE = 2**32

# adjust the difficulty every ? blocks
DIFFICULTY_ADJUST_BLOCK = 100

# the average time used for mining a new block(milliseconds)
AVERAGE_MINING_TIME = 10 * 1000

# perform PoW in a iteration manner
def proof_of_work(block_header, difficulty_bits):
    # calculate the difficulty target from difficulty bits

    """
        proof_of_work
        :return: the nonce which satisfies the target
    """

    target = 2**(256 - difficulty_bits)

    # perform the iteration, until finding a nonce which satisfies the target
    for nonce in range(MAX_NONCE):
        hash_result = hashlib.sha256(
            (str(block_header) + str(nonce)).encode()).hexdigest()
        # hash_res = hashlib.sha256(
        #     str(hash_res).encode('utf-8')).hexdigest()
        if int(hash_res, 16) < target:
            print(f'success with nonce {nonce}\n')
            print(f'hash is:\t\t {hash_res}')
            return nonce
    # target cannot be satisfied even all nonces are traversed
    print(f'failed after {MAX_NONCE} tries\n')
    return MAX_NONCE

def update_difficulty(blockchain, difficulty):
    # update difficulty every DIFFICULTY_ADJUST_BLOCK blocks

    """
        update_difficulty
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