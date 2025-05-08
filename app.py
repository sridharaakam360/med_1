from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from datetime import datetime
import sqlite3
import os
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'your-secret-key'  # Replace with a secure key for production

# Database setup
# Use an absolute path for the database
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_DIR = os.path.join(BASE_DIR, 'database')
DB_PATH = os.path.join(DB_DIR, 'medical_shop.db')

def init_db():
    try:
        # Ensure the database directory exists
        if not os.path.exists(DB_DIR):
            os.makedirs(DB_DIR)
            logger.debug(f"Created database directory: {DB_DIR}")
        
        # Connect to the database and enable foreign key support
        conn = sqlite3.connect(DB_PATH)
        conn.execute('PRAGMA foreign_keys = ON')  # Enable foreign keys
        c = conn.cursor()
        
        # Create tables
        c.execute('''CREATE TABLE IF NOT EXISTS products (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     name TEXT NOT NULL,
                     quantity INTEGER NOT NULL,
                     price REAL NOT NULL,
                     expiry_date TEXT NOT NULL,
                     supplier_id INTEGER,
                     FOREIGN KEY(supplier_id) REFERENCES suppliers(id))''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS suppliers (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     name TEXT NOT NULL,
                     contact TEXT)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS bills (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     customer_name TEXT NOT NULL,
                     total_amount REAL NOT NULL,
                     bill_date TEXT NOT NULL)''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS bill_items (
                     id INTEGER PRIMARY KEY AUTOINCREMENT,
                     bill_id INTEGER,
                     product_id INTEGER,
                     quantity INTEGER,
                     FOREIGN KEY(bill_id) REFERENCES bills(id),
                     FOREIGN KEY(product_id) REFERENCES products(id))''')
        
        conn.commit()
        logger.debug(f"Database initialized successfully at {DB_PATH}")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise
    finally:
        conn.close()

# Test database connection before each route
def get_db_connection():
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('PRAGMA foreign_keys = ON')  # Enable foreign keys for this connection
        logger.debug("Database connection established")
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise

# Initialize the database when the module is loaded
init_db()  # Moved outside the if __name__ == '__main__': block

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/billing', methods=['GET', 'POST'])
def billing():
    conn = get_db_connection()
    c = conn.cursor()
    if request.method == 'POST':
        customer_name = request.form['customer_name']
        items = request.form.getlist('items[]')
        quantities = request.form.getlist('quantities[]')
        total_amount = 0
        bill_date = datetime.now().strftime('%Y-%m-%d')
        
        # Create bill
        c.execute('INSERT INTO bills (customer_name, total_amount, bill_date) VALUES (?, ?, ?)',
                  (customer_name, 0, bill_date))
        bill_id = c.lastrowid
        
        # Process items
        for prod_id, qty in zip(items, quantities):
            qty = int(qty)
            c.execute('SELECT price, quantity FROM products WHERE id = ?', (prod_id,))
            product = c.fetchone()
            if product and product[1] >= qty:
                price = product[0]
                total_amount += price * qty
                c.execute('UPDATE products SET quantity = quantity - ? WHERE id = ?', (qty, prod_id))
                c.execute('INSERT INTO bill_items (bill_id, product_id, quantity) VALUES (?, ?, ?)',
                          (bill_id, prod_id, qty))
        
        # Update total amount
        c.execute('UPDATE bills SET total_amount = ? WHERE id = ?', (total_amount, bill_id))
        conn.commit()
        flash('Bill created successfully!')
        return redirect(url_for('billing'))
    
    c.execute('SELECT id, name, price, quantity FROM products')
    products = c.fetchall()
    conn.close()
    return render_template('billing.html', products=products)

@app.route('/inventory', methods=['GET', 'POST'])
def inventory():
    conn = get_db_connection()
    c = conn.cursor()
    if request.method == 'POST':
        name = request.form['name']
        quantity = request.form['quantity']
        price = request.form['price']
        expiry_date = request.form['expiry_date']
        supplier_id = request.form['supplier_id'] or None
        c.execute('INSERT INTO products (name, quantity, price, expiry_date, supplier_id) VALUES (?, ?, ?, ?, ?)',
                  (name, quantity, price, expiry_date, supplier_id))
        conn.commit()
        flash('Product added successfully!')
        return redirect(url_for('inventory'))
    
    c.execute('SELECT p.id, p.name, p.quantity, p.price, p.expiry_date, s.name FROM products p LEFT JOIN suppliers s ON p.supplier_id = s.id')
    products = c.fetchall()
    c.execute('SELECT id, name FROM suppliers')
    suppliers = c.fetchall()
    conn.close()
    return render_template('inventory.html', products=products, suppliers=suppliers)

@app.route('/expiry')
def expiry():
    conn = get_db_connection()
    c = conn.cursor()
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute('SELECT id, name, quantity, expiry_date FROM products WHERE expiry_date <= ?', (today,))
    expired_products = c.fetchall()
    conn.close()
    return render_template('expiry.html', products=expired_products)

@app.route('/suppliers', methods=['GET', 'POST'])
def suppliers():
    conn = get_db_connection()
    c = conn.cursor()
    if request.method == 'POST':
        name = request.form['name']
        contact = request.form['contact']
        c.execute('INSERT INTO suppliers (name, contact) VALUES (?, ?)', (name, contact))
        conn.commit()
        flash('Supplier added successfully!')
        return redirect(url_for('suppliers'))
    
    c.execute('SELECT id, name, contact FROM suppliers')
    suppliers = c.fetchall()
    conn.close()
    return render_template('suppliers.html', suppliers=suppliers)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))