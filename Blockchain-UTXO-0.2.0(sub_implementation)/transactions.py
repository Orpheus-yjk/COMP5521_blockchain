# -*- coding: utf-8 -*-

"""交易：实现支付到公钥哈希（P2PKH）交易并验证交易。a) 实现支付到公钥哈希（P2PKH）交易。b) 使用非对称加密创建数字签名并验证交易。

transactions.py定义了交易相关的类，如tx_input、tx_output和Transaction。
交易输入引用之前的交易输出，交易输出包含金额和公钥哈希。Transaction类生成交易ID，并处理Coinbase交易（矿工奖励）。

"""

__author__ = 'YJK developer'
__date__ = '2025-04'

import sys
import hashlib
import logging
from typing import List, Tuple

from math_util import VerifyHashAndSignatureUtils
from transaction_script import CoinbaseScript, StandardTransactionScript

__all__ = ['txInput', 'txOutput', 'Transaction']

# txInput 填充常量
INPUT_TXID_PLACEHOLDER = 'f4184fc596403b9d638783cf57adfe4c75c605f6356fbc91338530e9831e9e16'  # 一个符合比特币规范的交易id
INPUT_REFER_ID_PLACEHOLDER = 0xFFFFFFFF,  # Coinbase 的 refer id 也固定为 0xFFFFFFFF
INPUT_PUBKEY_PLACEHOLDER = b'03176f9ceaefc86f99e6c9f486525785083eb47ea94870c592bcf475a2303d20f8'
INPUT_SIGNATURE_PLACEHOLDER = b'1143f5f4f38b526d9202a14dfc1db54cf9270d5762d88d13d704e5bdad4262b10caf7a44d344e8b041bcd753b4e7cbca0fb6d1dc93bcb2440fa376785b8c972f'
# 交易的签名是由资金的发送方（即输入资金的拥有者）负责的。这是为了证明发送方有权使用该笔资金，并授权将其转移给接收方。
# 该签名的原始信息是：b"Demo trading data"，通过SignMessageUtils类加密

# txOutput 填充常量
OUTPUT_VALUE_PLACEHOLDER = 0
OUTPUT_PUBKEYHASH_PLACEHOLDER = "17LVrmuCzzibuQUJ265CUdVk6h6inrTJKV"  # 一个符合比特币规范的地址

# Transaction 填充常量
TRANSACTION_TXID_PLACEHOLDER = INPUT_TXID_PLACEHOLDER

class txInput:
    """资金来源凭证：资金的发送方（引用检验之前的交易）

    Attributes:
        txid(str): 引用的交易ID
        referid(int): 引用的交易内的索引（tx来源）
        pubkey(bytes): 签名方（资金的发送方）公钥
        signature: 签名方（资金的发送方）对交易的签名

    Methods:
        serialize(): 序列化
        deserialize(dict): 反序列化
    """

    def __init__(self, txid: str, referid: int, pubkey: bytes, signature: bytes):
        self.txid = txid
        self.referid = referid
        self.pubkey = pubkey
        if len(signature)==0:
            raise ValueError('输入交易签名为空！')  # 简单判断
        self.signature = signature

    def serialize(self):
        """序列化"""
        return self.__dict__

    @classmethod
    def deserialize(cls, data):
        """反序列化"""
        txid = data.get('txid', INPUT_TXID_PLACEHOLDER)
        referid = data.get('referid', INPUT_REFER_ID_PLACEHOLDER)
        pubkey = data.get('pubkey', INPUT_PUBKEY_PLACEHOLDER)
        signature = data.get('signature', INPUT_SIGNATURE_PLACEHOLDER)
        tx_input = cls(txid, referid, pubkey, signature)
        return tx_input

class txOutput:
    """资金去向记录（包含金额和收款方）

    Attributes:
        value: 金额
        pubkey_hash: 接收方公钥哈希（本设计中为比特币地址）

    Methods:
        serialize(): 序列化
        deserialize(dict): 反序列化
    """
    def __init__(self, value: int, pubkey_hash: str):
        self.value = value  # 可代表实际金额 / 虚拟token
        if len(pubkey_hash)==0:
            raise ValueError('交易输出的公钥哈希为空！')  # 这里不用通过VerifyHashAndSignatureUtils类判断pubkey_hash是否合规，而是在Transaction中做
        self.pubkey_hash = pubkey_hash

    def serialize(self):
        """序列化"""
        return self.__dict__

    @classmethod
    def deserialize(cls, data):
        """反序列化"""
        value = data.get('value', OUTPUT_VALUE_PLACEHOLDER)
        pubkey_hash = data.get('pubkey_hash', OUTPUT_PUBKEYHASH_PLACEHOLDER)
        return cls(value, pubkey_hash)

class Transaction(CoinbaseScript, StandardTransactionScript, VerifyHashAndSignatureUtils):
    """实现数字货币转账功能。tx是一条资金流， Tx （== txs）是一次完整的P2P交易。

    每次交易收集payer的所有可用Transaction信息，并将其中需要花费的部分汇总并生成一条新的Tx，最后给receiver。
    使用到的类库：CoinbaseScript, StandardTransactionScript, VerifyHashAndSignatureUtils（含GenerateKeysUtils, SignMessageUtils）。

    Attributes:
        vins: 交易输入列表。
            作用：存储该交易的所有输入(资金来源)；每个输入引用之前某个交易的输出(UTXO)
            特点：普通交易至少有一个输入，Coinbase交易(矿工奖励)有特殊输入(txid为空)
        vouts: 交易输出列表。
            作用：存储该交易的所有输出(资金去向)；每个输出指定接收方和转账金额
            特点：一个交易可以有多个输出(如找零)；输出成为UTXO，直到被后续交易引用
        Txid： 交易ID。
            作用：交易的唯一标识符，用于在区块链中引用该交易
            生成方式：通过generate_Txid()方法生成，挖矿区块id不能用generate_Txid()方法生成而要比如，随机赋值
            特点：具有唯一性，不可篡改(任何交易内容变化都会改变Txid)，用于构建Merkle树
        nlockTime：如果未设置（默认为0），交易会立即生效；否则，交易必须等到指定时间或区块高度后才能被打包。
        sum_value：交易总金额
            计算方式：累加所有输出(vouts)的value值
        fee：支付的费率
        TODO： 完善费率

    Methods:
        serialize(): 序列化
        deserialize(dict): 反序列化

        get_memory_size(): 【已弃用】返回对象在内存中的占用大小（单位：字节，近似值）
        calculate_raw_size(): 返回Transaction的实际大小
        calculate_fee(int): 根据费率计算手续费
        update_fee(int): 更新Transaction的fee

        generate_Txid(bool, *arg) -> Tuple[str, dict]: 生成Coinbase和普通Transaction的TXID以及Script
        generate_self_script() -> dict: 返回自身的script

        create_coinbase_Tx(int, str, int): 创建coinbase交易(矿工奖励)
        create_normal_tx(List[txInput],List[txOutput], int): 创建普通的单笔交易

        payer_sign(private_key: bytes, receiver_address: str, Tx_data: dict, txid: str, referid: int): 签名函数  TODO：格式检查
        verify_transaction(locking_script: str, public_key: bytes, signature: bytes, Tx_data:dict): 验证签名
    """
    def __init__(self, vins: List[txInput], vouts: List[txOutput], nlockTime=0):  # 默认创建时交易锁定
        """
        :param vins: array of class txInput
        :param vouts: array of class txOutput
        :param nlockTime
        """
        self.vins = vins
        self.vouts = vouts
        self.nlockTime = nlockTime  # 如果未设置（默认为0），交易会立即生效；否则，交易必须等到指定时间或区块高度后才能被打包。
        self.sum_value = 0
        for vout in vouts:
            self.sum_value += vout.value

        self.Txid = self.generate_Txid(False, vins, vouts, nlockTime)  # 默认为普通Transaction，如果Coinbase后续可强制修改
        # 整个Transaction是没有签名的，只有tx有scriptSig(在交易由payer发出并且进入mempool锁定的时候，用payer的签名)
        self.fee = 0

    def serialize(self):
        """序列化"""
        return {
            'Txid': self.Txid,
            'nlockTime': self.nlockTime,
            # 'sum_value': self.sum_value,
            'serialized_vins': [vin.serialize() for vin in self.vins],  # vin序列化 -> str
            'serialized_vouts': [vout.serialize() for vout in self.vouts],  # vout序列化 -> str
            'fee': self.fee
        }

    @classmethod
    def deserialize(cls, data):
        """反序列化"""
        Txid = data.get('Txid', TRANSACTION_TXID_PLACEHOLDER)
        nlockTime = data.get('nlockTime', 0)
        fee = data.get('fee', 0)
        # sum_value = data.get('sum_value', 0)
        serialized_vins_data = data.get('serialized_vins', [])
        serialized_vouts_data = data.get('serialized_vouts', [])
        vins = []
        vouts = []
        for vin_data in serialized_vins_data:
            vins.append(txInput.deserialize(vin_data))
        for vout_data in serialized_vouts_data:
            vouts.append(txOutput.deserialize(vout_data))

        Tx = cls(vins, vouts, nlockTime)
        return Tx

    def get_memory_size(self):
        """【弃用】旧方法（不准确），仅作兼容保留
        返回对象在内存中的占用大小（单位：字节，近似值）"""
        return sys.getsizeof(self) + sum(
            sys.getsizeof(inp) for inp in self.vins
        ) + sum(
            sys.getsizeof(out) for out in self.vouts
        )

    def calculate_raw_size(self) -> int:  # 基础内存计算（非 SegWit 交易）
        """计算交易原始字节大小（单位：字节）"""
        # 序列化交易数据
        serialized_tx = StandardTransactionScript.serialize_Tx(self.serialize())
        return len(serialized_tx)

    def calculate_fee(self, fee_rate: float) -> int:
        """根据费率计算手续费（单位：satoshi）"""
        return int(self.calculate_raw_size() * fee_rate)

    def update_fee(self, fee_rate):
        """更新Transaction的fee"""
        self.fee = self.calculate_fee(fee_rate=fee_rate)

    @staticmethod
    def generate_Txid(is_coinbase, *args) -> Tuple[str, dict]:
        """生成Coinbase和普通Transaction的TXID以及Script"""
        if is_coinbase:
            block_height = args[0]
            miner_address = args[1]
            mining_reward = args[2]
            Txid, Tx_data = CoinbaseScript.generate_coinbase_Txid(block_height, miner_address, mining_reward)
        else:
            vins = args[0]
            vouts = args[1]
            nlockTime = args[2]
            input_txids = []
            input_referids = []
            input_scripts = []
            output_values = []
            output_addresses = []
            for vin, vout in zip(vins, vouts):
                input_txids.append(vin.txid)
                input_referids.append(vin.referid)

                # 比特币标准解锁脚本 P2PKH: unlock_script = <sig> <pubKey>
                this_unlockscript = ' '.join([vin.signature, vin.pubkey.decode('utf8')])
                input_scripts.append(this_unlockscript)

                output_values.append(vout.value)
                output_addresses.append(vout.pubkey_hash)

            Txid, Tx_data = StandardTransactionScript.generate_normal_Txid(
                input_txids, input_referids, input_scripts, output_values, output_addresses, nlockTime
            )
        return Txid, Tx_data

    def generate_self_script(self) -> dict:
        """返回自身数据结构的script"""
        _, Tx_script = Transaction.generate_Txid(False, self.vins, self.vouts, self.nlockTime)
        return Tx_script

    @classmethod  # 使用cls在函数中独自创建一个另一个Tranaction类
    def create_normal_tx(cls, vins: List[txInput], vouts: List[txOutput], nlockTime=0):
        """创建普通的单笔交易。"""
        Tx = cls(vins, vouts, nlockTime)
        Tx.Txid, _ = Transaction.generate_Txid(False, vins, vouts, nlockTime)
        Tx.update_fee(fee_rate=20)
        return Tx

    @classmethod
    def create_coinbase_Tx(cls, block_height, miner_address, mining_reward):
        """创建Coinbase交易"""
        # Coinbase的Txid要进行特殊修改，防止因为不包含随机数导致错误
        Txid, Tx_script = CoinbaseScript.generate_coinbase_Txid(block_height, miner_address, mining_reward)
        # 解析
        # FIXME: 容易出错
        tx_input = txInput(Txid, Tx_script["vins"][0]["referid"], CoinbaseScript.COINBASE_PUBLKEY, Tx_script["vins"][0]["scriptSig"])  # 签名人：超级节点
        tx_output = txOutput(mining_reward, Tx_script["vouts"][0]["script_pubkey_hash"])
        # 搭建
        Tx = cls([tx_input] , [tx_output], 0)  # FIXME: nlockTime应该设计为当前区块高度+100
        Tx.Txid = Txid
        return Tx

    # 签署并验证
    def get_signature_message(self):
        """自构造签名材料 - message"""

        Tx_data = StandardTransactionScript.generate_Tx_script(
            inputs=self.vins,
            outputs=self.vouts,
            nlockTime=self.nlockTime
        )
        serialized_Tx = StandardTransactionScript.serialize_Tx(Tx_data)
        Tx_hash = hashlib.sha256(hashlib.sha256(serialized_Tx).digest()).digest()
        return Tx_hash

    @staticmethod
    def payer_sign(private_key: bytes, receiver_address: str, Tx_data: dict, txid: str, referid: int) -> Tuple[txInput, txOutput, bytes]:
        """资金发送者签名得到signature，并且生成资金流返回"""
        # 处理错误
        if "version" not in Tx_data.keys() or "locktime" not in Tx_data.keys() or "vins" not in Tx_data.keys() or "vouts" not in Tx_data.keys():
            raise ValueError("输入的交易数据 Tx_data 格式不对！")
        elif len(Tx_data)>4:
            logging.warning("输入的交易数据 Tx_data 包含冗余键值。")
        vins = Tx_data["vins"]
        if referid > len(vins)-1 or referid < 0:
            raise ValueError("引用的资金流索引溢出！")
        elif txid != vins[referid]["txid"]:
            raise ValueError("引用的资金流索引与ID不匹配！无法引用")

        # 此处无需验证，直接签名（对整个Transaction签名是合理的，因为在区块链网络上每一笔消费都是可见的）
        # 1. 序列化交易数据
        serialized_Tx = StandardTransactionScript.serialize_Tx(Tx_data)

        # 2. 计算交易哈希（双重SHA256）
        Tx_hash = hashlib.sha256(hashlib.sha256(serialized_Tx).digest()).digest()

        # 3. 生成SignMessageUtils类方法的签名
        Sig = VerifyHashAndSignatureUtils.sign_transaction(private_key=private_key, message=Tx_hash)

        tx_input = txInput(
            txid=txid, referid=referid, pubkey=VerifyHashAndSignatureUtils.private_key_to_public_key(private_key), signature=Sig
        )
        vouts = Tx_data["vouts"]
        tx_output = txOutput(
            value=vouts[referid]["value"], pubkey_hash=receiver_address
        )
        return tx_input, tx_output, Sig

    @staticmethod
    def verify_transaction(locking_script: str, public_key: bytes, signature: bytes, Tx_data:dict):
        """验证签名"""
        # 1. 检查公钥哈希
        unlocking_script = VerifyHashAndSignatureUtils.unlock_p2pkh_script(locking_script, public_key, signature)
        if unlocking_script == "Unlock Script Fail!": return False

        # 2. 根据Transaction data重新构造message，验证签名
        serialized_Tx = StandardTransactionScript.serialize_Tx(Tx_data)
        Tx_hash = hashlib.sha256(hashlib.sha256(serialized_Tx).digest()).digest()
        if VerifyHashAndSignatureUtils.verify_signature(public_key=public_key, signature=signature, message=Tx_hash):
            return True
        else: return False
