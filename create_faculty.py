from werkzeug.security import generate_password_hash
from db import db


username = input("Enter faculty username: ").strip()
password = input("Enter faculty password: ").strip()


# Check if username already exists
existing_user = db.users.find_one({
    "username": username
})

if existing_user:
    print("Username already exists ❌")

else:

    faculty_user = {
        "username": username,
        "password": generate_password_hash(password),
        "role": "faculty"
    }

    db.users.insert_one(faculty_user)

    print("Faculty account created successfully! ✅")