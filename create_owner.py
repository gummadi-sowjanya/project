"""Create the first Owner login. Run: python create_owner.py"""
import getpass
import uuid
from werkzeug.security import generate_password_hash
from database import fetch_one, execute_query

if fetch_one("SELECT user_id FROM UserAccount WHERE account_role = 'OWNER' LIMIT 1"):
    print('An Owner account already exists. No new Owner was created.')
else:
    username = input('Owner username: ').strip()
    password = getpass.getpass('Owner password (minimum 8 characters): ')
    confirm = getpass.getpass('Confirm password: ')
    if not username or len(password) < 8 or password != confirm:
        raise SystemExit('Username/password invalid or passwords do not match.')
    execute_query(
        """INSERT INTO UserAccount
           (user_id, employee_role_id, username, password_hash, account_role, status)
           VALUES (%s, NULL, %s, %s, 'OWNER', 'ACTIVE')""",
        ('USR-' + uuid.uuid4().hex[:16], username, generate_password_hash(password))
    )
    print('Owner account created. You can now log in.')
