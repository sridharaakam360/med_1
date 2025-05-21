import mysql.connector
from mysql.connector import Error
from queue import Queue
from threading import Lock
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import os
import sys
from pathlib import Path

# Add the project root directory to Python path when running directly
if __name__ == '__main__':
    project_root = str(Path(__file__).parent.parent.parent)
    if project_root not in sys.path:
        sys.path.append(project_root)
    from app.config import Config
else:
    from app.config import Config

class DatabasePool:
    """Database connection pool implementation."""
    def __init__(self, max_connections=5):
        self.max_connections = max_connections
        self.connections = Queue(maxsize=max_connections)
        self.lock = Lock()
        self._fill_pool()

    def _fill_pool(self):
        """Initialize the connection pool."""
        for _ in range(self.max_connections):
            try:
                conn = mysql.connector.connect(**Config.DB_CONFIG)
                self.connections.put(conn)
            except Error as e:
                print(f"Error creating database connection: {e}")

    def get_connection(self):
        """Get a connection from the pool."""
        try:
            return self.connections.get(timeout=5)  # Add timeout to prevent infinite wait
        except:
            # If pool is exhausted, create a new connection
            try:
                conn = mysql.connector.connect(**Config.DB_CONFIG)
                return conn
            except Error as e:
                print(f"Error creating new connection: {e}")
                raise

    def return_connection(self, conn):
        """Return a connection to the pool."""
        if conn is None:
            return
        try:
            if hasattr(conn, 'in_transaction') and not conn.in_transaction:
                self.connections.put(conn, timeout=1)
            else:
                conn.close()
        except Exception:
            try:
                conn.close()
            except Exception:
                pass

    def close_all(self):
        """Close all connections in the pool."""
        while not self.connections.empty():
            try:
                conn = self.connections.get_nowait()
                conn.close()
            except:
                pass

class DBConnection:
    """Context manager for database connections."""
    def __init__(self, pool):
        self.pool = pool
        self.conn = None

    def __enter__(self):
        self.conn = self.pool.get_connection()
        return self.conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn is not None:
            try:
                if exc_type:
                    self.conn.rollback()
                else:
                    self.conn.commit()
            except Exception:
                pass  # Optionally log this
            finally:
                self.pool.return_connection(self.conn)

def init_db():
    """Initialize database and create tables."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Create users table
            try:
                cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    password VARCHAR(255) NOT NULL,
                    role ENUM('admin', 'user') NOT NULL DEFAULT 'user',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP NULL
                )''')
            except Error as e:
                if e.errno != 1050:  # Ignore "table already exists" error
                    raise
            
            # Create suppliers table
            try:
                cursor.execute('''CREATE TABLE IF NOT EXISTS suppliers (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    contact_person VARCHAR(100),
                    phone VARCHAR(20),
                    email VARCHAR(100),
                    address TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )''')
            except Error as e:
                if e.errno != 1050:
                    raise
            
            # Create products table
            try:
                cursor.execute('''CREATE TABLE IF NOT EXISTS products (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    description TEXT,
                    quantity INT NOT NULL DEFAULT 0,
                    min_quantity INT NOT NULL DEFAULT 10,
                    price DECIMAL(10,2) NOT NULL,
                    expiry_date DATE,
                    supplier_id INT,
                    is_scheduled BOOLEAN DEFAULT FALSE,
                    schedule_type ENUM('H', 'H1') NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (supplier_id) REFERENCES suppliers(id)
                )''')
            except Error as e:
                if e.errno != 1050:
                    raise
            
            # Create activity_logs table
            try:
                cursor.execute('''CREATE TABLE IF NOT EXISTS activity_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    action VARCHAR(50) NOT NULL,
                    details TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )''')
            except Error as e:
                if e.errno != 1050:
                    raise
            
            # Create bills table
            try:
                cursor.execute('''CREATE TABLE IF NOT EXISTS bills (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    customer_name VARCHAR(100) NOT NULL,
                    customer_phone VARCHAR(20),
                    customer_email VARCHAR(100),
                    total_amount DECIMAL(10,2) NOT NULL,
                    bill_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    payment_method ENUM('cash', 'card', 'upi') NOT NULL,
                    created_by INT,
                    FOREIGN KEY (created_by) REFERENCES users(id)
                )''')
            except Error as e:
                if e.errno != 1050:
                    raise
            
            # Create bill_items table
            try:
                cursor.execute('''CREATE TABLE IF NOT EXISTS bill_items (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    bill_id INT,
                    product_id INT,
                    quantity INT NOT NULL,
                    unit_price DECIMAL(10,2) NOT NULL,
                    is_scheduled BOOLEAN DEFAULT FALSE,
                    schedule_type ENUM('H', 'H1') NULL,
                    FOREIGN KEY (bill_id) REFERENCES bills(id),
                    FOREIGN KEY (product_id) REFERENCES products(id)
                )''')
            except Error as e:
                if e.errno != 1050:
                    raise
            
            # Create default admin user if none exists
            cursor.execute('SELECT COUNT(*) FROM users WHERE role = "admin"')
            if cursor.fetchone()[0] == 0:
                cursor.execute('''INSERT INTO users (username, email, password, role)
                                VALUES (%s, %s, %s, %s)''',
                             ('admin', 'admin@example.com', 
                              generate_password_hash('admin123'), 'admin'))
            
            conn.commit()
            print("Database initialized successfully")
            
    except Error as e:
        print(f"Error initializing database: {e}")
        raise
    finally:
        if 'conn' in locals():
            conn.close()

# Initialize connection pool
db_pool = DatabasePool()

def get_db():
    """Get a database connection from the pool."""
    return DBConnection(db_pool)

if __name__ == '__main__':
    print("Initializing database...")
    init_db() 