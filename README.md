# COMP5521_Project

COMP5521 DISTRIBUTED LEDGER  TECHNOLOGY, CRYPTOCURRENCY AND EPAYMENT Project Specification   

##### Objective:

Have an in-depth understanding on how the blockchain system works.  
Be able to write a UTXO (unspent transaction output) blockchain platform. 

# Goals

1. Blockchain Prototype: construct the blockchain system according to the 
   following structure. The block should have the following basic content. 
   a) Index: the height of the current block. 
   b) Timestamp. 
   c) Previous Block Hash. 
   d) Current Block Hash. e) Difficulty: the number of bits at the beginning of block hash, dynamic 
   change. 
   f) Nonce: the random number used to calculate the block hash. 
   g) Merkle root of transactions. 
   h) Data: transaction. 
2. Mining and UTXO: implement a dynamic-difficulty Proof-of-Work algorithm. 
   a) Design a Proof-of-Work algorithm. For example, adjust the nonce and 
   generate a hash until it has a hash with a leading number of zeros. 
   b) Achieve dynamic difficulty. For example, adjusting the difficulty of the 
   current block dynamically based on the time taken to generate the 
   previous (10, 20, or more) blocks. 
3. Transaction: implement pay-to-public-key-hash (P2PKH) transactions and 
   verify transactions. 
   a) Implement pay-to-public-key-hash (P2PKH) transactions. 
   b) Use asymmetric cryptography to create digital signatures and verify 
   transactions. 
4. Network: basic interactions and validation should be realized. 
   a) Create an API to broadcast the new blocks and get the blocks from the 
   other nodes. The API should allow a user to interact with the blockchain 
   by the HTTP request, socket, or different ports. 
   b) Achieve a function to check if the new blocks that we receive from other 
   miners are valid or not. (Hint: recompute the hash of the block and 
   compare it with the given hash of the block.) 
5. Storage: choose your database in the implementation. 
   a) Store the raw data of the whole blockchain in the disk. 
   b) Store the latest state (e.g., chain height, full node list, neighbor list) of the 
   blockchain in memory. 
   c) Store the transactions (UTXO) in a transaction pool. 
6. Wallet: manage all transactions that you can spend. 
   You could refer to some open-source projects to implement your blockchain 
   system but you must refer to them in your report. Otherwise, it could be seen as 
   plagiarism. 



# 项目描述

COMP5521分布式账本技术、加密货币和电子支付 期末项目介绍

# 目标： 

深入了解区块链系统的工作原理。能够编写一个UTXO（未花费交易输出）区块链平台。

区块链原型: 根据以下结构构建区块链系统。区块应包含以下基本内容。a) 索引：当前区块的高度。b) 时间戳。c) 上一个区块哈希。d) 当前区块哈希。e) 难度：区块哈希开头的位数，动态变化。f) 随机数：用于计算区块哈希的随机数。g) 交易的Merkle根。h) 数据：交易。 

挖矿和UTXO：实现动态难度的工作量证明算法。a) 设计一个工作量证明算法。例如，调整随机数并生成哈希，直到哈希以一定数量的零开头。b) 实现动态难度。例如，根据生成前（10、20或更多）个区块所需时间动态调整当前区块的难度。

交易：实现支付到公钥哈希（P2PKH）交易并验证交易。a) 实现支付到公钥哈希（P2PKH）交易。b) 使用非对称加密创建数字签名并验证交易。 

网络：应实现基本的交互和验证。a) 创建一个API，用于广播新区块并从其他节点获取区块。API应允许用户通过HTTP请求、套接字或不同端口与区块链进行交互。b) 实现一个功能，用于检查我们从其他矿工接收的新区块是否有效。（提示：重新计算区块的哈希并将其与区块的给定哈希进行比较。） 

存储：在实现中选择数据库。a) 将整个区块链的原始数据存储在磁盘中。b) 将区块链的最新状态（例如，链高度、完整节点列表、邻居列表）存储在内存中。c) 将交易（UTXO）存储在交易池中。 

钱包：管理所有可以花费的交易。

——您可以参考一些开源项目来实现您的区块链系统，但必须在报告中引用它们。否则可能被视为抄袭。
