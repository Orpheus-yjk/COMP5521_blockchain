"""
比特币密钥生成与交易签名验证工具集

模块功能概述：
本模块提供比特币相关密钥生成、地址派生、交易签名及验证的核心功能实现，包含以下主要组件：

1. 密钥生成工具 (GenerateKeysUtils)
   - 生成符合比特币标准的随机私钥（32字节）
   - 将私钥转换为压缩格式公钥（SECP256k1曲线）
   - 通过公钥计算比特币地址（Base58Check编码）
   - 完整密钥对生成流程封装

2. 交易签名工具 (SignMessageUtils)
   - 使用ECDSA算法对交易数据进行签名
   - 支持SECP256k1椭圆曲线数字签名

3. 验证工具集 (VerifyHashAndSignatureUtils)
   - P2PKH脚本解锁逻辑实现
   - 签名有效性验证
   - 公钥哈希匹配检查

安全注意事项：
生产环境使用警告：
1. 本代码仅用于教育目的，展示比特币底层技术原理
2. 实际应用应使用专业库（如bitcoinlib/pycoin）
3. 私钥必须严格保密，示例中的内存存储方式不安全

扩展建议：
- 支持WIF格式私钥导入/导出
- 增加测试网地址生成功能
- 实现BIP32分层确定性钱包
- 添加BIP39助记词支持

版本要求：
- Python 3.6+
- 依赖库：ecdsa, hashlib, base58

典型使用流程：
1. 生成密钥对 → 2. 构建交易 → 3. 签名 → 4. 验证

示例代码见模块底部 __main__ 部分
"""

__author__ = 'YJK developer'
__date__ = '2025-04'

import logging
import os
import hashlib
import ecdsa
import base58

__all__ = ['GenerateKeysUtils', 'SignMessageUtils', 'VerifyHashAndSignatureUtils']  # 明确指定哪些名称可以被 `import *` 导入

class GenerateKeysUtils:
    """密钥生成工具。负责生成私钥，公钥以及最终地址。此类包含静态方法装饰器 @staticmethod。

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
    def private_key_to_public_key(private_key: bytes) -> bytes:
        """将私钥转换为压缩公钥"""
        sk = ecdsa.SigningKey.from_string(private_key, curve=ecdsa.SECP256k1)
        vk = sk.get_verifying_key()
        # 压缩公钥：前缀02(偶数y)或03(奇数y) + x坐标
        x = vk.pubkey.point.x()
        y = vk.pubkey.point.y()
        return bytes.fromhex(f'{"02" if y % 2 == 0 else "03"}') + x.to_bytes(32, 'big')

    @staticmethod
    def uncompressed_public_key(compressed_public_key: bytes) -> bytes:
        """解压缩压缩公钥"""
        if compressed_public_key.startswith(b'\x02') or compressed_public_key.startswith(b'\x03'):
            x = int.from_bytes(compressed_public_key[1:], 'big')
            y_parity = compressed_public_key[0] - 2
            curve = ecdsa.SECP256k1.curve
            a = curve.a()
            b = curve.b()
            p = curve.p()
            alpha = pow(x ** 3 + a * x + b, (p + 1) // 4, p)
            y = p - alpha if alpha % 2 ^ y_parity else alpha
            new_public_key = b'\x04' + x.to_bytes(32, 'big') + y.to_bytes(32, 'big')
            return new_public_key
        else:
            logging.warning("Invalid Compressed Public Key!")
            return compressed_public_key

    @staticmethod
    def hash160(data):
        """先SHA256再RIPEMD160哈希"""
        sha256 = hashlib.sha256(data).digest()
        ripemd160 = hashlib.new('ripemd160')
        ripemd160.update(sha256)
        return ripemd160.digest()

    @staticmethod
    def _public_key_to_address(public_key, version_byte=0x00):
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
    def public_key_to_public_address(pub_key, output_info=False):
        """生成具有区块链地址格式的公钥哈希。此方法公用，为了更好地解耦，以便用户解锁脚本和矿工验证"""

        # 1. 生成私钥（32字节随机数）

        # 2. 生成压缩公钥（33字节）

        # 3. 生成比特币地址
        address = GenerateKeysUtils._public_key_to_address(pub_key)
        if output_info:
            print(f"比特币地址: {address}")

        return address

    @staticmethod
    def randomly_generate_privateKey_and_publicKey_and_publicKeyHash(output_info=False):
        """返回私钥，公钥和公钥哈希。此方法应该为私有，只有持有私钥的人才能调用"""

        # 1. 生成私钥（32字节随机数）
        priv_key = GenerateKeysUtils.generate_private_key()
        if output_info:
            print(f"私钥 (hex): {priv_key.hex()}")

        # 2. 生成压缩公钥（33字节）
        pub_key = GenerateKeysUtils.private_key_to_public_key(priv_key)
        if output_info:
            print(f"公钥 (hex): {pub_key.hex()}")

        # 3. public_key_to_public_key_hash: 生成比特币地址
        return priv_key, pub_key, GenerateKeysUtils.public_key_to_public_address(pub_key, output_info)


class SignMessageUtils:
    """交易签名工具（兼容压缩/非压缩公钥验证）"""

    @staticmethod
    def sign_transaction(private_key: bytes, message: bytes) -> bytes:
        """
        用私钥对交易信息签名（返回DER编码签名，兼容比特币标准）

        参数:
            private_key: 32字节私钥
            message: 待签名的原始交易数据（需转换为double SHA256哈希）
        """
        # 1. 检查输入是否为字节类型
        if not isinstance(message, bytes):
            raise TypeError("message 必须是 bytes 类型")

        # 计算交易的 double SHA256 哈希
        # tx_hash = hashlib.sha256(hashlib.sha256(message).digest()).digest()
        # 容易出错： 不用上一行，因为ecdsa.sign中已经做了（业务层面）；而且这边如果做了双哈希，verify也必须同步做双哈希（容易漏，而且增加运算量）
        # 所以直接传入message就好了

        # 2. 使用确定性签名（RFC 6979）
        sk = ecdsa.SigningKey.from_string(private_key, curve=ecdsa.SECP256k1, hashfunc=hashlib.sha256)

        return sk.sign_deterministic(message, hashfunc=hashlib.sha256)  # 固定签名结果

class VerifyHashAndSignatureUtils(GenerateKeysUtils, SignMessageUtils):
    """验证工具集。

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
        <sig> <pubKey> || OP_DUP OP_HASH160 <pubKeyHash> OP_EQUALVERIFY OP_CHECKSIG
    """

    @staticmethod
    def unlock_p2pkh_script(locking_script: str, public_key: bytes, signature: bytes) -> str:
        """解锁P2PKH脚本。返回: (签名, 公钥)

        私钥不应被随意传递，而应仅在安全的签名环境中使用（如硬件钱包）。所以好的设计是：外部预先计算签名，再传入 unlock_p2pkh.

        谁能调用这个函数？在真实的比特币网络中，unlock_p2pkh 的调用者是：
        - 交易的发起者（资金接收方）：
            当用户想花费自己收到的比特币时，需要用自己的私钥生成签名，并构造解锁脚本（脚本放入mempool中，同时对utxo的‘加锁’进行广播；‘加锁‘改’已记录’是在挖矿记录时由矿工广播）。
            例如：Alice 向 Bob 转账，Bob 后续要花费这笔钱时，需调用类似逻辑。
        - 矿工/全节点：
            矿工在验证交易时，会执行锁定脚本 + 解锁脚本的组合，检查签名是否有效。
            但矿工不会直接调用此函数，而是通过比特币节点的脚本引擎处理。
        """
        # 1. 从锁定脚本提取公钥哈希（实际应用需解析脚本）
        parse_script = locking_script.split()  # 脚本解析过于简单：当前代码用 split() 简单分割锁定脚本，但真实的比特币脚本是二进制格式，需要更严谨的解析逻辑。
        if parse_script[0]!="OP_DUP" or parse_script[1]!="OP_HASH160" or \
                parse_script[3]!="OP_EQUALVERIFY" or parse_script[4]!="OP_CHECKSIG" or \
                len(parse_script)!=5:
            logging.warning("锁定脚本格式错误，无法解析！")
            return "Unlock Script Fail!"
        pubkey_hash_loaded = parse_script[2]  # 提取的公钥哈希

        # 2. 生成符合区块链地址格式的公钥哈希
        rehash_pubkey = GenerateKeysUtils.public_key_to_public_address(public_key)

        # 3. 验证公钥哈希是否匹配
        if rehash_pubkey != pubkey_hash_loaded:
            logging.warning("公钥哈希不匹配！")
            return "Unlock Script Fail!"

        # 4. 用私钥重新计算的公钥创建待签名的交易数据
        # TODO：实际应为交易的哈希
        tx_data = b"Demo trading data"  # FIXME: 实际应为交易的double SHA256哈希

        # 构建解锁脚本: <sig> <pubKey>
        unlocking_script = ' '.join([signature.hex(), public_key.hex()])
        return unlocking_script

    @staticmethod
    def verify_signature(public_key: bytes, signature: bytes, message: bytes) -> bool:
        """验证签名（自动处理压缩/非压缩公钥）"""
        # 在验证前添加格式检查
        if len(public_key) not in [33, 65]:  # 压缩公钥33字节，非压缩65字节
            print("无效的公钥长度")
            return False

        if len(signature) != 64:  # ECDSA签名通常为64字节
            print("无效的签名长度")
            return False

        try:
            # 1. 如果是压缩公钥（33字节），解压为65字节（带前缀04）
            if len(public_key) == 33:
                public_key = GenerateKeysUtils.uncompressed_public_key(public_key)

            # 2. 如果是65字节非压缩公钥（带前缀04），去除前缀
            if len(public_key) == 65 and public_key.startswith(b'\x04'):
                public_key = public_key[1:]  # 移除前缀04，保留64字节的x+y

            # 3. 检查公钥长度是否为64字节
            if len(public_key) != 64:
                logging.warning("公钥格式无效，必须为64字节（非压缩）或33字节（压缩）")
                return False

            # 4. 验证签名
            vk = ecdsa.VerifyingKey.from_string(public_key, curve=ecdsa.SECP256k1)
            return vk.verify(signature, message, hashfunc=hashlib.sha256)

        except (ecdsa.BadSignatureError, ValueError) as e:
            return False

# 完整生成流程演示
if __name__ == "__main__":
    key_utils = GenerateKeysUtils()
    key_utils.randomly_generate_privateKey_and_publicKey_and_publicKeyHash(output_info=True)

    print("----------------------------------------------------------------------------------")
    sign_utils = SignMessageUtils()
    verify_utils = VerifyHashAndSignatureUtils()
    # 假设这是接收方拥有的私钥（实际应用中应安全存储）
    RECEIVER_PRIVKEY = bytes.fromhex("9a50346681853432d90e90592938750164ceaec382a8a3473da9e5a1e21d0e5d")
    RECEIVER_PUBKEY = bytes.fromhex("0265abc03fbdc82e4e3312cba161f92034533fe3c11c5da310021ed3d738c57da4")
    RECEIVER_ADDRESS = "1HGUt8BThQAjLtmqKAaRF4cHt5ia22HKsp"
    # 模拟锁定脚本（来自发送方）
    locking_script = f"OP_DUP OP_HASH160 {RECEIVER_ADDRESS} OP_EQUALVERIFY OP_CHECKSIG"
    try:
        # 验证脚本执行（模拟比特币节点的验证）
        tx_data = b"Demo trading data"
        sig = sign_utils.sign_transaction(RECEIVER_PRIVKEY, tx_data)  # ecdsa.sign有双哈希功能，不需要专门写

        # 资金接收方解锁过程
        unlocking_script = verify_utils.unlock_p2pkh_script(locking_script, RECEIVER_PUBKEY, sig)
        signature_hex, pubkey_hex= unlocking_script.split(maxsplit=2)

        print(f">>>提供的私钥: {RECEIVER_PRIVKEY.hex()}")
        print(f">>>提供的公钥: {pubkey_hex}")
        print(f">>>生成的签名: {signature_hex}")
        print(f">>>交易的原始数据: {tx_data.hex()}")
        print(f">>>比特币网络地址: {RECEIVER_ADDRESS}")
        print("----------------------------------------------------------------------------------")

        pubkey = bytes.fromhex(pubkey_hex)
        if verify_utils.verify_signature(pubkey, sig, tx_data):
            print("✓ 签名验证成功，解锁有效！")
        else:
            print("✗ 签名验证失败！")

    except ValueError as e:
        print(f"解锁失败: {str(e)}")

