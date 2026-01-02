from pymongo import MongoClient
try:
    from .config import MONGO_URI, DB_NAME
except ImportError:
    from config import MONGO_URI, DB_NAME

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
person_collection = db["person"]
admin_collection = db["admin"]
alerts_collection = db["alerts"]  # NEW: store realtime alerts

# Ensure indexes (idempotent)
try:
    person_collection.create_index("person_id", unique=True)
except Exception:
    pass
try:
    alerts_collection.create_index("ts")
    alerts_collection.create_index([("cam_id",1),("ts",-1)])
except Exception:
    pass
