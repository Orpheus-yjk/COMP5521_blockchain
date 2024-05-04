from ecdsa import SigningKey, NIST384p, VerifyingKey

def generate_key():
    sk = SigningKey.generate(curve=NIST384p)
    vk = sk.get_verifying_key()
    return vk, sk


def make_transaction(sk, message):
    signature = sk.sign(str(message).encode("utf8"))  # 统一编码格式
    return signature


def is_valid(vk_string, message, signature):
    vk = VerifyingKey.from_string(vk_string, NIST384p)
    try:
        vk.verify(signature, str(message).encode("utf8"))  # 统一编码格式
        return True
    except:
        return False


message = "I am a transaction !"
vk, sk = generate_key()  # 产生公钥和私钥
vk_string = vk.to_string()
sig = make_transaction(sk, message)  # 模拟交易签名

if is_valid(vk_string, message, sig):
    print("True")
else:
    print("False")

