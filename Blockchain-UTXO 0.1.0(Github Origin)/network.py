# -*- coding: utf-8 -*-

"""网络：应实现基本的交互和验证。

说明：
a) 创建一个API，用于广播新区块并从其他节点获取区块。API应允许用户通过HTTP请求、套接字或不同端口与区块链进行交互。
b) 实现一个功能，用于检查我们从其他矿工接收的新区块是否有效。（提示：重新计算区块的哈希并将其与区块的给定哈希进行比较。）

TODO:
    network.py中有一些验证函数，但实现不完整。
    未实现P2P网络、数字签名等安全机制。
    缺少交易验证逻辑。
"""

__author__ = 'COMP5521_YJK\'s_Team'
__date__ = '2023-12-6'

def prove_valid_block(self, _block):
    if _block.prev_hash != self.last_block().hash or (
    not _block.calculate_block_hash.startswith('0' * _block.difficulty)):
        return False
    return True

def prove_valid_chain(self, another_chain):
    """验证区块（链）"""
    return True ### for implement

def broadcast_block():
    """传播区块"""
    None

def get_block():
    """获取区块"""
    None

### API to interact with disk data
### so python file is only to interact with disk data
### should not store blockchain in the python running