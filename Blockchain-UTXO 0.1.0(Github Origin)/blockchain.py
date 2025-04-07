# -*- coding: utf-8 -*-

"""这是一个简化版的区块链实现，涵盖基本功能，但实际应用中需要更多完善，如网络通信、安全性增强等。

blockchain.py是核心部分，实现了区块链的主要逻辑。
Blockchain类初始化时创建创世块，管理内存池（mempool）和未花费的交易输出（UTXO，Unspent Transaction Outputs的缩写）。
挖矿函数mine()负责生成新的区块，包括工作量证明（PoW）和难度调整。
还有处理交易的方法transfer()，涉及UTXO的更新和交易的验证。

TODO:
    基础要求未完成：
    - 未实现P2P网络、数字签名等安全机制。
    - 缺少交易验证逻辑。未实现完整共识机制。
    - UTXO使用Python队列，实际应用需数据库。
    - 项目实现和说明书的实际差异。特别是UTXO，mempool。该设计中避免了UTXO的加锁解锁操作使代码简单，但也带来潜在安全问题。
    高级要求：
    - 设计模式、类解耦，安全性，高并发场景处理。
    - 完善的注释，规范且清晰易懂的代码。

FIXME:
    挖掘一个新区块的平均时间（毫秒）实现有误。
    blockchain.py中的“unspentTxOuts”使用队列存储UTXO，这可能不够高效，且实现上有潜在错误。
    仅仅完成了无偿记账的区块链。实际当中记账是有回报的。
"""

__author__ = 'COMP5521_YJK\'s_Team'
__date__ = '2023-12-6'


import time
import hashlib
from queue import Queue
import logging

from block import Block
from transactions import tx_output, tx_input, Transaction

import numpy as np

class Blockchain:
    """Blockchain类是blockchain.py的核心部分，实现了区块链的主要逻辑。相当于"账本"，管理整个链条。

    核心功能：
    - 创建创世区块（第一个区块）
    - 挖矿机制（工作量证明）
    - 自动调整挖矿难度（每10个区块调整一次）
    - 管理未花费交易（UTXO系统）
    - 处理转账交易

    Attributes:
        node_address：str类型, 代表节点地址
        mempool：内存池，用队列维护
                说明：交易进入内存池等待打包，下次挖矿时交易会被打包进区块
        chain: 区块链数据，本设计用队列存
        unspentTxOuts: 本设计中存放UTXO相关的信息
                说明：追踪所有未花费的代币。类似现金系统：交易必须使用完整的"纸币"，找零会产生新输出
    """
    def __init__(self, address = hashlib.sha256((str(np.random.randint(1,1000000))).encode()).hexdigest()):
        """
        :param address: 节点地址（该区块链账本持有者在网络中的地址）
        """
        self.node_address = address # str类型, 代表节点地址
        self.mempool = []
        self.chain = []
        self.unspentTxOuts={}
        # 基础实现 字典内容格式：
        # key- address(str): [Queue(address(str)) - The payer, Queue(address(str)) - value, Queue(address(str)) - Txid, etc.] 单笔交易裸信息
        # 可以使用 collections.deque（双端队列），单线程时更高效
        # TODO：先实现P2PK  改进方向 - 再实现P2PKH

        # config: 定义挖矿参数
        self.MAX_NONCE = 2 ** 32  # 潜在 Nonces 的上界

        self.DIFFICULTY_ADJUST_BLOCK = 10  # 每隔 n 块调整难度

        self.AVERAGE_MINING_TIME = 3  # 挖掘一个新区块的平均时间（毫秒）。保持平均3秒出块速度

        self.NoneAddress = "NoneAddress" # 如果没提供节点信息，则占位符；同时也是方便调试
        # TODO: 待后续签名部分完整后应该书写 类似于hashlib.sha256("NoneAddress".encode()).hexdigest()
        # FIXME: 正确的“地址生成关系“：从生成私钥（os.urandom(32) 32位），到获得比特币地址，应经过3步

        # 我们需要在最开始就决定的规则：
        # 开始时假设所有节点的余额为0。因为要验证储蓄，有些麻烦，UXTO是不保存储蓄的。
        # 除非一次性生成n（若干）个coinbase，但一个区块只能保存一个coinbase，要等n个块很浪费
        # 因此，所有的验证都基于区块链上进行，没有存款，规定节点的收入仅仅来自挖矿无赠予

        self.genesis_block()  # 自动创建创世区块

    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
        # 区块操作和链验证
    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
    def genesis_block(self):
        """
        创建创世区块
        """
        if len(self.chain)>0:
            return
        genesis_block = Block(index=0, timestamp=time.time(), prev_hash="0", difficulty=4, merkle_root=0, data=[])  # 4 魔法数字
        # 初始难度值为4
        self.chain.append(genesis_block)
        # 注意每个节点必须要约定创块时间 - 网络部分，因为每个节点的本地时钟并不相同

    def generate_merkle_root(self, transaction_list):
        """将多个交易生成唯一指纹。快速验证交易是否存在"""
        def traverse_leaves (transaction_list):
            """处理树的叶子节点层"""
            leaves_level = []
            for idx in range(0, len(transaction_list)):
                leaves_level.append(hashlib.sha256(transaction_list[idx].Txid.encode()).hexdigest())  ###string->hash->hash_string
            return leaves_level  # array of str

        def traverse_one_level_up(prev_level):
            """处理树的上一层"""
            new_level = []
            cursor = 0
            while cursor < len(prev_level):
                if cursor+1<len(prev_level):
                    left_hash = prev_level[cursor]
                    right_hash = prev_level[cursor + 1]
                    # 将 left_hash 和 right_hash 合并为新的哈希值
                    new_level.append(hashlib.sha256((left_hash + right_hash).encode()).hexdigest())
                else:
                    only_one_hash = prev_level[cursor]
                    # 只有一个哈希值时保留
                    new_level.append(only_one_hash)
                cursor += 2
            return new_level

        def can_end_loop(now_level):
            """判断循环是否结束"""
            if len(now_level)==1:
                return now_level[0]  # 一般结束情况
            elif len(now_level)==0:
                return 0  # 特殊情况：Transaction空队列
            else : return -1  # 未到达树根

        # 获取默克尔树根
        tree_level = traverse_leaves(transaction_list)
        while (can_end_loop(tree_level) == -1):
            tree_level = traverse_one_level_up(tree_level)
        return can_end_loop(tree_level)

    def prove_valid_chain(self, another_chain):
        return True
        # TODO: 待完善 验证链合法 要和签名等部分一起

    def reload_blockchain(self, one_blockchain):
        """重载区块链"""
        # TODO: 需要和存储一起做
        self.mempool = one_blockchain.mempool.copy()
        self.chain = one_blockchain.chain.copy()
        self.unspentTxOuts=one_blockchain.unspentTxOuts.deepcopy()   # 一定要深度拷贝

    def deal_with_fork(self, one_blockchain):
        # use the max-length chain
        if (self.prove_valid_chain(one_blockchain.chain) and len(one_blockchain.chain)>len(self.chain)):
            self.reload_blockchain(one_blockchain)

    def last_block(self):
        """返回最后一个区块"""
        return self.chain[-1]

    def last_n_block(self, index):
        # 用于更新挖矿困难度 新难度 = 旧难度 × 预期时间 / 实际耗时
        return self.chain[-index]

    def pickup_num_Transaction(self, num):
        """新块打包

        - 交易进入内存池等待打包
        - 下次挖矿时交易会被打包进区块
        """
        pickup_Transactions=[]
        for i in range(0,num):  # 本设计采用顺序打包
            # FIXME: 实际中往往采取reward高(fee高)的区块优先级高
            if i==len(self.mempool):
                break
            pickup_Transactions.append(self.mempool[i])
        return pickup_Transactions

    def del_num_Transcation(self, num):
        """从本地的mempool删除区块"""
        for i in range(0, num):
            if len(self.mempool)==0:  # 一般不会发生
                break
            self.mempool.pop(0)

    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
        # 下面是采矿部分，其中 mine() 合并了来自mining.py的采矿部分。
        # 利用上面的功能
    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————

    def mine(self):
        """挖矿获得奖励 独立的工作量证明算法实现 - 通过大量计算寻找符合条件的随机数（nonce）"""
        last_block = self.last_block()
        last_block_header_serialization=str(last_block.header.__dict__)  # 最后区块头的序列化
        difficulty_bits=last_block.header.difficulty
        target = 2 ** (256 - difficulty_bits)
        proof = None

        # 进行迭代，直到找到满足目标要求的nonce
        for nonce in range(self.MAX_NONCE):
            hash_result_iter_1 = hashlib.sha256((last_block_header_serialization + str(nonce)).encode()).hexdigest()
            hash_result_iter_2 = hashlib.sha256(hash_result_iter_1.encode()).hexdigest()  # 双重SHA-256哈希
            if int(hash_result_iter_2, 16) < target:
                proof = nonce
                break  # 挖矿成功

        # TODO: 拿到的proof应该要加密以便别人不能拿到 ？在sign的时候做？

        length = len(self.mempool)  # TODO: 后期应该换成block_capable_size(系统规定或者用户声明)，因为实际上一个块不能装下整个mempool
        pickup_Transcation = self.pickup_num_Transaction(length)  # 挖矿、然后才能记账
        self.del_num_Transcation(length)

        # Coinbase
        _Tx=Transaction.create_coinbase_Tx(self.NoneAddress, self.node_address, '')
        # TODO: 完善这些参数
        print("Len of pickup_Transcation before: %d" %(len(pickup_Transcation)))
        pickup_Transcation.append(_Tx)  # This node get subsidy 1000
        # TODO: 实际中挖矿有竞争机制
        print("Len of pickup_Transcation after: %d" %(len(pickup_Transcation)))
        print("Len of Txid for coinbase Tx : %d" % (len(_Tx.Txid)))
        print("Txid for coinbase Tx : %s" % (_Tx.Txid))

        # UTXO也要更新
        if self.node_address not in self.unspentTxOuts.keys():
            # 新建关于node_address的一笔交易表单 Q0 Q1 Q2 etc. ，在UTXO _dict里，相当于记录一笔UTXO
            # FIXME: UTXO使用Python队列，是权宜之计。实际应用需数据库。而且还要支持网络完整的共识机制
            tmp_q0=Queue()
            tmp_q0.put(self.NoneAddress)
            tmp_q1=Queue()
            tmp_q1.put(_Tx.sum_value)
            tmp_q2=Queue()
            tmp_q2.put(_Tx.Txid)
            self.unspentTxOuts.update({self.node_address: [tmp_q0, tmp_q1, tmp_q2]})
        else:
            self.unspentTxOuts[self.node_address][0].put(self.NoneAddress)
            self.unspentTxOuts[self.node_address][1].put(_Tx.sum_value)
            self.unspentTxOuts[self.node_address][2].put(_Tx.Txid)

        # 添加区块
        new_block = Block(index=last_block.header.index + 1,
                          timestamp=time.time(),
                          prev_hash=last_block.hash,
                          difficulty=last_block.header.difficulty,
                          merkle_root=self.generate_merkle_root(pickup_Transcation),
                          nonce=proof,
                          data=pickup_Transcation)

        # 更新挖矿难度
        if new_block.header.index  % self.DIFFICULTY_ADJUST_BLOCK == 0:
            new_block.header.difficulty=self.new_difficulty(new_block.header.difficulty)
        self.chain.append(new_block)
        return new_block.header.index

    def new_difficulty(self, difficulty):
        """
        :param difficulty: 旧挖矿难度
        :return: 新的挖矿难度
        """
        R = self.last_block().header.timestamp - self.last_n_block(self.DIFFICULTY_ADJUST_BLOCK).header.timestamp
        # 新难度 = 旧难度 × 预期时间 / 实际耗时
        # 保持平均3秒出块速度
        new_difficulty = round(difficulty * self.DIFFICULTY_ADJUST_BLOCK * self.AVERAGE_MINING_TIME / R)
        return new_difficulty

    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
        # 最重要的事情：货币兑换 (P2P Transfer)
    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
    def print_nodeaddress(self):
        return self.node_address

    def transfer(self, address_payer, address_receiver, total_value):
        """
        转账交易。
        :param address_payer: 付款人地址（哈希）
        :param address_receiver: 收款人地址（哈希）
        :param total_value: 总金额（会根据该金额搜集足够多的UTXO进行消费，转账给接收者多余的转给自己；出现失败则回滚为原状态）
        :return: 交易成功或失败
        """
        if not address_payer in self.unspentTxOuts.keys():
            logging.warning("No such address or it has zero amount")
            return False

        if address_receiver not in self.unspentTxOuts.keys():
            # 新建关于address_receiver的一笔交易表单 Q0 Q1 Q2 etc. ，在UTXO _dict里，预备记录一笔UTXO
            self.unspentTxOuts.update({address_receiver:[Queue(), Queue(), Queue()]})

        # 搜集足够多的UTXO进行消费
        sum_value=0
        index=0
        # FIXME: UTXO使用Python队列，是权宜之计。实际应用需数据库。而且还要支持网络完整的共识机制
        tmp_prepayer_queue=Queue()
        tmp_value_queue=Queue()
        tmp_Txid_queue=Queue()
        while sum_value<total_value and (not self.unspentTxOuts[address_payer][0].empty()):
            index = index+1
            tmp_prepayer=self.unspentTxOuts[address_payer][0].get()  # 弹出第一个元素
            tmp_value=self.unspentTxOuts[address_payer][1].get()  # 弹出第一个元素
            tmp_Txid=self.unspentTxOuts[address_payer][2].get()  # 弹出第一个元素

            print("tmp_prepayer : %s" % (tmp_prepayer))
            print("tmp_value : %d" % (tmp_value))
            print("tmp_Txid : %s" % (tmp_Txid))
            print()
            tmp_prepayer_queue.put(tmp_prepayer)
            tmp_value_queue.put(tmp_value)
            tmp_Txid_queue.put(tmp_Txid)
            sum_value = sum_value + tmp_value

        if sum_value<total_value:
            # 总数不够，发生错误，回滚至原状态
            while not tmp_prepayer_queue.empty():
                tmp_prepayer=tmp_prepayer_queue.get()  # 弹出第一个元素
                tmp_value=tmp_value_queue.get()  # 弹出第一个元素
                tmp_Txid=tmp_Txid_queue.get()  # 弹出第一个元素
                self.unspentTxOuts[address_payer][0].put(tmp_prepayer)  # 这里基于本设计后续做法（如果有残余的转给自己），不考虑原顺序直接在队尾压入；如果考虑则用deque
                self.unspentTxOuts[address_payer][1].put(tmp_value)
                self.unspentTxOuts[address_payer][2].put(tmp_Txid)
            logging.warning("No enough money. Roll back")
            return False
        else :
            # 创建交易
            print("Create Transaction")
            vins=[]
            vouts=[]
            while not tmp_prepayer_queue.empty():
                tmp_prepayer=tmp_prepayer_queue.get()
                tmp_value=tmp_value_queue.get()
                tmp_Txid=tmp_Txid_queue.get()
                vins.append(tx_input(tmp_Txid, address_receiver, ''))
                # TODO: should implement pub_key later : pub_key = addressOne.signature
                vouts.append(tx_output(tmp_value, ''))
                # TODO: should implement pub_key_hash later

            # 如果有残余的转给自己
            if sum_value>total_value:
                vouts[-1].value = vouts[-1].value - (sum_value - total_value)
                last_Txid=vins[-1].txid
                vins.append(tx_input(last_Txid, address_payer, ''))
                # TODO: should implement pub_key later : pub_key = addressOne.signature
                vouts.append(tx_output(sum_value - total_value, ''))
                # TODO: should implement pub_key_hash later

            # 生成新的Transaction
            new_Transaction = Transaction(vins, vouts)
            self.mempool.append(new_Transaction)  # 将 Transaction 放入 mempool

            # UTXO也要更新
            key=address_receiver  # 修改 receiver的Transactions记录
            self.unspentTxOuts[key][0].put(address_payer)
            self.unspentTxOuts[key][1].put(total_value)
            self.unspentTxOuts[key][2].put(new_Transaction.Txid)

            # 有残余转给自己的，单独更新payer的UTXO记录（第二笔）
            if sum_value > total_value:
                key=address_payer
                self.unspentTxOuts[key][0].put(address_payer)  ###money from
                self.unspentTxOuts[key][1].put(sum_value - total_value)
                self.unspentTxOuts[key][2].put(new_Transaction.Txid)

            return True  # 顺利转入