import mysql.connector
from config import Config

def get_db_connection():
    return mysql.connector.connect(
        host=Config.MYSQL_HOST,
        user=Config.MYSQL_USER,
        password=Config.MYSQL_PASSWORD,
        database=Config.MYSQL_DATABASE
    )


def fetch_all(query, values=None):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query, values or ())
        return cursor.fetchall()

    finally:
        cursor.close()
        connection.close()


def fetch_one(query, values=None):
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute(query, values or ())
        return cursor.fetchone()

    finally:
        cursor.close()
        connection.close()


def execute_query(query, values=None):
    connection = get_db_connection()
    cursor = connection.cursor()

    try:
        cursor.execute(query, values or ())
        connection.commit()
        return cursor.lastrowid

    except Exception:
        connection.rollback()
        raise

    finally:
        cursor.close()
        connection.close()