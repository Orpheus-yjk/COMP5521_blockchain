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
    - 项目实现和说明书的实际差异。特别是UTXO，mempool。该设计中避免了UTXO的加锁解锁操作使代码简单，但也带来潜在安全问题。
    高级要求：
    - 设计模式、类解耦，安全性，高并发场景处理。
    - 完善的注释，规范的代码。

FIXME:
    挖掘一个新区块的平均时间（毫秒）实现有误。
    仅仅完成了无偿记账的区块链。实际当中记账是有回报的。
"""

__author__ = 'YJK'
__date__ = '2023-12-6'

import time
import copy
import hashlib
import logging

from couchdb import ResourceConflict, ResourceNotFound
from ecdsa import SigningKey, NIST256p

from block import Block
from transactions import tx_output, tx_input, Transaction
from storage import DB

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
    """
    def is_hexadecimal(self, s):
        """是否16进制"""
        try:
            int(s, 16)
            return True
        except ValueError:
            return False

    def __init__(self, public_key_hex='', private_key_hex=''):   # elliptic_curve="NIST256p"
        # 以十六进制字符串表示的椭圆曲线密钥, e.g. 1c43ed486812a07f09b069bdf6d3362a8740030f2f7e477d8925e078158d4638
        self.private_key = private_key_hex
        self.public_key = public_key_hex
        if (not self.is_hexadecimal(self.private_key)) or (not self.is_hexadecimal(self.public_key)):
            logging.warning("Invalid key. Generate a new pair randomly. (node address)")
            sk = SigningKey.generate(curve=NIST256p)
            pk = sk.get_verifying_key()
            self.private_key = sk.to_string().hex()
            self.public_key = pk.to_string().hex()
            # print(sk, pk)
        self.node_address = Transaction.calculate_public_key_hash(self.public_key) # derived from public key
        self.mempool = []   # record block No. and Txid
        self.chain = []
        self.utxos = {}     # record user_pub_key, block No. and along with index
        self.usedTxlist=[]
        self.NoneAddress = hashlib.sha256("NoneAddress".encode("utf8")).hexdigest()
        self.NullTx = Transaction([], [])
        self.NullTxid = self.NullTx.Txid
        self.Nullpub_key = hashlib.sha256(str(time.time()).encode("utf8")).hexdigest()
        # 潜在 Nonces 的上界
        self.MAX_NONCE = 2 ** 32
        # 每隔 n 块调整难度
        self.DIFFICULTY_ADJUST_BLOCK = 10
        # 挖掘一个新区块的平均时间（毫秒）。保持平均3秒出块速度
        self.AVERAGE_MINING_TIME = 3
        # 所有的验证都基于区块链上进行，没有存款，节点的收入仅仅来自挖矿
        self.genesis_block()    # Create the genesis block

        self.database = DB()
        # self.database.db()

    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
    # Block operations
    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————

    def genesis_block(self):
        """创建创世区块"""
        if len(self.chain) > 0:
            return
        genesis_block = Block(index=0, timestamp=time.time(), prev_hash="0", difficulty=4, merkle_root=0,
                              data=[])  # 4 魔法数字
        # 初始难度值为4
        self.chain.append(genesis_block)
        # 注意每个节点必须要约定创块时间 - 网络部分，因为每个节点的本地时钟并不相同

    def generate_merkle_root(self, transaction_list):
        """将多个交易生成唯一指纹。快速验证交易是否存在"""
        def traverse_leaves(transaction_list):
            """处理树的叶子节点层"""
            leaves_level = []
            for idx in range(0, len(transaction_list)):
                leaves_level.append(
                    hashlib.sha256(transaction_list[idx].Txid.encode()).hexdigest())  ###string->hash->hash_string
            return leaves_level  # array of str

        def traverse_one_level_up(prev_level):
            """处理树的上一层"""
            new_level = []
            cursor = 0
            while cursor < len(prev_level):
                if cursor + 1 < len(prev_level):
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
            if len(now_level) == 1:
                return now_level[0]  # 一般结束情况
            elif len(now_level) == 0:
                return 0  # 特殊情况：Transaction空队列
            else:
                return -1  # 未到达树根

        # 获取默克尔树根
        tree_level = traverse_leaves(transaction_list)
        while can_end_loop(tree_level) == -1:
            tree_level = traverse_one_level_up(tree_level)
        return can_end_loop(tree_level)

    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
    # The following is the mining section, where mine() merges mining. py
    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————

    def pickup_num_Transaction(self, num):
        """新块打包

        - 交易进入内存池等待打包
        - 下次挖矿时交易会被打包进区块
        """
        pickup_Transactions=[]   # Transaction[]
        for i in range(0,num):
            if i==len(self.mempool):
                break
                # 如果未达到块大小，则返回
            pickup_Transactions.append(self.mempool[i])
        return pickup_Transactions

    def del_num_Transcation(self, num):
        """在mempool中删除Transaction"""
        for i in range(0, num):
            if len(self.mempool)==0:
                break
            self.mempool.pop(0)

    def add_utxos(self, receiver_pub_key_hash, Txid, blocknumber, vout):
        """增添UTXO"""
        if receiver_pub_key_hash not in self.utxos.keys():    # 添加新客户
            self.utxos.update({receiver_pub_key_hash:[]})
        self.utxos[receiver_pub_key_hash].append([Txid, blocknumber, vout])

    def saveTx(self, _Tx):
        """save Tx in the CouchDB"""
        # print("saveTx")
        complete = True
        for i in range(len(_Tx.vouts)):
            info_dict = _Tx.vouts[i].serialize()
            key = "UTXO_txout" + _Tx.Txid + str(i)
            # print(key)
            try:
                self.database.create(key, info_dict)
            except ResourceConflict as e:
                print("save error")
                complete = False
        return complete

    def delTx(self, _Tx):
        """del Tx in the CouchDB"""
        ifsuccess = True
        # print("delTx")
        for i in range(len(_Tx.vouts)):
            info_dict = _Tx.vouts[i].serialize()
            key = "UTXO_txout" + _Tx.Txid + str(i)
            # print(key)
            doc = self.database.get(key)
            if not doc:
                continue
            try:
                self.database.delete(doc)
            except ResourceNotFound as e:
                print("del error")
                ifsuccess = False
        return ifsuccess

    def getTx(self, _Txid):
        """get Tx in the chain. search whole chain. Return blocknumber, vout = 0,0"""
        for i in range(0,len(self.chain)):
            for j in range(0,len(self.chain[i].data)):
                if self.chain[i].data[j].Txid == _Txid: #found
                    return i, j
        return 0, 0

    def mine(self):
        """挖矿获得奖励 独立的工作量证明算法实现 - 通过大量计算寻找符合条件的随机数（nonce）"""
        last_block = self.last_block()
        last_block_header_serialization = str(last_block.header.__dict__)  # 最后区块头的序列化
        difficulty_bits = last_block.header.difficulty
        target = 2 ** (256 - difficulty_bits)
        proof = None

        # 进行迭代，直到找到满足目标要求的nonce
        for nonce in range(self.MAX_NONCE):
            hash_result_iter_1 = hashlib.sha256((last_block_header_serialization + str(nonce)).encode()).hexdigest()
            hash_result_iter_2 = hashlib.sha256(hash_result_iter_1.encode()).hexdigest()  # 双重SHA-256哈希
            if int(hash_result_iter_2, 16) < target:
                proof = nonce
                break  # 挖矿成功

        _Tx=Transaction.create_coinbase_Tx(noneTokenid= self.NullTxid, vout_index = -1, pub_key=self.Nullpub_key, pub_key_hash='')
        # _Tx具有人类赋予的唯一 ID，否则仅仅通过公式计算会让每个 Coinbase Tx 具有相同的 ID
        block_size = len(self.mempool)  # TODO: 后期应该换成block_capable_size(系统规定或者用户声明)，因为实际上一个块不能装下整个mempool
        pick_length = block_size
        pickup_Transcation = [_Tx]
        append_Transcation = self.pickup_num_Transaction(pick_length)
        self.del_num_Transcation(pick_length)
        # pick up Transactions that is unused, _Tx一定包含在now Tx当中
        for _tmpTx in append_Transcation:
            pickup_Transcation.append(_tmpTx)

        for i in range(1,len(pickup_Transcation)):  # 忽略已使用的 _Tx
            _tmpTx = pickup_Transcation[i]
            Txid = _tmpTx.Txid
            blocknumber = last_block.header.index + 1
            vout = i
            owner_pub_key_hash = _tmpTx.vins[0].pub_key    # owner
            if owner_pub_key_hash not in self.utxos.keys():
                self.utxos.update({owner_pub_key_hash: []})
            self.utxos[owner_pub_key_hash].append([Txid, blocknumber,vout])  # 被utxo录入block的Tx才可以被用
            self.saveTx(_tmpTx)   # 当进入块时，CouchDB 中的记录增加

        new_block = Block(index=last_block.header.index + 1,
                          timestamp=time.time(),
                          prev_hash=last_block.hash,
                          difficulty=last_block.header.difficulty,
                          merkle_root=self.generate_merkle_root(pickup_Transcation),
                          nonce=proof,
                          data=pickup_Transcation)

        self.add_utxos(self.node_address, _Tx.Txid, new_block.header.index, 0)  # 切记记录未使用的 Tx：Coinbase
        self.saveTx(_Tx)
        # utxo记录Txs的信息，包括block NO. 和 Index
        # add utxo
        # 加入 {hash_pubkey: newTranscationId, block Id, vout_index in newTranscation}

        # 每隔 DIFFICULTY_ADJUST_BLOCK 个区块更新难度
        if new_block.header.index  % self.DIFFICULTY_ADJUST_BLOCK == 0:
            new_block.header.difficulty=self.new_difficulty(new_block.header.difficulty)
        self.chain.append(new_block)
        return new_block.header.index   # 返回块高度

    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
    # 更新挖矿难易程度
    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
    def last_block(self):
        """返回最后一个区块"""
        return self.chain[-1]

    def last_n_block(self, index):
        """返回最后 n 个区块"""
        return self.chain[-index]

    def new_difficulty(self, difficulty):
        """温和调整方案，可能需要多次调整才能让难度跟全网算力相适配。
        :param difficulty: 旧挖矿难度
        :return: 新的挖矿难度
        """
        actual_time_consumed = self.last_block().timestamp - self.last_n_block(self.DIFFICULTY_ADJUST_BLOCK).timestamp # 获取从上一次调整到这次调整的实际用时
        adjust_coefficient = self.DIFFICULTY_ADJUST_BLOCK * self.AVERAGE_MINING_TIME / actual_time_consumed
        if adjust_coefficient > 1:
            new_difficulty = difficulty + 1
        else:
            new_difficulty = difficulty - 1
        # 新难度 = 旧难度 × 预期时间 / 实际耗时
        # 保持平均3秒出块速度
        return new_difficulty

    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
    # 主要内容：资金交换（P2P 转账）
    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
    def print_nodeaddress(self):
        """打印节点地址（私钥）"""
        return self.node_address

    def get_Tx_total_value(self, thisTx):
        """获取Transaction的总金额"""
        tot_value = 0
        for i in range(0,len(thisTx.vouts)):
            tot_value = tot_value + thisTx.vouts[i].value
        return tot_value

    def transfer(self, payer_pub_key_hash, payer_priv_key, receiver_pub_key_hash, receiver_priv_key, receiver_pub_key, total_value):
        """转账交易"""
        # 通过接收方私人密钥签署发送方协议
        # 从付款人的公钥哈希值向收款人的公钥哈希值付款
        if not payer_pub_key_hash in self.utxos.keys():
            print("No such address found or no transcation having been recorded")
            return False

        # UTXO-based payment
        sum_value = 0
        pnt = 0
        record = []
        while sum_value < total_value and pnt < len(self.utxos[payer_pub_key_hash]):    # review deposit
            Txid, blocknumber, vout =  self.utxos[payer_pub_key_hash][pnt][0], self.utxos[payer_pub_key_hash][pnt][1], self.utxos[payer_pub_key_hash][pnt][2]
            for i in range(0, len(self.chain[blocknumber].data[vout].vouts)):
                self.chain[blocknumber].data[vout].vouts[i].pub_key_hash = receiver_pub_key_hash    # 支付公共密钥哈希值
                # FIXME：更改区块链实际上与区块链的设计相冲突，这里是临时性的，可以说管理者将其保留在内存中，而不是区块链中。
                # self.usedTxlist.append(Txid)
            sum_value = sum_value + self.get_Tx_total_value(self.chain[blocknumber].data[vout])
            record.append([Txid, blocknumber, vout])
            pnt = pnt + 1

        # 判断 if sum_value < total_value: rollback
        if sum_value < total_value:
            pnt = 0
            while pnt < len(record):
                Txid, blocknumber, vout = record[pnt]
                for i in range(0, len(self.chain[blocknumber].data[vout].vouts)):
                    self.chain[blocknumber].data[vout].vouts[i].pub_key_hash = ''
                    # FIXME：改变区块链实际上是与区块链设计理念相冲突的，这里是权宜之计
                self.usedTxlist.remove(self.chain[blocknumber].data[vout].Txid)
                pnt = pnt + 1
            return False
        elif sum_value >= total_value :
            # 创建新的 Tx，不添加进 utxos，而是将其放入 mempool，因为 utxos 只记录那些已被区块记录的内容
            newTx = Transaction([],[])
            surplus =  sum_value - total_value
            sum_value = 0
            for pnt in range(0,len(record)):
                Txid, blocknumber, vout  = record[pnt]
                print("Used Txid : ", Txid)
                self.utxos[payer_pub_key_hash].pop(0)   # 删除 utxos 中已使用的 Tx
                self.delTx(self.chain[blocknumber].data[vout])  # 删除 CouchDB 中已使用的 Tx
                thisTx_total_value = self.get_Tx_total_value(self.chain[blocknumber].data[vout])
                if sum_value + thisTx_total_value <= total_value:   # 检查是否有剩余
                    transfer_value = thisTx_total_value
                else:
                    transfer_value = total_value - sum_value
                sum_value = sum_value + thisTx_total_value
                newTx.vins.append(tx_input(Txid, vout, receiver_pub_key_hash))
                newTx.vouts.append(tx_output(transfer_value, ''))
            newTx.generate_Txid()
            newTx.sign(receiver_priv_key)
            self.mempool.append(newTx)
            print("New Txid unput: ", newTx.Txid)
            # Important: 在 mempool 中添加 Tx 时保存，不要将其添加到 utxos 中。只有在记录区块后，才能将 Tx 添加到 utxos 中。

            if surplus > 0:
                lastTxid = record[-1][0]
                lastvout = record[-1][2]
                newTx = Transaction([tx_input(lastTxid, lastvout, payer_pub_key_hash)], [tx_output(surplus, '')])   # 将余款退还付款人
                newTx.generate_Txid()
                newTx.sign(payer_priv_key)
                self.mempool.append(newTx)
        return True # 顺利转入

    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
    # 区块验证
    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————

    def prove_valid_chain(self, another_chain):
        return True
        # TODO: 待完善 验证链合法 要和签名等部分一起

    def prove_valid_block(self, another_block):
        return True
        # TODO: 待完善 验证链合法 要和签名等部分一起

    def reload_blockchain(self, aBlockchain):
        """重载区块链"""
        # TODO: 需要和存储一起做
        self.mempool = copy.deepcopy(aBlockchain.mempool)
        self.chain = copy.deepcopy(aBlockchain.chain)
        self.utxos = aBlockchain.utxos.deepcopy()

    def deal_with_fork(self, ablockchain):
        """处理区块分叉"""
        # 采用最大长度链
        if self.prove_valid_chain(ablockchain.chain) and len(ablockchain.chain)>len(self.chain):
            self.reload_blockchain(ablockchain) # 重载区块链

    def get_Tx_info(self, Txid):
        blocknumber, vout = self.getTx(Txid)

###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
# 钱包功能
###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————

class Account:
    def __init__(self, priv_key='', pub_key='', pub_key_hash=''):
        if len(priv_key)==0 or len(pub_key)==0:
            from ecdsa import SigningKey, NIST384p
            sk = SigningKey.generate(curve=NIST384p)
            vk = sk.verifying_key
            self.priv_key = sk.to_string().hex()
            self.pub_key = vk.to_string().hex()
        else :
            self.priv_key=priv_key
            self.pub_key=pub_key
        self.pub_key_hash = Transaction.calculate_public_key_hash(self.pub_key)

def sum_acc_value(bc, pub_key_hash):
    sum = 0
    print("this person's pub_key_hash: ", pub_key_hash)
    if pub_key_hash in bc.utxos.keys():
        lst = bc.utxos[pub_key_hash]
        for info in lst:
            Txid = info[0]
            blocknumber = info[1]
            vout = info[2]
            if Txid not in bc.usedTxlist:
                print("sum: ", Txid, blocknumber, vout)
                sum = sum + bc.get_Tx_total_value(bc.chain[blocknumber].data[vout])
    return sum


if __name__ == '__main__':

    Acc = [Account() for i in range(6)]

    Master=Acc[0]

    a=Blockchain(public_key_hex=Master.pub_key, private_key_hex=Master.priv_key)
    a.genesis_block()
    print(a.chain[-1].header.index)
    print(a.chain[-1].header.timestamp)
    print(a.chain[-1].header.prev_hash)
    print(a.chain[-1].header.difficulty)
    print(a.chain[-1].header.nonce)
    print(a.chain[-1].header.merkle_root)


    addr=a.print_nodeaddress()
    print("Master / Acc[0]: ", Transaction.calculate_public_key_hash(Master.pub_key))
    for i in range(len(Acc)):
        print("Acc[{}]: ".format(i), Acc[i].pub_key_hash)

    # =====================================# =====================================# =====================================
    # start doing
    print("before Transfer: mine 1")
    a.mine()
    print()
    print("Transfer 1:")
    a.transfer(payer_pub_key_hash=Master.pub_key_hash,
               payer_priv_key=Master.priv_key,
               receiver_pub_key_hash=Acc[1].pub_key_hash,
               receiver_priv_key=Acc[1].priv_key,
               receiver_pub_key=Acc[1].pub_key,
               total_value=10)
    print("utxos:")
    print(a.utxos)

    while True:
        cmd = input('请输入一个命令 continue /: ')
        if cmd == "view":
            idx = input('请输入查看余额的账户编号: ')
            try:
                idx = int(idx)
                assert idx < 6
                print(sum_acc_value(a, Acc[idx].pub_key_hash))
            except:
                print("something go wrong ")
                continue
            continue
        elif cmd == "mine":
            print("Mint round: ", a.mine())
            continue
        elif cmd == "":
            continue
        elif cmd == "check":
            continue

        while True:
            P1 = input('请输入一个发起者编号 <6 0是master ')
            R1 = input('请输入一个接收者编号 <6 0是master ')
            if P1 == "utxo":
                print(a.utxos)
                continue
            if P1 == "mem":
                try:
                    print(a.mempool[int(R1)].serialize())
                except:
                    continue
                continue
            if P1 == "quit":
                break
            try:
                P1=int(P1)
                R1=int(R1)
            except:
                print("Wrong input account. Retry.")
                print()
                continue
            if P1 >=6 or R1>=6:
                print("Wrong input account. Retry.")
                print()
                continue
            V1 = input('请输入转账金额 ')

            try:
                V1=int(V1)
                print("Transfer success: ",
                    a.transfer(payer_pub_key_hash=Acc[P1].pub_key_hash,
                           payer_priv_key=Acc[P1].priv_key,
                           receiver_pub_key_hash=Acc[R1].pub_key_hash,
                           receiver_priv_key=Acc[R1].priv_key,
                           receiver_pub_key=Acc[R1].pub_key,
                           total_value=V1)
                )
            except:
                print("Wrong input account. Retry.")
                print()
                continue

