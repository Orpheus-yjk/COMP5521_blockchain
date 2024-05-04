# coding:utf-8
import binascii
import hashlib
import time

import ecdsa
# import db
subsidy = 1000  # reward for mining one block


class tx_output:
    def __init__(self, value, pub_key_hash=''):
        self.value = value   ## money / amount / token
        self.pub_key_hash = pub_key_hash

    ### 序列化
    def serialize(self):
        return self.__dict__

    # @classmethod
    # def deserialize(cls, data):
    #     value = data.get('value', 0)
    #     pub_key_hash = data.get('pub_key_hash', 0)
    #     return cls(value, pub_key_hash)

class tx_input:
    def __init__(self, txid, vout_to, pub_key):
        self.txid=txid
        self.vout = vout_to
        self.pubkey = pub_key
        self.signature = ''

    def serialize(self):
        return self.__dict__

class Transaction:
    ### tx是一条资金流， Tx == txs是一次完整的P2P交易，收集payer的所有Transaction信息，汇总给receiver
    def __init__(self, vins, vouts):    ##array of class tx_input, tx_output
        self.vins=vins
        self.vouts=vouts
        self.Txid= self.generate_Txid()   ##txid is str() make by hashlib.sha256
        self.sum_value=0
        for idx in range(len(vins)):
            self.sum_value = self.sum_value + vouts[idx].value

    def generate_Txid(self):
        # generate unique id for a tx (Input is a Transaction)
        ## serialize: class parameters ==>dict.  str: dict==>string
        vin_list= [str(vin.serialize()) for vin in self.vins]
        vouts_list = [str(vout.serialize()) for vout in self.vouts]

        concat_list = vin_list
        concat_list.extend(vouts_list)  ##str
        concat_list=''.join(concat_list)

        hash = hashlib.sha256(concat_list.encode()).hexdigest()  ###whatever hash function to do Txid
        ###also include random_number in persistence of the same Txid for content all the same
        return hashlib.sha256((hash+str(time.time())).encode()).hexdigest()

    def is_coinbase(self, _Tx):
        # if the Transcation _Tx only has one tx
        return len(_Tx.vins) == 1 and len(_Tx.vins[0].txid) == 0    #_Tx.vins[0].vout == block miner

    @classmethod
    ##使用cls在函数中独自创建一个另一个Tranaction类
    def create_coinbase_Tx(cls, noneaddresss, address_to, pub_key_hash=''):
        print("coin_noneaddress : %s" % (noneaddresss))
        _txinput = tx_input(noneaddresss, address_to, '')
        _txoutput = tx_output(subsidy, pub_key_hash)
            ### address_to can be either address(P2PK) or address_hash(P2PKH)

        Tx= cls([_txinput] , [_txoutput])
        return Tx

    def create_one_tx(self, Txid, address_receiver, value, input_pub_key, output_pub_key_hash):
        ###建立一个tx
        _txinput = tx_input(Txid, address_receiver, input_pub_key)
        _txoutput = tx_output(value, output_pub_key_hash)
        return _txinput, _txoutput

    def Transaction_self_copy(self):
        new_vins = []
        new_vouts = []
        for vin in self.vins:
            new_vins.append(tx_input(vin.txid, vin.vout, ''))

        for vout in self.vouts:
            new_vouts.append(tx_output(vout.value, vout.pub_key_hash))

        new_Transaction = Transaction(new_vins, new_vouts)
        return new_Transaction


    def sign(self):
        None




