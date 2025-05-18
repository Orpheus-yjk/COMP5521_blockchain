"""比特币交易脚本生成与交易序列化工具库

该模块提供以下核心功能：
1. Coinbase 交易生成（矿工奖励）
2. 普通交易生成（UTXO 消费）
3. 交易数据的序列化（script）与 TXID 计算

主要类：
- TransactionScript: 基础交易结构构建工具
- CoinbaseScript: 专用于生成符合规范的 Coinbase交易的类
- StandardTransactionScript: 普通交易生成器类

示例用法：
    >>> # 生成 Coinbase 交易
    >>> Txid_1, Tx_data_1 = CoinbaseScript.generate_coinbase_Txid(
    ...     block_height=840000,
    ...     miner_address="1A1zP...",
    ...     mining_reward=625000000
    ... )
    >>> # 生成普通交易
    >>> Txid_2, Tx_data_2 = StandardTransactionScript.generate_normal_Txid(
    ...     input_txids=["a1075d..."],
    ...     input_scripts=["473044..."],
    ...     output_addresses=["1BvBMSE..."]
    ... )

注意事项：
1. 假设所有金额单位均为 satoshi (1 BTC = 100,000,000 satoshi)
2. 假设Coinbase 交易需等待 100 个区块确认后才能花费
3. 普通交易的 input_scripts 需包含有效的签名和公钥

参考：
- Bitcoin Developer Guide: https://developer.bitcoin.org/devguide/transactions.html
- BIP34: https://github.com/bitcoin/bips/blob/master/bip-0034.mediawiki
"""

__author__ = 'YJK developer'
__date__ = '2025-04'

import hashlib
import random
import struct
from typing import Tuple

__all__ = ['TransactionScript', 'CoinbaseScript', 'StandardTransactionScript']

# 拟一个超级节点的公钥来表征发薪人/系统
SUPERNODE_PRIVKEY = b"9a50346681853432d90e90592938750164ceaec382a8a3473da9e5a1e21d0e5d"  # 无用处，仅供验证
SUPERNODE_PUBLKEY = b"0265abc03fbdc82e4e3312cba161f92034533fe3c11c5da310021ed3d738c57da4"
SUPERNODE_ADDRESS = "1HGUt8BThQAjLtmqKAaRF4cHt5ia22HKsp"
SUPERNODE_DEMO_SIG = b"bd2c37105f141c3bc95911a7e0d40f39f0351dc1f43562c6be014bcaef483e28" \
                     b"84af314547c7bb294beac2dbf35cb7768e0ed71b71a7339422330a7cb309c520"


class TransactionScript:
    """交易序列化辅助工具"""
    VERSION = 1

    @staticmethod
    def generate_input_script(txid, referid, scriptSig, sequence):
        """构建输入流script"""
        return [{
            "txid": txid,
            "referid": referid,
            "scriptSig": scriptSig,
            "sequence": sequence
        }]

    @staticmethod
    def generate_output_script(mining_reward: int, miner_address: str):
        """构建输出流script"""
        return [{
            "value": mining_reward,
            "script_pubkey_hash": miner_address
        }]

    @staticmethod
    def generate_Tx_script(inputs, outputs, nlockTime=0):
        """构建Transaction Script"""
        Tx_script = {
            "version": TransactionScript.VERSION,
            "locktime": nlockTime,
            "vins": inputs,
            "vouts": outputs
        }
        return Tx_script

    @staticmethod
    def serialize_Tx(Tx_data: dict) -> bytes:
        """简化版的交易序列化"""

        # 版本号 (4字节小端)
        version = struct.pack("<I", Tx_data["version"])
        # 输入计数 (1字节)
        vin_count = bytes([1])
        # 输入数据
        txid = bytes.fromhex(Tx_data["vins"][0]["txid"])[::-1]  # 反转字节序
        referid = struct.pack("<I", Tx_data["vins"][0]["referid"])
        scriptSig = bytes.fromhex(Tx_data["vins"][0]["scriptSig"])
        scriptSig_len = bytes([len(scriptSig)])
        sequence = struct.pack("<I", Tx_data["vins"][0]["sequence"])
        # 输出计数 (1字节)
        vout_count = bytes([len(Tx_data["vouts"])])
        # 输出数据
        output_data = b""
        for out in Tx_data["vouts"]:
            value = struct.pack("<Q", out["value"])
            # script_pubkey_hash = bytes.fromhex(out["script_pubkey"]) 这是P2PK的写法。本设计采用P2PKH
            script_pubkey_hash = out["script_pubkey_hash"].encode('utf8')
            script_len = bytes([len(script_pubkey_hash)])
            output_data += value + script_len + script_pubkey_hash
        # 锁时间 (4字节小端)
        locktime = struct.pack("<I", Tx_data["locktime"])

        return version + vin_count + txid + referid + scriptSig_len + scriptSig + sequence + vout_count + output_data + locktime


class CoinbaseScript(TransactionScript):
    """用于随机生成符合比特币规范的 Coinbase 交易 TXID"""
    COINBASE_PUBLKEY = b"0265abc03fbdc82e4e3312cba161f92034533fe3c11c5da310021ed3d738c57da4"

    @staticmethod
    def generate_coinbase_Txid(block_height: int, miner_address: str, mining_reward: int) -> Tuple[str, dict]:
        """
        生成随机的符合规范的 Coinbase 交易 TXID
        返回: (Txid_hex, Tx_script_dict)
        """
        # 1. 构造 Coinbase 输入 (唯一输入，无前序交易)
        coinbase_script = CoinbaseScript.generate_coinbase_script(block_height)

        # 2. 构造输入，输出（矿工奖励）
        inputs = TransactionScript.generate_input_script(
            txid="0000000000000000000000000000000000000000000000000000000000000000",
            referid=0xFFFFFFFF,  # Coinbase 的 vout 固定为 0xFFFFFFFF
            scriptSig=coinbase_script.hex(),
            sequence=0xFFFFFFFF
        )
        outputs = TransactionScript.generate_output_script(
            mining_reward=mining_reward,
            miner_address=miner_address
        )

        # 3. 随机生成交易数据（模拟真实结构）
        Tx_script = TransactionScript.generate_Tx_script(inputs, outputs, block_height+1)  # FIXME：一般第三个参数大于block_height，表示解锁时间

        # 4. 序列化交易数据（简化版，实际需按比特币协议序列化规则）
        serialized_Tx = TransactionScript.serialize_Tx(Tx_script)

        # 5. 计算 TXID (双重SHA-256)
        Txid = hashlib.sha256(hashlib.sha256(serialized_Tx).digest()).digest()[::-1].hex()

        return Txid, Tx_script

    # ----------- 辅助函数 -----------
    @staticmethod
    def generate_coinbase_script(block_height: int) -> bytes:
        """生成随机的 Coinbase 脚本（包含区块高度和随机数据）"""
        # 区块高度按 BIP34 编码
        height_bytes = bytes([block_height & 0xff])
        # 随机数据（模拟矿池标签或 ExtraNonce）
        random_data = bytes([random.randint(0, 255) for _ in range(8)])
        return height_bytes + random_data

    @staticmethod
    def is_coinbase(Tx_script):
        """判断是否为coinbase（挖矿奖励区块）"""
        if len(Tx_script["vins"]) > 1 or len(Tx_script["vouts"]) > 1:
            return False
        input = Tx_script["vins"][0]
        if input["referid"] != 0xFFFFFFFF or input["sequence"] != 0xFFFFFFFF:
            return False
        return True


class StandardTransactionScript(TransactionScript):
    """普通交易生成器（非Coinbase）"""

    @staticmethod
    def generate_normal_Txid(
        input_txids: list[str],
        input_referids: list[int],
        input_scripts: list[str],
        output_values: list[int],
        output_addresses: list[str],
        nlockTime: int = 0
    ) -> Tuple[str, dict]:
        """
        生成普通交易的 TXID 和交易数据

        Args:
            input_txids: 输入交易的TXID列表（引用UTXO）
            input_referids: 对应输入的vout索引列表
            input_scripts: 输入解锁脚本（签名+公钥）的十六进制列表
            output_addresses: 输出地址列表
            output_values: 对应输出的金额列表（单位：satoshi）
            nlockTime: 锁定时间（默认0表示立即生效）

        Returns:
            Tuple[str, dict]: (TXID_hex, 交易数据字典)

        Raises:
            ValueError: 如果输入输出数量不匹配或参数非法
        """
        # 1. 校验参数
        if len(input_txids) != len(input_referids) or len(input_txids) != len(input_scripts):
            raise ValueError("输入参数长度不匹配")
        if len(output_addresses) != len(output_values):
            raise ValueError("输出参数长度不匹配")

        # 2. 构造输入列表（普通交易需引用已有UTXO）
        inputs = []
        for txid, referid, script in zip(input_txids, input_referids, input_scripts):
            inputs.append({
                "txid": txid,
                "referid": referid,
                "scriptSig": script,  # 包含签名和公钥的解锁脚本
                "sequence": 0xFFFFFFFF  # 默认最大序列号
            })

        # 3. 构造输出列表（锁定到目标地址）
        outputs = []
        for address, value in zip(output_addresses, output_values):
            outputs.append({
                "value": value,
                "script_pubkey_hash": address  # 地址转锁定脚本
            })

        # 4. 组装交易数据
        Tx_data = TransactionScript.generate_Tx_script(
            inputs=inputs,
            outputs=outputs,
            nlockTime=nlockTime
        )

        # 5. 序列化并计算TXID
        serialized_Tx = TransactionScript.serialize_Tx(Tx_data)

        Txid = hashlib.sha256(hashlib.sha256(serialized_Tx).digest()).digest()[::-1].hex()

        return Txid, Tx_data

# def address_to_scriptpubkey(address: str) -> str:
#     """模拟地址转锁定脚本（实际需实现Base58/Bech32解码）"""
#     return f"76a914{hashlib.sha256(address.encode()).hexdigest()[:40]}88ac"  # P2PKH示例
# 本设计使用 P2PKH支付，无法 address_to_scriptpubkey
# 只有 P2PK 才能 address_to_scriptpubkey


# ----------- 示例用法 -----------
if __name__ == "__main__":  # Standard Transaction Script
    # 模拟输入（引用已有的UTXO）
    input_txids = ["ee8ed5f529c9b9c2ad4113de129c3723ace75fa40a6a5c5d70df95d71774d179",
                   "f02bc337bbee55eeeba2c588c76d9f0db4d6fe74364f9b26fa6bd00a6eaa36fc"]  # 实际需替换为真实UTXO的TXID
    input_referids = [0, 1]                      # UTXO的输出索引
    input_scripts = [
        hashlib.sha256("40c73707d0ff9d71ec").hexdigest(),  # 第一个输入的签名脚本（签名+公钥）
        hashlib.sha256("407e9be4dd066e5c69").hexdigest()   # 第二个输入的签名脚本
    ]

    # 模拟输出（1个接收方 + 1个找零）
    output_addresses = ["1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                        "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2"]
    output_values = [100000000,
                     399900000]  # 转账0.1 BTC，找零3.999 BTC（假设输入总额4 BTC）

    # 生成交易
    Txid, Tx_data = StandardTransactionScript.generate_normal_Txid(
        input_txids=input_txids,
        input_referids=input_referids,
        input_scripts=input_scripts,
        output_addresses=output_addresses,
        output_values=output_values,
        nlockTime=0
    )

    print("生成的普通交易 TXID:", Txid)
    print("交易数据:", Tx_data)
