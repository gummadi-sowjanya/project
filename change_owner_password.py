from database import execute_query, fetch_one
from werkzeug.security import generate_password_hash

username = input("Enter Owner username: ")
new_password = input("Enter new password: ")

if len(new_password) < 8:
    print("Password must contain at least 8 characters.")
else:
    owner = fetch_one(
        """
        SELECT user_id FROM UserAccount
        WHERE username = %s AND account_role = 'OWNER'
        """,
        (username,)
    )

    if owner:
        password_hash = generate_password_hash(new_password)

        execute_query(
            """
            UPDATE UserAccount
            SET password_hash = %s
            WHERE user_id = %s
            """,
            (password_hash, owner['user_id'])
        )

        print("Owner password changed successfully.")
    else:
        print("Owner account not found.")