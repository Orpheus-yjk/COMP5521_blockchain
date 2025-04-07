"""
这是测试。
"""
import os
import hashlib
import ecdsa
import base58
from typing import Tuple


class GenerateKeysUtils:
    """此类包含静态方法装饰器 @staticmethod

    安全注意事项：
    1. 实际应用中私钥必须严格保密
    2. 生产环境应使用专业库（如`bitcoinlib`、`pycoin`）
    3. 此代码仅用于教育目的，展示比特币地址生成原理
    如果需要更完整的实现（包括WIF格式私钥、测试网地址等），可以在上述基础上扩展。
    """
    @staticmethod
    def generate_arbitrary_random_number(bitnum):
        """生成任意字节随机数"""
        return os.urandom(bitnum)

    # 以下是使用Python实现比特币地址生成的完整代码（从私钥 → 公钥(压缩公钥） → 公钥哈希 → 比特币地址），兼容主流加密库并符合比特币标准
    @staticmethod
    def generate_private_key():
        """生成随机32字节私钥（256位）"""
        return os.urandom(32)

    @staticmethod
    def private_key_to_public_key(private_key):
        """将私钥转换为压缩公钥"""
        sk = ecdsa.SigningKey.from_string(private_key, curve=ecdsa.SECP256k1)
        vk = sk.get_verifying_key()
        # 压缩公钥：前缀02(偶数y)或03(奇数y) + x坐标
        x = vk.pubkey.point.x()
        y = vk.pubkey.point.y()
        return bytes.fromhex(f'{"02" if y % 2 == 0 else "03"}') + x.to_bytes(32, 'big')

    @staticmethod
    def hash160(data):
        """先SHA256再RIPEMD160哈希"""
        sha256 = hashlib.sha256(data).digest()
        ripemd160 = hashlib.new('ripemd160')
        ripemd160.update(sha256)
        return ripemd160.digest()

    @staticmethod
    def public_key_to_address(public_key, version_byte=0x00):
        """将公钥转换为比特币地址"""
        # 1. 计算公钥的hash160
        h160 = GenerateKeysUtils.hash160(public_key)

        # 2. 添加版本字节（主网是0x00）
        extended = bytes([version_byte]) + h160

        # 3. 计算校验码（两次SHA256的前4字节）
        checksum = hashlib.sha256(hashlib.sha256(extended).digest()).digest()[:4]

        # 4. Base58Check编码
        return base58.b58encode(extended + checksum).decode('ascii')

    @staticmethod
    def generate_private_and_public_key(output_info=False):
        """返回一组私钥和公钥，以及公钥决定的地址"""

        # 1. 生成私钥（32字节随机数）
        priv_key = math_utils.generate_private_key()
        if output_info:
            print(f"私钥 (hex): {priv_key.hex()}")

        # 2. 生成压缩公钥（33字节）
        pub_key = math_utils.private_key_to_public_key(priv_key)
        if output_info:
            print(f"公钥 (hex): {pub_key.hex()}")

        # 3. 生成比特币地址
        address = math_utils.public_key_to_address(pub_key)
        if output_info:
            print(f"比特币地址: {address}")

        return priv_key, pub_key, address

class SignMessageUtils:
    @staticmethod
    def sign_transaction(private_key: bytes, message: bytes) -> bytes:
        """用私钥对交易信息签名"""
        sk = ecdsa.SigningKey.from_string(private_key, curve=ecdsa.SECP256k1)
        return sk.sign(message)

class VerifyHashAndSignatureUtils(GenerateKeysUtils, SignMessageUtils):
    """验证签名。

    关键步骤解析：
        **提取公钥哈希**
            - 从锁定脚本 `OP_DUP OP_HASH160 <pubKeyHash> OP_EQUALVERIFY OP_CHECKSIG` 中提取 `<pubKeyHash>`
        **生成公钥**
            - 使用接收方的私钥生成压缩公钥（33字节）
        **验证公钥哈希**
            - 计算生成公钥的 `hash160`，确保与锁定脚本中的哈希匹配
        **创建交易签名**
            - 对交易数据的哈希（实际应为交易的 `double SHA256`）使用私钥签名
        **构建解锁脚本**
            - 最终解锁脚本格式：`<signature> <pubKey>`
    实际比特币节点验证流程：拼接解锁脚本 + 锁定脚本
    <sig> <pubKey> OP_DUP OP_HASH160 <pubKeyHash> OP_EQUALVERIFY OP_CHECKSIG
    """

    @staticmethod
    def unlock_p2pkh(locking_script: str, privkey: bytes) -> Tuple[bytes, bytes]:
        """
        解锁P2PKH脚本
        返回: (签名, 公钥)
        """
        # 1. 从锁定脚本提取公钥哈希（实际应用需解析脚本）
        pubkey_hash_hex = locking_script[6:-4]  # 简单提取，真实场景需要完整脚本解析
        pubkey_hash = bytes.fromhex(pubkey_hash_hex)

        # 2. 生成公钥
        pubkey = GenerateKeysUtils.private_key_to_public_key(privkey)

        # 3. 验证公钥哈希是否匹配
        if GenerateKeysUtils.hash160(pubkey) != pubkey_hash:
            raise ValueError("公钥哈希不匹配！")

        # 4. TODO: 创建待签名的交易数据（实际应为交易的哈希）
        tx_data = b"Demo trading data"  # FIXME: 实际应为交易的double SHA256哈希

        # 5. 用私钥签名
        signature = SignMessageUtils.sign_transaction(privkey, tx_data)

        return signature, pubkey

    @staticmethod
    def verify_signature(public_key: bytes, signature: bytes, message: bytes) -> bool:
        """验证签名是否有效"""
        vk = ecdsa.VerifyingKey.from_string(public_key, curve=ecdsa.SECP256k1)
        try:
            return vk.verify(signature, message)
        except ecdsa.BadSignatureError:
            return False



# 完整生成流程演示
if __name__ == "__main__":
    math_utils = GenerateKeysUtils()
    math_utils.generate_private_and_public_key(True)

    # 假设这是接收方拥有的私钥（实际应用中应安全存储）
    RECEIVER_PRIVKEY = bytes.fromhex("18e14a7b6a307f426a94f8114701e7c8e774e7f9a47e2c2035db29a206321725")