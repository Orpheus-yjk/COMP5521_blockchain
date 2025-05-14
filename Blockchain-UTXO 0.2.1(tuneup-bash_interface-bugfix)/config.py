# config.py

DB_CONFIG = {
    'leveldb': {
        'db_name': 'blockchain_db'
    },
    'redis': {
        'host': 'localhost',
        'port': 6379,
        'password': None,
        'db_name': 'blockchain_meta'
    },
    'mongodb': {
        'host': 'localhost',
        'port': 27017,
        'username': None,
        'password': None,
        'db_name': 'utxo_db'
    }
}

def validate_db_config():
    required_fields = {
        'leveldb': ['db_name'],
        'redis': ['host', 'port', 'db_name'],
        'mongodb': ['host', 'port', 'db_name']
    }

    for db_type, fields in required_fields.items():
        if db_type not in DB_CONFIG:
            raise ValueError(f"缺少 {db_type} 配置")
        for field in fields:
            if field not in DB_CONFIG[db_type]:
                raise ValueError(f"{db_type} 配置缺少 {field} 字段")