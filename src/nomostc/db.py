from pymongo import MongoClient
from pymongo.database import Database

from nomostc.settings import settings

_client: MongoClient | None = None


def get_db() -> Database:
    global _client
    if _client is None:
        _client = MongoClient(
            settings.mongo_uri,
            maxPoolSize=settings.mongo_max_pool_size,
            minPoolSize=settings.mongo_min_pool_size,
        )
    return _client[settings.mongo_db]


def close_db() -> None:
    """Close the MongoDB client and release pool connections. Call on app shutdown."""
    global _client
    if _client is not None:
        _client.close()
        _client = None
