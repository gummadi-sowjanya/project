from database import fetch_one, execute_query
from werkzeug.security import generate_password_hash
import getpass

print("CHANGE OWNER DETAILS")

current_username = input("Enter current Owner username: ")
new_username = input("Enter new Owner username: ")
new_password = getpass.getpass("Enter new Owner password: ")

if not new_username.strip():
    print("Username cannot be empty.")

elif len(new_password) < 8:
    print("Password must contain at least 8 characters.")

else:
    owner = fetch_one(
        """
        SELECT user_id
        FROM UserAccount
        WHERE username = %s
          AND account_role = 'OWNER'
          AND status = 'ACTIVE'
        """,
        (current_username,)
    )

    if not owner:
        print("Active Owner account not found.")

    else:
        existing = fetch_one(
            "SELECT user_id FROM UserAccount WHERE username = %s",
            (new_username.strip(),)
        )

        if existing and existing['user_id'] != owner['user_id']:
            print("This username is already in use.")

        else:
            password_hash = generate_password_hash(new_password)

            execute_query(
                """
                UPDATE UserAccount
                SET username = %s,
                    password_hash = %s
                WHERE user_id = %s
                  AND account_role = 'OWNER'
                """,
                (
                    new_username.strip(),
                    password_hash,
                    owner['user_id']
                )
            )

            print("Owner username and password changed successfully.")