import hashlib
import random
import struct
from typing import Tuple

# Coinbase Info
# 拟一个超级节点的公钥来表征发薪人/系统
SUPERNODE_PRIVKEY = b"9a50346681853432d90e90592938750164ceaec382a8a3473da9e5a1e21d0e5d"  # 无用处，仅供验证
SUPERNODE_PUBLKEY = b"0265abc03fbdc82e4e3312cba161f92034533fe3c11c5da310021ed3d738c57da4"
SUPERNODE_ADDRESS = "1HGUt8BThQAjLtmqKAaRF4cHt5ia22HKsp"
SUPERNODE_DEMO_SIG = b"bd2c37105f141c3bc95911a7e0d40f39f0351dc1f43562c6be014bcaef483e2884af314547c7bb294beac2dbf35cb7768e0ed71b71a7339422330a7cb309c520"

class TransactionScript:
    """交易序列化辅助工具"""
    VERSION = 1

    @staticmethod
    def generate_input_script(txid, vout, scriptSig_hex, sequence):
        """构建输入流script"""
        return [{
            "txid": txid,
            "vout": vout,
            "scriptSig": scriptSig_hex,
            "sequence": sequence
        }]

    @staticmethod
    def generate_output_script(mining_reward : int, miner_address : str):
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
            "vin": inputs,
            "vout": outputs
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
        txid = bytes.fromhex(Tx_data["vin"][0]["txid"])[::-1]  # 反转字节序
        vout = struct.pack("<I", Tx_data["vin"][0]["vout"])
        scriptSig = bytes.fromhex(Tx_data["vin"][0]["scriptSig"])
        scriptSig_len = bytes([len(scriptSig)])
        sequence = struct.pack("<I", Tx_data["vin"][0]["sequence"])
        # 输出计数 (1字节)
        vout_count = bytes([len(Tx_data["vout"])])
        # 输出数据
        output_data = b""
        for out in Tx_data["vout"]:
            value = struct.pack("<Q", out["value"])
            script_pubkey_hash = out["script_pubkey_hash"].encode('utf8')  # bytes.fromhex(out["script_pubkey"]) 这是P2PK的。本设计采用P2PKH
            script_len = bytes([len(script_pubkey_hash)])
            output_data += value + script_len + script_pubkey_hash
        # 锁时间 (4字节小端)
        locktime = struct.pack("<I", Tx_data["locktime"])

        return version + vin_count + txid + vout + scriptSig_len + scriptSig + sequence + vout_count + output_data + locktime

class Coinbase(TransactionScript):
    """用于随机生成符合比特币规范的 Coinbase 交易 TXID"""
    @staticmethod
    def generate_coinbase_txid(block_height: int, miner_address: str, mining_reward: int) -> Tuple[str, dict]:
        """
        生成随机的符合规范的 Coinbase 交易 TXID
        返回: (Txid_hex, Tx_script_dict)
        """
        # 1. 构造 Coinbase 输入 (唯一输入，无前序交易)
        coinbase_script = Coinbase.generate_coinbase_script(block_height)

        # 2. 构造输入，输出（矿工奖励）
        inputs = TransactionScript.generate_input_script(
            txid="0000000000000000000000000000000000000000000000000000000000000000",
            vout=0xFFFFFFFF,  # Coinbase 的 vout 固定为 0xFFFFFFFF
            scriptSig_hex=coinbase_script.hex(),
            sequence=0xFFFFFFFF
        )
        outputs = TransactionScript.generate_output_script(
            mining_reward = mining_reward,
            miner_address = miner_address
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

    @classmethod
    def is_coinbase(cls, Tx_script):
        """判断是否为coinbase（挖矿奖励区块）"""
        if len(Tx_script["vin"])>1 or len(Tx_script["vout"])>1: return False
        input = Tx_script["vin"][0]
        if input["txid"] != "0000000000000000000000000000000000000000000000000000000000000000" or \
                input["vout"] != 0xFFFFFFFF or input["sequence"] != 0xFFFFFFFF:
            return False
        return True

# ----------- 示例用法 -----------
if __name__ == "__main__":
    random_privkey_hex = "bdb621d428908a617bbbdbae022f12680c01e1da9c7451cd82a39fe7eae609de"
    random_publkey_hex = "0370cecdb7f33a1c26172100ffd3d600395a44b47f39c58617e11b6d768b96e910"
    random_address_hex = "16HbyV4TjEBRaULBzF7zfko377Lf1JtSvY"

    # 随机生成一个 Coinbase 交易（区块高度 840000，矿工地址随机，奖励 6.25 BTC）
    Txid, Tx_script = Coinbase.generate_coinbase_txid(
        block_height=840000,
        miner_address=random_address_hex,
        mining_reward=6250000000,  # 6.25 BTC = 625,000,000,000 satoshi
    )

    print("生成的 Coinbase TXID:", Txid)
    print("交易数据:", Tx_script)
    print("是否Coinbase:", Coinbase.is_coinbase(Tx_script))