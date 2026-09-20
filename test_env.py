import os
from dotenv import load_dotenv

load_dotenv()

print("MONGO_URI found:", bool(os.getenv("MONGO_URI")))
print("SECRET_KEY found:", bool(os.getenv("SECRET_KEY")))