import os
import certifi
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")

if not MONGO_URI:
    raise RuntimeError("MONGO_URI is missing from .env")

try:
    client = MongoClient(
        MONGO_URI,
        tls=True,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=10000,
        connectTimeoutMS=20000,
        socketTimeoutMS=20000
    )

    client.admin.command("ping")

    print("MongoDB connected successfully! ✅")

    db = client["college_attendance"]

except Exception as e:
    print("MongoDB connection failed ❌")
    print(e)
    raise