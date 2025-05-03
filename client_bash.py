# -*- coding: utf-8 -*-
"""
区块链命令行客户端，支持P2P网络通信、挖矿、交易等操作
运行方式: python client.py [--port P2P_PORT] [--api-port API_PORT] [--peer PEER_IP:PORT]
"""

import argparse
import threading
import time
from flask import Flask, jsonify
import requests
from blockchain import Blockchain
from mempool import Mempool
from mining import MiningModule
from network import NetworkInterface

# 默认配置
DEFAULT_P2P_PORT = 5000
DEFAULT_API_PORT = 5001

class BlockchainClient:
    """区块链命令行客户端"""
    
    def __init__(self, p2p_port, api_port):
        self.blockchain = Blockchain()
        self.mempool = Mempool()
        self.miner = MiningModule()
        self.network = NetworkInterface(self.blockchain, self.mempool)
        self.p2p_port = p2p_port
        self.api_port = api_port

        # 启动网络服务
        threading.Thread(target=self._start_servers).start()
        time.sleep(1)  # 等待服务启动

    def _start_servers(self):
        """启动P2P和API服务"""
        self.network.app.run(port=self.p2p_port)
        api_app = Flask(__name__)
        api_app.run(port=self.api_port)

    def add_peer(self, address):
        """添加邻居节点"""
        self.network.add_neighbor(address)
        print(f"已添加邻居节点: {address}")

    def mine_block(self, miner_address):
        """挖矿"""
        try:
            getbkh = self.blockchain.blockchain[-1].block_hash  # 有前面的块
        except:
            getbkh = '0'*64  # 没有前面的块
        self.miner.reset_last_block_hash(getbkh)  # 更改前哈希值
        new_block = self.miner.mine_block(
            mempool=self.mempool,
            blockchain=self.blockchain,
            miner_address=miner_address
        )
        if self.network.validate_and_add_block(new_block):
            self.network.broadcast_block(new_block)
            print(f"成功挖到区块 #{new_block.header.index}")
        else:
            print("挖矿失败，区块验证未通过")

    def print_blockchain(self):
        """打印区块链信息"""
        print("\n当前区块链状态:")
        print(f"区块高度: {self.blockchain.height()}")
        try:
            print(f"最新区块哈希: {self.blockchain.blockchain[-1].block_hash[:16]}...")
        except:
            pass
        print(f"邻居节点数: {len(self.network.P2P_neighbor)}\n")

    def sync_blocks(self):
        """手动触发区块同步"""
        self.network.sync_blocks_once()

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='区块链客户端')
    parser.add_argument('--port', type=int, default=DEFAULT_P2P_PORT, help='P2P端口')
    parser.add_argument('--api-port', type=int, default=DEFAULT_API_PORT, help='API端口')
    parser.add_argument('--peer', help='初始邻居节点地址 (IP:PORT)')
    args = parser.parse_args()

    # 初始化客户端
    client = BlockchainClient(args.port, args.api_port)
    
    # 添加初始邻居节点
    if args.peer:
        client.add_peer(args.peer)

    # 命令行交互
    while True:
        cmd = input("\n请输入命令 (mine/addpeer/sync/exit): ").strip().lower()
        
        if cmd == 'mine':
            address = input("请输入矿工地址: ")
            client.mine_block(address)
            client.print_blockchain()
        
        elif cmd == 'addpeer':
            peer = input("请输入邻居节点地址 (IP:PORT): ")
            client.add_peer(peer)
        
        elif cmd == 'sync':
            client.sync_blocks()
            print("已触发区块同步")
        
        elif cmd == 'exit':
            print("退出系统")
            break
        
        else:
            print("无效命令，可用命令: mine/addpeer/sync/exit")

if __name__ == "__main__":
    main()