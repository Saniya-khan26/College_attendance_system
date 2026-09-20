from werkzeug.security import generate_password_hash
from db import db


username = input("Enter admin username: ").strip()
new_password = input("Enter new admin password: ")

user = db.users.find_one({
    "username": username,
    "role": "admin"
})

if not user:
    print("Admin user not found ❌")

else:
    new_hashed_password = generate_password_hash(new_password)

    db.users.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password": new_hashed_password
            }
        }
    )

    print("Admin password reset successfully! ✅")