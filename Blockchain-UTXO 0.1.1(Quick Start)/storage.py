# -*- coding: utf-8 -*-

"""这是未完成的网络代码。
TODO:
    存储：在实现中选择数据库。
    - a) 将整个区块链的原始数据存储在磁盘中。
    - b) 将区块链的最新状态（例如，链高度、完整节点列表、邻居列表）存储在内存中。
    - c) 将交易（UTXO）存储在交易池中。
"""

__author__ = 'YJK'
__date__ = '2023-12-6'
import threading
import couchdb

class Singleton(object):
    _instance_lock = threading.Lock()
    __instance = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is None:
            with Singleton._instance_lock:
                cls.__instance = super(
                    Singleton, cls).__new__(cls)
        return cls.__instance


class DB(Singleton):
    def __init__(self, db_server_url = 'http://127.0.0.1:5984/', db_name='blockchain5521'):
        self._db_server_url = db_server_url
        self._server = couchdb.Server(self._db_server_url)
        self._db_name = db_name
        self._db = None

    @property
    def db(self):
        if not self._db:
            try:
                self._db = self._server[self._db_name]
            except couchdb.ResourceNotFound:
                self._db = self._server.create(self._db_name)
        return self._db

    def create(self, id, data):
        self.db[id] = data
        return id

    def __getattr__(self, name):
        return getattr(self.db, name)

    def __contains__(self, name):
        return self.db.__contains__(name)

    def __getitem__(self, key):
        return self.db[key]

    def __setitem__(self, key, value):
        self.db[key] = value

