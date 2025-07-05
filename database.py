
import os
import sqlite3
import psycopg2
import psycopg2.extras
from urllib.parse import urlparse

class DatabaseManager:
    def __init__(self):
        self.database_url = os.environ.get('DATABASE_URL')
        self.use_postgres = self.database_url is not None

    def get_connection(self):
        """Get database connection based on environment"""
        if self.use_postgres:
            url = urlparse(self.database_url)
            conn = psycopg2.connect(
                database=url.path[1:],
                user=url.username,
                password=url.password,
                host=url.hostname,
                port=url.port
            )
            return conn
        else:
            return sqlite3.connect('okharcha.db')

    def execute_query(self, query, params=None, fetch_one=False, fetch_all=False):
        """Execute query with proper parameter binding"""
        conn = self.get_connection()

        if self.use_postgres:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            # Convert ? to %s for PostgreSQL
            pg_query = query.replace('?', '%s')
            cursor.execute(pg_query, params or ())
        else:
            cursor = conn.cursor()
            cursor.execute(query, params or ())

        result = None
        if fetch_one:
            result = cursor.fetchone()
        elif fetch_all:
            result = cursor.fetchall()

        conn.commit()
        conn.close()

        return result

    def get_placeholder(self):
        """Get the correct parameter placeholder for the database"""
        return '%s' if self.use_postgres else '?'

# Global database manager instance
db = DatabaseManager()
