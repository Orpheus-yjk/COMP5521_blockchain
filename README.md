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