# -*- coding: utf-8 -*-

"""
这是一个测试脚本。
"""

__author__ = 'YJK'
__date__ = '2023-12-6'

from ecdsa import SigningKey, NIST384p
sk = SigningKey.generate(curve=NIST384p)
vk = sk.verifying_key

print(sk.to_string().hex())
print(vk.to_string().hex())