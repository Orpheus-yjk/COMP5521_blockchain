# -*- coding: utf-8 -*-

"""交易：实现支付到公钥哈希（P2PKH）交易并验证交易。a) 实现支付到公钥哈希（P2PKH）交易。b) 使用非对称加密创建数字签名并验证交易。

transactions.py定义了交易相关的类，如tx_input、tx_output和Transaction。
交易输入引用之前的交易输出，交易输出包含金额和公钥哈希。Transaction类生成交易ID，并处理Coinbase交易（矿工奖励）。

"""

__author__ = 'YJK'
__date__ = '2023-12-6'

import hashlib
import time

from ecdsa import SigningKey, NIST384p, VerifyingKey
subsidy = 500  # 开采一个区块的奖励

class tx_input:
    """资金来源凭证（引用之前的交易）

    Attributes:
        txid: 引用的交易ID
        vout: 输出索引
        pubkey: 公钥
        signature: 签名

    Methods:
        serialize(): 序列化
    """

    def __init__(self, txid, vout_to, pub_key):
        self.txid = txid
        self.vout = vout_to
        self.pubkey = pub_key
        self.signature = ''

    def serialize(self):
        """序列化"""
        return self.__dict__

    @classmethod
    def deserialize(cls, data):
        txid = data.get('Txid', '')
        vout = data.get('vout', 0)
        pub_key = data.get('pub_key', '')
        signature = data.get('signature', '')
        tx_input = cls(txid, vout, pub_key)
        tx_input.signature = signature
        return tx_input

class tx_output:
    """资金去向记录（包含金额和收款方）

    Attributes:
        value: 金额
        pub_key_hash: 接收方公钥哈希

    Methods:
        serialize(): 序列化
    """

    def __init__(self, value, pub_key_hash=''):
        self.value = value  # 可代表实际money / amount / 虚拟token
        self.pub_key_hash = pub_key_hash

    def serialize(self):
        """序列化"""
        return self.__dict__

    @classmethod
    def deserialize(cls, data):
        value = data.get('value', 0)
        pub_key_hash = data.get('pub_key_hash', 0)
        return cls(value, pub_key_hash)

class Transaction:
    """实现数字货币转账功能。

    tx是一条资金流， Tx （== txs）是一次完整的P2P交易。
    每次交易收集payer的所有可用Transaction信息，并将其中需要花费的部分汇总并生成一条新的Tx，最后给receiver。

    Attributes:
        vins: 交易输入列表。
            作用：
                存储该交易的所有输入(资金来源)
                每个输入引用之前某个交易的输出(UTXO)
            特点：
                普通交易至少有一个输入，Coinbase交易(矿工奖励)有特殊输入(txid为空)
        vouts: 交易输出列表。
            作用：
                存储该交易的所有输出(资金去向)
                每个输出指定接收方和转账金额
            特点：
                一个交易可以有多个输出(如找零)
                输出成为UTXO，直到被后续交易引用
        Txid： 交易ID。
            作用：
                交易的唯一标识符，用于在区块链中引用该交易
            生成方式：
                通过generate_Txid()方法生成，挖矿区块id不能用generate_Txid()方法生成而要比如，随机赋值
            特点：
                具有唯一性，不可篡改(任何交易内容变化都会改变Txid)，用于构建Merkle树
        sum_value：交易总金额
            计算方式：
                累加所有输出(vouts)的value值

    Methods:
        generate_Txid(): 生成交易ID(SHA256)
        is_coinbase(): 判断是否为coinbase交易
        create_coinbase_Tx(): 创建coinbase交易(矿工奖励)
        create_one_tx(): 创建普通的单笔交易

    """
    def __init__(self, vins, vouts):
        """
        :param vins: array of class tx_input
        :param vouts: array of class tx_output
        """
        self.vins = vins
        self.vouts = vouts
        self.Txid= self.generate_Txid()  # txid is str() make by hashlib.sha256

    def serialize(self):
        return {
            'txid': self.Txid,
            'vins': [vin.serialize() for vin in self.vins],
            'vouts': [vout.serialize() for vout in self.vouts]
        }

    @classmethod
    def deserialize(cls, data):
        txid = data.get('txid', '')
        vins_data = data.get('vins', [])
        vouts_data = data.get('vouts', [])
        vins = []
        vouts = []
        for vin_data in vins_data:
            vins.append(tx_input.deserialize(vin_data))

        for vout_data in vouts_data:
            vouts.append(tx_output.deserialize(vout_data))
        tx = cls(vins, vouts)
        tx.txid = txid
        return tx

    def generate_Txid(self):
        vin_list = [str(vin.serialize()) for vin in self.vins]
        vouts_list = [str(vout.serialize()) for vout in self.vouts]

        concat_list = vin_list
        concat_list.extend(vouts_list)  ##str
        concat_list = ''.join(concat_list)

        hash = hashlib.sha256(concat_list.encode()).hexdigest()  # 生成一个基础Txid。也可以用其他方式生成Txid，这是经典方法
        # 还包括 random_number，当Txid账面内容相同时防止提供相同的 Txid
        # TODO：可以添加业务前缀后缀
        return hashlib.sha256((hash + str(time.time())).encode()).hexdigest()

    def is_coinbase(self, _Tx):
        # 判断：是否为coinbase（挖矿奖励区块）
        return len(_Tx.vins) == 1 and len(_Tx.vins[0].txid) == 0  # 顺带说明：此时 _Tx.vins[0].vout == block miner

    @classmethod
    # 使用cls在函数中独自创建一个另一个Tranaction类
    def create_coinbase_Tx(cls, noneTokenid, vout_index=-1, pub_key='', pub_key_hash=''):
        _txinput = tx_input(noneTokenid, vout_index, pub_key)
        _txoutput = tx_output(subsidy, pub_key_hash)
        Tx = cls([_txinput] , [_txoutput])
        Tx.Txid = hashlib.sha256((str(time.time())+Tx.Txid).encode("utf8")).hexdigest()
        return Tx

    def used(self):
        self.ifused = False

    def unused(self):
        self.ifused = False

    @classmethod
    def calculate_public_key_hash(cls, public_key):    # 所有节点都应使用相同的哈希值 func()
        return hashlib.sha256(hashlib.sha256(public_key.encode("utf8")).hexdigest().encode("utf8")).hexdigest()

    def Transaction_self_copy_leaveout_signature(self):
        new_vins = []
        new_vouts = []
        for vin in self.vins:
            new_vins.append(tx_input(vin.Txid, vin.vout, ''))

        for vout in self.vouts:
            new_vouts.append(tx_output(vout.value, vout.pub_key_hash))

        new_Transaction = Transaction(new_vins, new_vouts)
        return new_Transaction

    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
    # sign and verify as below
    ###————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————————
    def is_hexadecimal(self, s):
        try:
            int(s, 16)
            return True
        except ValueError:
            return False

    def sign(self, private_key):
        if not self.is_hexadecimal(private_key) :
            print("Invalid private key")
            return
        Tx_copy = self.Transaction_self_copy_leaveout_signature()
        for idx, vin in enumerate(Tx_copy.vins):
            Tx_copy.vins[idx].signature = None
            Tx_copy.vins[idx].pub_key = str(idx)  # prev_tx.vouts[vin.vout].pub_key_hash
            Tx_copy.Txid = Tx_copy.generate_Txid()
            Tx_copy.vins[idx].pub_key = None
            sk = SigningKey.from_string(bytes.fromhex(private_key), NIST384p)  # private_key: hex string(see Intuitively)   sk: SigningKey
            self.vins[idx].signature = sk.sign(Tx_copy.Txid.encode("utf8"))  # binascii.hexlify(sign).decode()

    def verify(self, private_key, public_key):
        if not self.is_hexadecimal(private_key) :
            print("Invalid %d bytes private key" % (len(private_key)))
            return False
        if not self.is_hexadecimal(public_key) :
            print("Invalid %d bytes public key" % (len(public_key)))
            return False

        Tx_copy = self.Transaction_self_copy_leaveout_signature()

        for idx, vin in enumerate(self.vins):
            Tx_copy.vins[idx].signature = None
            Tx_copy.vins[idx].pub_key = str(idx)
            Tx_copy.Txid=Tx_copy.generate_Txid()
            Tx_copy.vins[idx].pub_key = None
            # sk = SigningKey.from_string(bytes.fromhex(private_key), NIST384p)
            # check_signature = sk.sign(Tx_copy.Txid.encode("utf8"))
            vk = VerifyingKey.from_string(bytes.fromhex(public_key), NIST384p)
            # if self.vins[idx].signature.hex() != check_signature.hex():return False
            # 用同样私钥生成的签名，化成字符串居然可以不同。 同样， 私钥唯一，但是字符串表示也不唯一。
            try:
                vk.verify(self.vins[idx].signature, Tx_copy.Txid.encode("utf8"))  # 统一编码格式 utf-8
            except:
                return False
        return True  # 顺利验证
