from werkzeug.security import generate_password_hash
from db import db


username = input("Enter admin username: ")
password = input("Enter admin password: ")


existing_user = db.users.find_one({
    "username": username
})


if existing_user:
    print("Username already exists ❌")

else:
    hashed_password = generate_password_hash(password)

    db.users.insert_one({
        "username": username,
        "password": hashed_password,
        "role": "admin"
    })

    print("Admin account created successfully! ✅")