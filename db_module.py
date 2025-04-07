"""
数据库模型。
"""

__author__ = 'YJK developer'
__date__ = '2025-04'

import json
import logging
from datetime import datetime, timedelta
from typing import Union, List, Dict, Optional

import plyvel
import redis
from pymongo import MongoClient, ASCENDING, DESCENDING
from pymongo.errors import PyMongoError

class LevelDBModule:
    """LevelDB数据库模块，用于存储区块链数据"""

    def __init__(self, db_name: str = "blockchain_db"):
        """
        初始化LevelDB数据库
        :param db_name: 数据库名称（默认：blockchain_db）
        """
        self.db_name = db_name
        self._db = None
        self._initialize_db()

    def _initialize_db(self):
        """初始化数据库连接"""
        try:
            self._db = plyvel.DB(self.db_name, create_if_missing=True)
            logging.info(f"成功连接LevelDB数据库：{self.db_name}")
        except Exception as e:
            logging.error(f"数据库连接失败: {str(e)}")
            raise RuntimeError("数据库初始化失败")

    def save_block(self, block_hash: str, block_data: dict):
        """
        保存区块数据
        :param block_hash: 区块哈希（键）
        :param block_data: 区块序列化数据（值）
        """
        try:
            serialized = json.dumps(block_data).encode('utf-8')
            self._db.put(block_hash.encode('utf-8'), serialized)
            logging.debug(f"区块 {block_hash[:8]}... 保存成功")
        except Exception as e:
            logging.error(f"数据保存失败: {str(e)}")
            raise

    def get_block(self, block_hash: str) -> Optional[dict]:
        """
        获取区块数据
        :param block_hash: 要查询的区块哈希
        :return: 反序列化的区块数据字典
        """
        try:
            data = self._db.get(block_hash.encode('utf-8'))
            return json.loads(data.decode('utf-8')) if data else None
        except Exception as e:
            logging.error(f"数据读取失败: {str(e)}")
            return None

    def delete_block(self, block_hash: str):
        """删除指定区块"""
        try:
            self._db.delete(block_hash.encode('utf-8'))
            logging.warning(f"区块 {block_hash[:8]}... 已删除")
        except Exception as e:
            logging.error(f"删除操作失败: {str(e)}")
            raise

    def get_all_blocks(self) -> dict:
        """获取全部区块数据"""
        blocks = {}
        try:
            for key, value in self._db:
                blocks[key.decode('utf-8')] = json.loads(value.decode('utf-8'))
            return blocks
        except Exception as e:
            logging.error(f"全量数据读取失败: {str(e)}")
            return {}

    def close(self):
        """关闭数据库连接"""
        if self._db:
            self._db.close()
            logging.info("数据库连接已关闭")

    def __enter__(self):
        """支持上下文管理器"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文自动关闭"""
        self.close()


class RedisModule:
    """Redis数据库模块，用于存储区块链变量和列表数据"""

    def __init__(self,
                 db_name: str = "blockchain_meta",
                 host: str = "localhost",
                 port: int = 6379,
                 password: str = None):
        """
        初始化Redis连接
        :param db_name: 数据库名称（默认：blockchain_meta）
        :param host: Redis主机地址（默认：localhost）
        :param port: Redis端口（默认：6379）
        :param password: 认证密码（可选）
        """
        self.db_name = db_name  # 用作Redis键前缀
        self.client = redis.StrictRedis(
            host=host,
            port=port,
            password=password,
            decode_responses=True,  # 自动解码返回字符串
            socket_timeout=5  # 超时设置
        )
        try:
            self.client.ping()  # 测试连接
            logging.info(f"Redis连接成功 {host}:{port}/{db_name}")
        except redis.ConnectionError as e:
            logging.error(f"Redis连接失败: {str(e)}")
            raise RuntimeError("无法连接Redis服务器")

    # ----------------- 通用键管理 -----------------
    def _get_key(self, key: str) -> str:
        """为键添加数据库名前缀"""
        return f"{self.db_name}:{key}"

    # ----------------- 变量操作 -----------------
    def save_var(self, key: str, value: Union[str, int, float]) -> bool:
        """
        保存变量数据（字符串/数值）
        :param key: 变量名（如"chain_height"）
        :param value: 变量值
        :return: 是否成功
        """
        try:
            return bool(self.client.set(self._get_key(key), value))
        except redis.RedisError as e:
            logging.error(f"保存变量失败 {key}: {str(e)}")
            return False

    def get_var(self, key: str, default=None) -> Optional[Union[str, int, float]]:
        """
        获取变量值
        :param key: 变量名
        :param default: 默认值（当键不存在时返回）
        :return: 变量值或None
        """
        try:
            val = self.client.get(self._get_key(key))
            return val if val is not None else default
        except redis.RedisError as e:
            logging.error(f"获取变量失败 {key}: {str(e)}")
            return default

    def incr_var(self, key: str, amount: int = 1) -> Optional[int]:
        """原子递增整型变量"""
        try:
            return self.client.incrby(self._get_key(key), amount)
        except redis.RedisError as e:
            logging.error(f"递增变量失败 {key}: {str(e)}")
            return None

    # ----------------- 列表操作 -----------------
    def push_list(self, list_name: str, *values: str) -> bool:
        """
        向列表尾部添加元素
        :param list_name: 列表名称（如"peer_nodes"）
        :param values: 要添加的值
        :return: 是否成功
        """
        try:
            return bool(self.client.rpush(self._get_key(list_name), *values))
        except redis.RedisError as e:
            logging.error(f"列表添加失败 {list_name}: {str(e)}")
            return False

    def get_list(self, list_name: str, start: int = 0, end: int = -1) -> List[str]:
        """
        获取列表片段
        :param list_name: 列表名称
        :param start: 起始索引
        :param end: 结束索引（-1表示到最后）
        :return: 元素列表
        """
        try:
            return self.client.lrange(self._get_key(list_name), start, end)
        except redis.RedisError as e:
            logging.error(f"获取列表失败 {list_name}: {str(e)}")
            return []

    def remove_from_list(self, list_name: str, value: str, count: int = 0) -> bool:
        """
        从列表中删除元素
        :param list_name: 列表名称
        :param value: 要删除的值
        :param count: 删除数量（0表示全部）
        :return: 是否成功
        """
        try:
            removed = self.client.lrem(self._get_key(list_name), count, value)
            return removed > 0
        except redis.RedisError as e:
            logging.error(f"列表删除失败 {list_name}: {str(e)}")
            return False

    # ----------------- 哈希表操作 -----------------
    def save_hash(self, hash_name: str, data: Dict[str, str]) -> bool:
        """
        保存哈希表数据（如区块头信息）
        :param hash_name: 哈希表名
        :param data: 键值对字典
        :return: 是否成功
        """
        try:
            return bool(self.client.hmset(self._get_key(hash_name), data))
        except redis.RedisError as e:
            logging.error(f"保存哈希失败 {hash_name}: {str(e)}")
            return False

    def get_hash(self, hash_name: str) -> Dict[str, str]:
        """
        获取整个哈希表
        :param hash_name: 哈希表名
        :return: 键值对字典
        """
        try:
            return self.client.hgetall(self._get_key(hash_name))
        except redis.RedisError as e:
            logging.error(f"获取哈希失败 {hash_name}: {str(e)}")
            return {}

    # ----------------- 实用方法 -----------------
    def clear_all(self) -> bool:
        """清空当前数据库所有数据"""
        try:
            self.client.flushdb()
            return True
        except redis.RedisError as e:
            logging.error(f"清空数据库失败: {str(e)}")
            return False

    def close(self):
        """关闭连接（Redis连接池会自动管理，通常不需要手动调用）"""
        self.client.close()


class MongoDBModule:
    """MongoDB UTXO存储模块"""

    def __init__(self,
                 db_name: str = "utxo_db",
                 host: str = "localhost",
                 port: int = 27017,
                 username: str = None,
                 password: str = None):
        """
        初始化MongoDB连接
        :param db_name: 数据库名称（默认：utxo_db）
        :param host: 主机地址（默认：localhost）
        :param port: 端口号（默认：27017）
        :param username: 认证用户名（可选）
        :param password: 认证密码（可选）
        """
        self.connection_str = f"mongodb://{host}:{port}"
        if username and password:
            self.connection_str = f"mongodb://{username}:{password}@{host}:{port}"

        try:
            self.client = MongoClient(self.connection_str, serverSelectionTimeoutMS=5000)
            self.client.server_info()  # 测试连接
            self.db = self.client[db_name]
            self.utxo_collection = self.db["utxos"]
            self._create_indexes()
            logging.info(f"MongoDB连接成功 {host}:{port}/{db_name}")
        except PyMongoError as e:
            logging.error(f"MongoDB连接失败: {str(e)}")
            raise RuntimeError("数据库连接失败")

    def _create_indexes(self):
        """创建查询索引"""
        self.utxo_collection.create_index([("txid", ASCENDING), ("vout_index", ASCENDING)], unique=True)
        self.utxo_collection.create_index([("address", ASCENDING)])
        self.utxo_collection.create_index([("amount", DESCENDING)])

    # ----------------- 核心UTXO操作 -----------------
    def add_utxo(self, txid: str, vout_index: int, amount: float, address: str, script_pubkey: str) -> bool:
        """
        添加UTXO记录
        :param txid: 交易ID
        :param vout_index: 输出索引
        :param amount: 金额
        :param address: 接收地址
        :param script_pubkey: 锁定脚本
        :return: 是否成功
        """
        doc = {
            "txid": txid,
            "vout_index": vout_index,
            "amount": amount,
            "address": address,
            "script_pubkey": script_pubkey,
            "created_at": datetime.utcnow(),
            "spent": False
        }
        try:
            result = self.utxo_collection.insert_one(doc)
            return result.acknowledged
        except PyMongoError as e:
            logging.error(f"UTXO添加失败 {txid}:{vout_index} - {str(e)}")
            return False

    def mark_as_spent(self, txid: str, vout_index: int) -> bool:
        """
        标记UTXO为已花费
        :param txid: 交易ID
        :param vout_index: 输出索引
        :return: 是否成功
        """
        try:
            result = self.utxo_collection.update_one(
                {"txid": txid, "vout_index": vout_index},
                {"$set": {"spent": True, "spent_at": datetime.utcnow()}}
            )
            return result.modified_count > 0
        except PyMongoError as e:
            logging.error(f"UTXO标记失败 {txid}:{vout_index} - {str(e)}")
            return False

    def get_utxo(self, txid: str, vout_index: int) -> Optional[Dict]:
        """
        获取特定UTXO
        :param txid: 交易ID
        :param vout_index: 输出索引
        :return: UTXO文档或None
        """
        try:
            return self.utxo_collection.find_one({
                "txid": txid,
                "vout_index": vout_index,
                "spent": False
            })
        except PyMongoError as e:
            logging.error(f"UTXO查询失败 {txid}:{vout_index} - {str(e)}")
            return None

    def get_utxos_by_address(self, address: str, min_amount: float = None) -> List[Dict]:
        """
        获取地址下的所有未花费UTXO
        :param address: 钱包地址
        :param min_amount: 最小金额筛选（可选）
        :return: UTXO列表
        """
        query = {"address": address, "spent": False}
        if min_amount is not None:
            query["amount"] = {"$gte": min_amount}

        try:
            return list(self.utxo_collection.find(query).sort("amount", DESCENDING))
        except PyMongoError as e:
            logging.error(f"地址UTXO查询失败 {address} - {str(e)}")
            return []

    def get_balance(self, address: str) -> float:
        """
        计算地址余额
        :param address: 钱包地址
        :return: 余额总和
        """
        try:
            pipeline = [
                {"$match": {"address": address, "spent": False}},
                {"$group": {"_id": None, "total": {"$sum": "$amount"}}}
            ]
            result = list(self.utxo_collection.aggregate(pipeline))
            return result[0]["total"] if result else 0.0
        except PyMongoError as e:
            logging.error(f"余额计算失败 {address} - {str(e)}")
            return 0.0

    # ----------------- 批量操作 -----------------
    def bulk_add_utxos(self, utxos: List[Dict]) -> bool:
        """批量添加UTXO"""
        try:
            result = self.utxo_collection.insert_many(utxos)
            return result.acknowledged
        except PyMongoError as e:
            logging.error(f"批量UTXO添加失败 - {str(e)}")
            return False

    def bulk_spend_utxos(self, txid_vout_pairs: List[tuple]) -> int:
        """
        批量标记UTXO为已花费
        :param txid_vout_pairs: [(txid1, vout1), (txid2, vout2)...]
        :return: 成功更新的数量
        """
        try:
            operations = [
                {
                    "update_many": {
                        "filter": {"txid": txid, "vout_index": vout},
                        "update": {"$set": {"spent": True, "spent_at": datetime.utcnow()}}
                    }
                } for txid, vout in txid_vout_pairs
            ]
            result = self.utxo_collection.bulk_write(operations)
            return result.modified_count
        except PyMongoError as e:
            logging.error(f"批量UTXO标记失败 - {str(e)}")
            return 0

    # ----------------- 维护操作 -----------------
    def cleanup_spent_utxos(self, older_than_days: int = 30) -> int:
        """
        清理已花费的UTXO（归档历史数据）
        :param older_than_days: 保留最近N天的数据
        :return: 删除的记录数
        """
        cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
        try:
            result = self.utxo_collection.delete_many({
                "spent": True,
                "spent_at": {"$lt": cutoff_date}
            })
            return result.deleted_count
        except PyMongoError as e:
            logging.error(f"UTXO清理失败 - {str(e)}")
            return 0

    def close(self):
        """关闭数据库连接"""
        self.client.close()


# 使用示例
if __name__ == "__main__":

    # LevelDB
    # 配置日志
    logging.basicConfig(level=logging.INFO)

    # 初始化数据库
    db = LevelDBModule()

    # 示例区块数据
    sample_block = {
        "header": {
            "index": 1,
            "prev_hash": "0000000000000000",
            "merkle_root": "a1b2c3d4e5",
            "timestamp": 1630000000,
            "difficulty": 4,
            "nonce": 12345
        },
        "transactions": [
            {"txid": "tx1", "value": 50},
            {"txid": "tx2", "value": 30}
        ]
    }

    # 保存区块
    db.save_block("abcd1234efgh5678", sample_block)

    # 查询区块
    block = db.get_block("abcd1234efgh5678")
    print("查询结果：", block)

    # 关闭连接
    db.close()

    # Redis
    logging.basicConfig(level=logging.INFO)

    # 初始化
    redis_db = RedisModule(db_name="yjk_chain", port=6379)

    # 变量操作示例
    redis_db.save_var("chain_height", 100)  # 保存链高度
    height = redis_db.get_var("chain_height", default=0)
    print(f"当前链高度: {height}")

    # 列表操作示例
    redis_db.push_list("peer_nodes", "node1:5000", "node2:5000")  # 添加节点
    nodes = redis_db.get_list("peer_nodes")
    print(f"邻居节点: {nodes}")

    # 哈希表操作示例
    block_header = {
        "prev_hash": "0000abc...",
        "merkle_root": "123def...",
        "nonce": "12345"
    }
    redis_db.save_hash("block:100", block_header)
    header = redis_db.get_hash("block:100")
    print(f"区块头数据: {header}")

    # 清理测试数据
    redis_db.clear_all()
    redis_db.close()

    # mongodb
    logging.basicConfig(level=logging.INFO)

    # 初始化
    mongo_db = MongoDBModule(db_name="yjk_blockchain")

    # 添加UTXO示例
    utxo_data = {
        "txid": "a1b2c3d4e5f67890",
        "vout_index": 0,
        "amount": 3.5,
        "address": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
        "script_pubkey": "76a91462e907b15cbf27d5425399ebf6f0fb50ebb88f1888ac"
    }
    mongo_db.add_utxo(**utxo_data)

    # 查询地址UTXO
    utxos = mongo_db.get_utxos_by_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")
    print(f"找到 {len(utxos)} 个UTXO")

    # 标记为已花费
    mongo_db.mark_as_spent("a1b2c3d4e5f67890", 0)

    # 关闭连接
    mongo_db.close()