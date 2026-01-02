# backend/admin.py
import os
from passlib.context import CryptContext
from .db import admin_collection
from .config import MONGO_URI  # ensures dotenv loaded

# Use pbkdf2_sha256 (portable, avoids bcrypt Windows backend issues)
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")

def create_admin(username: str, password: str):
    if admin_collection.find_one({"username": username}):
        return {"status": "exists"}
    hashed_pw = pwd_context.hash(password)
    admin_collection.insert_one({"username": username, "password": hashed_pw})
    return {"status": "created"}

def verify_admin(username: str, password: str):
    admin = admin_collection.find_one({"username": username})
    if not admin:
        return False
    return pwd_context.verify(password, admin["password"])

def ensure_default_admin():
    user = os.getenv("ADMIN_USER", "admin")
    pw = os.getenv("ADMIN_PASS", "admin123")
    if not admin_collection.find_one({"username": user}):
        create_admin(user, pw)

# Ensure a default admin for demo
ensure_default_admin()
