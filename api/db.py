import os
from functools import lru_cache

from pymongo import ASCENDING, MongoClient
from pymongo.errors import ConfigurationError, ServerSelectionTimeoutError


class DatabaseConfigError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def get_client():
    uri = os.getenv("DATABASE_URL")
    if not uri:
        raise DatabaseConfigError("DATABASE_URL is not configured.")

    return MongoClient(
        uri,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=20000,
        uuidRepresentation="standard",
    )


def get_db():
    try:
        client = get_client()
        db_name = os.getenv("MONGO_DB_NAME", "RAGGPT")
        return client.get_default_database(default=db_name)
    except ConfigurationError as error:
        raise DatabaseConfigError(str(error)) from error


def check_connection():
    try:
        get_client().admin.command("ping")
    except ServerSelectionTimeoutError as error:
        raise DatabaseConfigError("Could not connect to MongoDB.") from error


@lru_cache(maxsize=1)
def ensure_indexes():
    db = get_db()
    db.users.create_index([("email", ASCENDING)], unique=True)
    db.documents.create_index([("user_id", ASCENDING), ("created_at", ASCENDING)])
    db.chunks.create_index([("user_id", ASCENDING), ("document_id", ASCENDING)])
    db.chunks.create_index([("user_id", ASCENDING), ("filename", ASCENDING)])
    return True
