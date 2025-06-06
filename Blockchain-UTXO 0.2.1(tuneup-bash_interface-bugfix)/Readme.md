# Blockchain-UTXO 0.2.1(联调、bash客户端和bug修补)

## 一、代码中的继承关系分析

### 1. 文件内继承关系

以下是主要的继承关系：

1. **math_util.py**:
   - `VerifyHashAndSignatureUtils` 继承自 `GenerateKeysUtils` 和 `SignMessageUtils`

2. **transactions.py**:
   - `Transaction` 类继承自 `CoinbaseScript`, `StandardTransactionScript`, `VerifyHashAndSignatureUtils`

3. **transaction_script.py**:
   - `CoinbaseScript` 继承自 `TransactionScript`
   - `StandardTransactionScript` 继承自 `TransactionScript`

### 2. 模块间引用

以下是主要的引用关系：

1. blockchain 引用 transactions
2. transactions 引用 math_util transaction_script
3. mempool 引用 transactions math_util
4. mining 引用 transactions blockchain
5. network 引用 transaction_script transactions mempool blockchain mining

## 二、初始简易`client.py` 实现


```python
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
        print(f"最新区块哈希: {self.blockchain.blockchain[-1].block_hash[:16]}...")
        print(f"邻居节点数: {len(self.network.P2P_neighbor)}\n")

    def sync_blocks(self):
        """手动触发区块同步"""
        self.network._sync_blocks()

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
```

# 三、bash client使用说明

**Total Code Size: 4000 lines**

**client_bash.py: 500 lines**

1. **启动节点**:

- 示例：

```bash
cd /../your_repo

# 默认端口
python client.py

# 指定端口号
python client.py --port 5000 --api-port 5001

# 指定端口号和邻居
python client.py --port 5000 --api-port 5001 --peer 127.0.0.1:6000
```

- 部署双节点并互相通信：

```bash
# 节点1（指定端口号和邻居）
python client.py --port 5000 --api-port 5001 --peer 127.0.0.1:6000

# 节点2（指定端口号和邻居）
python client.py --port 6000 --api-port 6001 --peer 127.0.0.1:5000
```

- 部署三节点的链式结构（目的：说明无法从链指向的尾端获取最新的信息）

```bash
# 节点1（指定端口号和邻居，同时作为miner，addpeer指向6000既能广播新的区块，又能资助sync获取该节点信息，属于单方向行动）
python client.py --port 5000 --api-port 5001 --peer 127.0.0.1:6000

# 节点2（指定端口号，是尾端只接受广播消息并自我更新，一定程度上成为了边缘数据库）
python client.py --port 6000 --api-port 6001

# 节点3（指定端口号和邻居，是miner的上游可以通过自主sync随时获取最新区块链信息）
python client.py --port 7000 --api-port 7001 --peer 127.0.0.1:5000
```

- 部署五节点的复杂网络结构 易于验证持续挖矿下的同步功能和转账正确性（后附公私钥对和节点地址参考）

```bash
python client_bash.py --port 5000 --api-port 5001
# 后续执行数据库删除等...
python client_bash.py --port 6000 --api-port 6001

python client_bash.py --port 7000 --api-port 7001

python client_bash.py --port 8000 --api-port 8001

python client_bash.py --port 9000 --api-port 9001
# 监视器

# 每个client_bash运行在127.0.0.1:p2p_port
# 6000端口命令行：
addpeer
127.0.0.1:5000
addpeer
127.0.0.1:8000
# 7000端口命令行：
addpeer
127.0.0.1:5000
addpeer
127.0.0.1:8000
# 5000端口命令行：
addpeer
127.0.0.1:6000
# 9000端口命令行：监视器
addpeer
127.0.0.1:5000 ... 127.0.0.1:8000
```
2. **主要命令**:

   - `mine`: 开始挖矿，需要输入矿工地址

     - 参考地址：`1HGUt8BThQAjLtmqKAaRF4cHt5ia22HKsp`,`17LVrmuCzzibuQUJ265CUdVk6h6inrTJKV`,`1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa`,`1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2`

   - `continuous_mine`: 同上，不过要输入连续挖矿的个数

     - 挖矿时间会慢慢边长，最开始只有零点几秒。挖矿中间会休息若干时间

   - `addpeer`: 添加邻居节点，格式为`IP:PORT`

   - `transfer`: 开启转账交易，输入私钥（用于登录矿工地址），对方地址，以及转账金额，手续费率（推荐参考比特币的20~50之间）。

     - 可用math_util.py中的**key_utils.randomly_generate_privateKey_and_publicKey_and_publicKeyHash (output_info=True)**生成相关填写信息

     - 这里有可以参考的公私钥对和节点地址：

       - 节点1：
         私钥 (hex): 7fe66e4a97a760e84707dcc15404e838e9398b2fea5561d0311ef853a3214da9
         公钥 (hex): 025604c0f3f98bd73cc4542fd9ede2d37f46836dd37415428983bec1c6d618550c
         比特币地址: 18QJhgS3DkPJGiSaFkNZMoe9Nsq1bv4eHH(499997890)

         节点2：
         私钥 (hex): 27efcd440849235a99d10539f6339aba3cfa50d575a313ffdb5123f78e8629c3
         公钥 (hex): 03621421ea52ce3f85672fe018167f35274614ece6af5b6ce0ea86f9039783724e
         比特币地址: 18n3kQHq2nUf1LkJwpo3ZzK5kQqnY4LGey(100)

         节点3:

         私钥 (hex): 6d3c478b02281114bb66f1cb499daa041938125822f5f33ee504f585c3ebc2c7
         公钥 (hex): 028528caf68e7277ab2f1032b6bcffc151ef1b05d250d5d32b2f6201459e2a6122
         比特币地址: 131hU8Sk1Vortm2EU8vKWqBMRsHnwkgYEU(500000000)

   - `sync`: 手动触发区块链同步

   - `exit`: 退出程序

3. **跨网络通信**:

   - 确保节点在同一局域网
   - 使用真实内网IP地址而非`localhost`
   - 防火墙需开放指定端口

4. **实现的功能**

- **P2P网络通信**:
   - 自动维护邻居节点列表
   - 区块/交易广播机制
   - HTTP接口提供区块链数据

- **共识机制**:
   - PoW挖矿算法
   - 动态难度调整
   - 区块验证（哈希、Merkle根、交易有效性）
   - 转账交易验证（交易签名）
   
- **命令行交互**:
   - 实时查看区块链状态
   - 手动控制挖矿和同步
   - 网络节点管理

- **数据存储**:
   - 区块链数据序列化存储
   - UTXO状态内存管理
   - 交易池维护

此实现满足项目要求中的网络通信、共识机制、数据存储等核心需求，不同节点可通过命令行实现区块链网络的交互操作，节点之间定期同步区块链数据。

5. **运行成功界面**

（1）三节点网络成功界面

![](../pics/success_3_cmd_structure.jpg)

<img src="../pics/success_3_cmd.jpg" style="zoom: 33%;" />

（2）五节点网络成功界面

**包含转账、消息同步**

![](../pics/success_5_cmd_structure.jpg)

<img src="../pics/success_5_cmd.jpg" style="zoom: 50%;" />

<img src="../pics/success_tx_blk.jpg" style="zoom: 50%;" />

---

# 将项目部署到Kubernetes集群的指南

要将这个区块链项目部署到Kubernetes集群，可以按照以下步骤进行：

## 1. 容器化应用

首先为每个组件创建Docker镜像：

1. **创建Dockerfile**:
```dockerfile
FROM python:3.9-slim

WORKDIR /app
COPY . .

RUN pip install -r requirements.txt

CMD ["python", "client_bash.py", "--port", "5000", "--api-port", "5001"]
```

2. **构建镜像**:
```bash
docker build -t blockchain-node .
```

## 2. Kubernetes部署配置

### 2.1 创建Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: blockchain-node
spec:
  replicas: 3  # 运行3个节点
  selector:
    matchLabels:
      app: blockchain
  template:
    metadata:
      labels:
        app: blockchain
    spec:
      containers:
      - name: blockchain
        image: blockchain-node
        ports:
        - containerPort: 5000  # P2P端口
        - containerPort: 5001  # API端口
        env:
        - name: PEER_NODES
          value: "blockchain-node-0.blockchain-service.default.svc.cluster.local:5000,blockchain-node-1.blockchain-service.default.svc.cluster.local:5000"
        volumeMounts:
        - name: blockchain-data
          mountPath: /app/data
      volumes:
      - name: blockchain-data
        persistentVolumeClaim:
          claimName: blockchain-pvc
```

### 2.2 创建Service

```yaml
apiVersion: v1
kind: Service
metadata:
  name: blockchain-service
spec:
  selector:
    app: blockchain
  ports:
    - name: p2p
      port: 5000
      targetPort: 5000
    - name: api
      port: 5001
      targetPort: 5001
  clusterIP: None  # 使用Headless Service
```

### 2.3 创建StatefulSet (替代Deployment, 如果需要稳定的网络标识)

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: blockchain-node
spec:
  serviceName: blockchain-service
  replicas: 3
  selector:
    matchLabels:
      app: blockchain
  template:
    metadata:
      labels:
        app: blockchain
    spec:
      containers:
      - name: blockchain
        image: blockchain-node
        ports:
        - containerPort: 5000
        - containerPort: 5001
        volumeMounts:
        - name: blockchain-data
          mountPath: /app/data
  volumeClaimTemplates:
  - metadata:
      name: blockchain-data
    spec:
      accessModes: [ "ReadWriteOnce" ]
      resources:
        requests:
          storage: 1Gi
```

### 2.4 创建PersistentVolumeClaim

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: blockchain-pvc
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
```

## 3. 数据库服务部署

由于项目使用了多种数据库(LevelDB, Redis, MongoDB)，可以:

1. **Redis**:
```bash
helm install redis bitnami/redis
```

2. **MongoDB**:
```bash
helm install mongodb bitnami/mongodb
```

3. **LevelDB**不需要单独部署，因为它会作为本地存储

## 4. 配置和部署

1. 创建Kubernetes ConfigMap存储配置:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: blockchain-config
data:
  config.yaml: |
    p2p_port: 5000
    api_port: 5001
    initial_peers: "blockchain-node-0.blockchain-service.default.svc.cluster.local:5000"
```

2. 应用所有配置:
```bash
kubectl apply -f blockchain-deployment.yaml
kubectl apply -f blockchain-service.yaml
kubectl apply -f blockchain-config.yaml
```

## 5. 网络配置考虑

1. **Ingress控制器** - 暴露API端口给外部访问
2. **网络策略** - 限制P2P通信只在区块链节点之间
3. **服务发现** - 使用Kubernetes DNS服务发现其他节点

## 6. 监控和日志

1. 部署Prometheus和Grafana监控节点状态
2. 配置ELK栈收集和分析日志

## 7. 扩展考虑

1. **水平扩展** - 增加更多节点副本
2. **自动恢复** - 配置健康检查和自动重启
3. **滚动更新** - 实现无缝升级区块链软件

这个部署方案提供了高可用性和可扩展性，同时保持了区块链网络的P2P特性。根据实际需求，您可能需要调整存储大小、资源限制和副本数量。
