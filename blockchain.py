import time
import hashlib
from queue import Queue

from block import Block
from transactions import tx_output, tx_input, Transaction, NId, Npk, calculate_public_key_hash

import numpy as np

class Blockchain:
    def __init__(self, address = hashlib.sha256((str(np.random.randint(1,1000))).encode()).hexdigest()):
        self.mempool = []
        self.chain = []
        self.node_address = address # str(), representation of a node
        self.public_key , self.private_key = ("","")

        self.unspentTxOuts={}   ## key(address): [The payer//Queue(address)//, value//Queue(int)//, Txid//Queue(str)//...] easily
            ## 先实现P2PK  ##再实现P2PKH

        ## define parameters for mining
        # the upper bound of all potential nonces
        self.MAX_NONCE = 2 ** 32
        # adjust the difficulty every ? blocks
        self.DIFFICULTY_ADJUST_BLOCK = 10
        # the average time used for mining a new block(milliseconds)
        self.AVERAGE_MINING_TIME = 3

        self.NoneAddress = hashlib.sha256("NoneAddress".encode()).hexdigest()

        # 开始时假设所有节点的余额为0，因为要验证储蓄，有些麻烦。UXTO是不保存储蓄的。
            # 除非一次性生成n个coinbase，但一个区块只能保存一个coinbase，要等n个块很浪费
        # 所有的验证都基于区块链上进行，没有存款，节点的收入仅仅来自挖矿

        # Create the genesis block
        self.genesis_block()

    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
        ###Block operations and chain validating
    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————


    def genesis_block(self):
        """
        Create genesis block
        """
        if len(self.chain)>0:
            return
        genesis_block = Block(index=0, timestamp=time.time(), prev_hash="0", difficulty=4, merkle_root=0, data=[])
        self.chain.append(genesis_block)
        # 每个节点必须要约定创块时间， 因为每个节点的本地时钟并不相同

    def generate_merkle_root(self, input_level):        ###for Transactions
        def build_bottom_level(input_level):
            bottom_level = []
            for idx in range(0, len(input_level)):
                bottom_level.append(hashlib.sha256(input_level[idx].Txid.encode()).hexdigest())  ###string->hash->hash_string
            return bottom_level  ###str[]

        def build_next_level(prev_level):
            new_level = []
            i = 0
            while i < len(prev_level):
                if i+1<len(prev_level):
                    left_hash = prev_level[i]
                    right_hash = prev_level[i + 1]
                    new_level.append(hashlib.sha256((left_hash + right_hash).encode()).hexdigest())  ##combine left_hash and right_hash to make new hash
                else:
                    only_one_hash = prev_level[i]
                    new_level.append(only_one_hash)
                i += 2
            return new_level

        def end_loop(now_level):
            if len(now_level)==1:
                return now_level[0]
            elif len(now_level)==0:
                return 0
            else : return -1

        tree_level = build_bottom_level(input_level)

        while (end_loop(tree_level) == -1):
            tree_level = build_next_level(tree_level)
        return end_loop(tree_level)

    def prove_valid_chain(self, another_chain):
        return True ### for implement

    def reload_blockchain(self, Ablockchain):
        self.mempool = Ablockchain.mempool.copy()
        self.chain = Ablockchain.chain.copy()
        self.unspentTxOuts=Ablockchain.unspentTxOuts.deepcopy()   ###一定要深度完全拷贝

    def deal_with_fork(self, Ablockchain):
        ### using the max-length chain
        if (self.prove_valid_chain(Ablockchain.chain) and len(Ablockchain.chain)>len(self.chain)):
            self.reload_blockchain(Ablockchain)

    def last_block(self):
        """
        Return the last block
        """
        return self.chain[-1]

    def last_n_block(self, index):
        # used for update difficulty
        return self.chain[-index]

    def pickup_num_Transaction(self, num):
        pickup_Transactions=[]      ###Transaction[]
        for i in range(0,num):
            if i==len(self.mempool):
                break
            pickup_Transactions.append(self.mempool[i])
        return pickup_Transactions

    def del_num_Transcation(self, num):
        for i in range(0, num):
            if len(self.mempool)==0:
                break
            self.mempool.pop(0)

    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
        ### The following is the mining section, where mine() merges mining. py
        ### utilize the function above
    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————


    def mine(self):
        last_block = self.last_block()
        last_block_header=str(last_block.header.__dict__)   ##last block header
        difficulty_bits=last_block.header.difficulty

        target = 2 ** (256 - difficulty_bits)
        proof = -1

        # perform the iteration, until finding a nonce which satisfies the target
        for nonce in range(self.MAX_NONCE):
            hash_result = hashlib.sha256(hashlib.sha256((str(last_block_header) + str(nonce)).encode()).hexdigest().encode()).hexdigest()
            if int(hash_result, 16) < target:
                proof = nonce
                break
        ##mine successfully
        ## proof应该要加密 ？ ？ 做sign？

        length = len(self.mempool)   #后期应该换成blocksize
        pickup_Transcation = self.pickup_num_Transaction(length)        ###Transaction []
        self.del_num_Transcation(length)

        ###coinbase
        _Tx=Transaction.create_coinbase_Tx(noneTokenid= NId, vout_index = -1, pub_key=Npk, pub_key_hash=calculate_public_key_hash(self.public_key))     ###coinbase Transaction

        pickup_Transcation.append(_Tx)  #node get subsidy 1000
        print("Txid for coinbase Tx : %s" % (_Tx.Txid))
        ###UTXO也要更新
        if self.node_address not in self.unspentTxOuts.keys():
            tmp_q0=Queue()
            tmp_q0.put(self.NoneAddress)
            tmp_q1=Queue()
            tmp_q1.put(_Tx.sum_value)
            tmp_q2=Queue()
            tmp_q2.put(_Tx.Txid)
            tmp_q3=Queue()
            tmp_q3.put(-1);
            self.unspentTxOuts.update({self.node_address: [tmp_q0, tmp_q1, tmp_q2, tmp_q3]})
        else:
            self.unspentTxOuts[self.node_address][0].put(self.NoneAddress)
            self.unspentTxOuts[self.node_address][1].put(_Tx.sum_value)
            self.unspentTxOuts[self.node_address][2].put(_Tx.Txid)
            self.unspentTxOuts[self.node_address][3].put(-1)

        ### add block
        new_block = Block(index=last_block.header.index + 1,
                          timestamp=time.time(),
                          prev_hash=last_block.hash,
                          difficulty=last_block.header.difficulty,
                          merkle_root=self.generate_merkle_root(pickup_Transcation),
                          nonce=proof,
                          data=pickup_Transcation)      ###calculate the block hash at the same time

        # update difficulty
        if new_block.header.index  % self.DIFFICULTY_ADJUST_BLOCK == 0:
            new_block.header.difficulty=self.new_difficulty(new_block.header.difficulty)
        self.chain.append(new_block)
        return new_block.header.index


    def new_difficulty(self, difficulty):

        # 温和调整方案，可能需要多次调整才能让难度跟全网算力相适配
        # 获取从上一次调整到这次调整的实际用时
        actual_time_consumed = self.last_block().timestamp - self.the_last_n_block(self.DIFFICULTY_ADJUST_BLOCK).timestamp
        adjust_coefficient = self.DIFFICULTY_ADJUST_BLOCK * self.AVERAGE_MINING_TIME / actual_time_consumed

        if adjust_coefficient > 1:
            new_difficulty = difficulty + 1
        else:
            new_difficulty = difficulty - 1

        return new_difficulty


    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
        ### most important thing: money exchange (P2P Transfer)
    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————

    def print_nodeaddress(self):
        return self.node_address

    def transfer(self, address_payer, address_receiver, total_value):

        if not address_payer in self.unspentTxOuts.keys():
            print("No such address or it has no amount")
            return False

        ##require address_receiver to be an real address

        if address_receiver not in self.unspentTxOuts.keys():     ###build its infromation
            self.unspentTxOuts.update({address_receiver:[Queue(), Queue(), Queue()]})

        ###get old stakes
        sum_value=0
        index=0
        tmp_prepayer_queue=Queue()
        tmp_value_queue=Queue()
        tmp_Txid_queue=Queue()
        tmp_voutindex_queue=Queue()
        while sum_value<total_value and (not self.unspentTxOuts[address_payer][0].empty()):
            index = index+1
            tmp_prepayer=self.unspentTxOuts[address_payer][0].get()
            tmp_value=self.unspentTxOuts[address_payer][1].get()
            tmp_Txid=self.unspentTxOuts[address_payer][2].get()

            tmp_prepayer_queue.put(tmp_prepayer)
            tmp_value_queue.put(tmp_value)
            tmp_Txid_queue.put(tmp_Txid)
            sum_value = sum_value + tmp_value

        print("######")
        if sum_value<total_value:

            ###rollback
            while not tmp_prepayer_queue.empty():
                tmp_prepayer=tmp_prepayer_queue.get()
                tmp_value=tmp_value_queue.get()
                tmp_Txid=tmp_Txid_queue.get()
                tmp_voutindex=tmp_voutindex_queue.get()
                self.unspentTxOuts[address_payer][0].put(tmp_prepayer)
                self.unspentTxOuts[address_payer][1].put(tmp_value)
                self.unspentTxOuts[address_payer][2].put(tmp_Txid)

            return False
        else :
            ### create Transaction
            vins=[]
            vouts=[]
            while not tmp_prepayer_queue.empty():
                tmp_prepayer=tmp_prepayer_queue.get()
                tmp_value=tmp_value_queue.get()
                tmp_Txid=tmp_Txid_queue.get()
                vins.append(tx_input(tmp_Txid, -1, address_payer))  ### should implement pub_key later : pub_key = addressOne.signature
                vouts.append(tx_output(tmp_value, calculate_public_key_hash(address_receiver)))  ### should implement pub_key_hash later

            ###是否有残余的转给自己
            if sum_value>total_value:
                vouts[-1].value = vouts[-1].value - (sum_value - total_value)
                last_Txid=vins[-1].txid
                vins.append(tx_input(last_Txid, -1, address_payer))
                vouts.append(tx_output(sum_value - total_value, calculate_public_key_hash(address_payer)))

            ###生成新的Transaction
            new_Transaction=Transaction(vins, vouts)

            ###UTXO也要更新
            key=address_receiver      ## 修改 receiver的Transactions记录
            self.unspentTxOuts[key][0].put(address_payer)       ###money from
            self.unspentTxOuts[key][1].put(total_value)
            self.unspentTxOuts[key][2].put(new_Transaction.Txid)
            self.mempool.append(new_Transaction)        ###put Transaction into the mempool

            ###是否有残余的，单独更新payer的Transactions记录
            if sum_value > total_value:
                key=address_payer
                self.unspentTxOuts[key][0].put(address_payer)  ###money from
                self.unspentTxOuts[key][1].put(sum_value - total_value)
                self.unspentTxOuts[key][2].put(new_Transaction.Txid)

            return True ##transfer successfully