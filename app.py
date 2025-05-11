import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_wtf.csrf import CSRFProtect
from wtforms import StringField, IntegerField, FloatField, DateField, SelectField
from wtforms.validators import DataRequired, NumberRange
from flask_wtf import FlaskForm
import sqlite3
from werkzeug.security import generate_password_hash

# Configure logging with rotation
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

app = Flask(__name__)

# Load configuration from environment variables
# Use a fixed secret key in production for stable sessions
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
if not app.config['SECRET_KEY']:
    app.config['SECRET_KEY'] = '51f52814d7bb5d8d7cb5ec61a9b05f237c6ca5f87cc21cdd'  # Fallback, change in production
    logger.warning("Using fallback SECRET_KEY. Set a proper SECRET_KEY in environment variables.")

# Ensure sessions persist by setting the session type
app.config['SESSION_TYPE'] = 'filesystem'
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_TIME_LIMIT'] = None  # No time limit for CSRF tokens

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Database setup
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_DIR = os.path.join(BASE_DIR, 'database')
DB_PATH = os.environ.get('DB_PATH', os.path.join(DB_DIR, 'medical_shop.db'))

def init_db():
    """Initialize the SQLite database and create necessary tables."""
    try:
        if not os.path.exists(DB_DIR):
            os.makedirs(DB_DIR)
            logger.debug(f"Created database directory: {DB_DIR}")

        if os.path.exists(DB_PATH):
            try:
                with sqlite3.connect(DB_PATH) as conn:
                    c = conn.cursor()
                    c.execute('SELECT 1')
                    logger.debug(f"Existing database file is valid: {DB_PATH}")
            except sqlite3.DatabaseError as e:
                logger.warning(f"Invalid database file: {e}. Recreating.")
                os.remove(DB_PATH)
        else:
            logger.debug(f"Creating new database at {DB_PATH}")

        with sqlite3.connect(DB_PATH) as conn:
            conn.execute('PRAGMA foreign_keys = ON')
            c = conn.cursor()
            
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
            logger.debug(f"Database initialized at {DB_PATH}")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise

def get_db_connection():
    """Get a database connection with foreign keys enabled."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('PRAGMA foreign_keys = ON')
        logger.debug("Database connection established")
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise

# Initialize database
init_db()

# Forms for validation
class ProductForm(FlaskForm):
    name = StringField('Product Name', validators=[DataRequired()])
    quantity = IntegerField('Quantity', validators=[DataRequired(), NumberRange(min=0)])
    price = FloatField('Price', validators=[DataRequired(), NumberRange(min=0)])
    expiry_date = DateField('Expiry Date', validators=[DataRequired()])
    supplier_id = SelectField('Supplier', coerce=int)

class SupplierForm(FlaskForm):
    name = StringField('Supplier Name', validators=[DataRequired()])
    contact = StringField('Contact Details', validators=[DataRequired()])

class BillingForm(FlaskForm):
    customer_name = StringField('Customer Name', validators=[DataRequired()])

@app.route('/')
def index():
    """Render the homepage with dashboard summary."""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            # Total products
            c.execute('SELECT COUNT(*) FROM products')
            products_count = c.fetchone()[0]
            # Expired products
            today = datetime.now().strftime('%Y-%m-%d')
            c.execute('SELECT COUNT(*) FROM products WHERE expiry_date <= ?', (today,))
            expired_count = c.fetchone()[0]
            # Recent bills (last 7 days)
            seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            c.execute('SELECT COUNT(*) FROM bills WHERE bill_date >= ?', (seven_days_ago,))
            bills_count = c.fetchone()[0]
        return render_template('index.html', products_count=products_count, expired_count=expired_count, bills_count=bills_count)
    except Exception as e:
        logger.error(f"Error fetching dashboard data: {e}")
        flash('An error occurred while loading the dashboard.', 'error')
        return render_template('index.html')

@app.route('/billing', methods=['GET', 'POST'])
def billing():
    """Handle billing: display products and process bill creation."""
    form = BillingForm()
    today = datetime.now().strftime('%Y-%m-%d')
    if request.method == 'POST' and form.validate_on_submit():
        try:
            with get_db_connection() as conn:
                c = conn.cursor()
                customer_name = form.customer_name.data
                items = request.form.getlist('items[]')
                quantities = request.form.getlist('quantities[]')
                total_amount = 0
                bill_date = datetime.now().strftime('%Y-%m-%d')

                # Validate items and quantities
                if not items or not quantities or len(items) != len(quantities):
                    flash('Invalid items or quantities provided.', 'error')
                    return redirect(url_for('billing'))

                # Create bill
                c.execute('INSERT INTO bills (customer_name, total_amount, bill_date) VALUES (?, ?, ?)',
                          (customer_name, 0, bill_date))
                bill_id = c.lastrowid

                # Process items
                for prod_id, qty in zip(items, quantities):
                    try:
                        qty = int(qty)
                        if qty <= 0:
                            flash(f"Quantity must be positive for product ID {prod_id}.", 'error')
                            continue
                        c.execute('SELECT price, quantity FROM products WHERE id = ?', (prod_id,))
                        product = c.fetchone()
                        if not product:
                            flash(f"Product ID {prod_id} not found.", 'error')
                            continue
                        if product[1] < qty:
                            flash(f"Not enough stock for product ID {prod_id}. Available: {product[1]}.", 'error')
                            continue
                        price = product[0]
                        total_amount += price * qty
                        c.execute('UPDATE products SET quantity = quantity - ? WHERE id = ?', (qty, prod_id))
                        c.execute('INSERT INTO bill_items (bill_id, product_id, quantity) VALUES (?, ?, ?)',
                                  (bill_id, prod_id, qty))
                    except ValueError:
                        flash(f"Invalid quantity for product ID {prod_id}.", 'error')
                        continue

                # Update total amount
                c.execute('UPDATE bills SET total_amount = ? WHERE id = ?', (total_amount, bill_id))
                conn.commit()
                flash('Bill created successfully!', 'success')
                return redirect(url_for('billing'))
        except Exception as e:
            logger.error(f"Error creating bill: {e}")
            flash('An error occurred while creating the bill.', 'error')
            return redirect(url_for('billing'))

    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT id, name, price, quantity FROM products WHERE quantity > 0')
        products = c.fetchall()
    return render_template('billing.html', form=form, products=products, today=today)

@app.route('/bill_history')
def bill_history():
    """Display all past bills."""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT b.id, b.customer_name, b.total_amount, b.bill_date,
                         bi.product_id, bi.quantity, p.name, p.price
                         FROM bills b
                         LEFT JOIN bill_items bi ON b.id = bi.bill_id
                         LEFT JOIN products p ON bi.product_id = p.id
                         ORDER BY b.bill_date DESC''')
            bills = c.fetchall()
            # Group bills by bill_id for easier rendering
            bill_dict = {}
            for bill in bills:
                bill_id = bill[0]
                if bill_id not in bill_dict:
                    bill_dict[bill_id] = {
                        'customer_name': bill[1],
                        'total_amount': bill[2],
                        'bill_date': bill[3],
                        'items': []
                    }
                if bill[4]:  # If there's a bill item
                    bill_dict[bill_id]['items'].append({
                        'product_name': bill[6],
                        'quantity': bill[5],
                        'price': bill[7]
                    })
            return render_template('bill_history.html', bills=bill_dict.values())
    except Exception as e:
        logger.error(f"Error fetching bill history: {e}")
        flash('An error occurred while fetching bill history.', 'error')
        return redirect(url_for('index'))

@app.route('/inventory', methods=['GET', 'POST'])
def inventory():
    """Manage inventory: add, edit, delete products."""
    form = ProductForm()
    today = datetime.now().strftime('%Y-%m-%d')
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT id, name FROM suppliers')
        suppliers = c.fetchall()
        form.supplier_id.choices = [(0, 'Select Supplier (Optional)')] + [(s[0], s[1]) for s in suppliers]

        if request.method == 'POST' and form.validate_on_submit():
            try:
                name = form.name.data
                quantity = form.quantity.data
                price = form.price.data
                expiry_date = form.expiry_date.data.strftime('%Y-%m-%d')
                supplier_id = form.supplier_id.data if form.supplier_id.data != 0 else None

                c.execute('INSERT INTO products (name, quantity, price, expiry_date, supplier_id) VALUES (?, ?, ?, ?, ?)',
                          (name, quantity, price, expiry_date, supplier_id))
                conn.commit()
                flash('Product added successfully!', 'success')
                return redirect(url_for('inventory'))
            except Exception as e:
                logger.error(f"Error adding product: {e}")
                flash('An error occurred while adding the product.', 'error')

        c.execute('SELECT p.id, p.name, p.quantity, p.price, p.expiry_date, s.name FROM products p LEFT JOIN suppliers s ON p.supplier_id = s.id')
        products = c.fetchall()
    return render_template('inventory.html', form=form, products=products, suppliers=suppliers, today=today)

@app.route('/inventory/edit/<int:product_id>', methods=['GET', 'POST'])
def edit_product(product_id):
    """Edit a product."""
    form = ProductForm()
    today = datetime.now().strftime('%Y-%m-%d')
    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT id, name FROM suppliers')
        suppliers = c.fetchall()
        form.supplier_id.choices = [(0, 'Select Supplier (Optional)')] + [(s[0], s[1]) for s in suppliers]

        if request.method == 'GET':
            c.execute('SELECT name, quantity, price, expiry_date, supplier_id FROM products WHERE id = ?', (product_id,))
            product = c.fetchone()
            if not product:
                flash('Product not found.', 'error')
                return redirect(url_for('inventory'))
            form.name.data = product[0]
            form.quantity.data = product[1]
            form.price.data = product[2]
            form.expiry_date.data = datetime.strptime(product[3], '%Y-%m-%d')
            form.supplier_id.data = product[4] if product[4] else 0

        if request.method == 'POST' and form.validate_on_submit():
            try:
                name = form.name.data
                quantity = form.quantity.data
                price = form.price.data
                expiry_date = form.expiry_date.data.strftime('%Y-%m-%d')
                supplier_id = form.supplier_id.data if form.supplier_id.data != 0 else None

                c.execute('UPDATE products SET name = ?, quantity = ?, price = ?, expiry_date = ?, supplier_id = ? WHERE id = ?',
                          (name, quantity, price, expiry_date, supplier_id, product_id))
                conn.commit()
                flash('Product updated successfully!', 'success')
                return redirect(url_for('inventory'))
            except Exception as e:
                logger.error(f"Error updating product: {e}")
                flash('An error occurred while updating the product.', 'error')

        return render_template('edit_product.html', form=form, product_id=product_id, suppliers=suppliers, today=today)

@app.route('/inventory/delete/<int:product_id>', methods=['POST'])
def delete_product(product_id):
    """Delete a product."""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('DELETE FROM products WHERE id = ?', (product_id,))
            conn.commit()
            flash('Product deleted successfully!', 'success')
    except Exception as e:
        logger.error(f"Error deleting product: {e}")
        flash('An error occurred while deleting the product.', 'error')
    return redirect(url_for('inventory'))

@app.route('/expiry')
def expiry():
    """Show expired products."""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            today = datetime.now().strftime('%Y-%m-%d')
            c.execute('SELECT id, name, quantity, expiry_date FROM products WHERE expiry_date <= ?', (today,))
            expired_products = c.fetchall()
        return render_template('expiry.html', products=expired_products)
    except Exception as e:
        logger.error(f"Error fetching expired products: {e}")
        flash('An error occurred while fetching expired products.', 'error')
        return redirect(url_for('index'))

@app.route('/suppliers', methods=['GET', 'POST'])
def suppliers():
    """Manage suppliers: add, edit, delete."""
    form = SupplierForm()
    if request.method == 'POST' and form.validate_on_submit():
        try:
            with get_db_connection() as conn:
                c = conn.cursor()
                name = form.name.data
                contact = form.contact.data
                c.execute('INSERT INTO suppliers (name, contact) VALUES (?, ?)', (name, contact))
                conn.commit()
                flash('Supplier added successfully!', 'success')
                return redirect(url_for('suppliers'))
        except Exception as e:
            logger.error(f"Error adding supplier: {e}")
            flash('An error occurred while adding the supplier.', 'error')

    with get_db_connection() as conn:
        c = conn.cursor()
        c.execute('SELECT id, name, contact FROM suppliers')
        suppliers = c.fetchall()
    return render_template('suppliers.html', form=form, suppliers=suppliers)

@app.route('/suppliers/edit/<int:supplier_id>', methods=['GET', 'POST'])
def edit_supplier(supplier_id):
    """Edit a supplier."""
    form = SupplierForm()
    with get_db_connection() as conn:
        c = conn.cursor()
        if request.method == 'GET':
            c.execute('SELECT name, contact FROM suppliers WHERE id = ?', (supplier_id,))
            supplier = c.fetchone()
            if not supplier:
                flash('Supplier not found.', 'error')
                return redirect(url_for('suppliers'))
            form.name.data = supplier[0]
            form.contact.data = supplier[1]

        if request.method == 'POST' and form.validate_on_submit():
            try:
                name = form.name.data
                contact = form.contact.data
                c.execute('UPDATE suppliers SET name = ?, contact = ? WHERE id = ?', (name, contact, supplier_id))
                conn.commit()
                flash('Supplier updated successfully!', 'success')
                return redirect(url_for('suppliers'))
            except Exception as e:
                logger.error(f"Error updating supplier: {e}")
                flash('An error occurred while updating the supplier.', 'error')

        return render_template('edit_supplier.html', form=form, supplier_id=supplier_id)

@app.route('/suppliers/delete/<int:supplier_id>', methods=['POST'])
def delete_supplier(supplier_id):
    """Delete a supplier."""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            # Check if supplier is linked to any products
            c.execute('SELECT COUNT(*) FROM products WHERE supplier_id = ?', (supplier_id,))
            product_count = c.fetchone()[0]
            if product_count > 0:
                flash('Cannot delete supplier. They are linked to existing products.', 'error')
                return redirect(url_for('suppliers'))
            c.execute('DELETE FROM suppliers WHERE id = ?', (supplier_id,))
            conn.commit()
            flash('Supplier deleted successfully!', 'success')
    except Exception as e:
        logger.error(f"Error deleting supplier: {e}")
        flash('An error occurred while deleting the supplier.', 'error')
    return redirect(url_for('suppliers'))

# Error handler for CSRF errors
@app.errorhandler(400)
def handle_csrf_error(e):
    """Handle CSRF errors by flashing a message and redirecting."""
    if 'csrf' in str(e).lower():
        logger.warning(f"CSRF error: {e}")
        flash('Your session has expired. Please try again.', 'error')
        return redirect(url_for('index'))
    return e

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)