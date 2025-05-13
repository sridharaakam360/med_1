import os
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_wtf.csrf import CSRFProtect
from wtforms import StringField, IntegerField, FloatField, DateField, SelectField, PasswordField, EmailField
from wtforms.validators import DataRequired, NumberRange, Email, Length, EqualTo
from flask_wtf import FlaskForm
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# Configure logging with rotation
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler('app.log', maxBytes=10000, backupCount=3)
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

app = Flask(__name__)

# Load configuration from environment variables
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '51f52814d7bb5d8d7cb5ec61a9b05f237c6ca5f87cc21cdd')
app.config['SESSION_TYPE'] = 'filesystem'
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_TIME_LIMIT'] = None

# Initialize CSRF protection
csrf = CSRFProtect(app)

# Database setup
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_DIR = os.path.join(BASE_DIR, 'database')
DB_PATH = os.environ.get('DB_PATH', os.path.join(DB_DIR, 'medical_shop.db'))

# Authentication decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to access this page.', 'error')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_role' not in session or session['user_role'] != 'admin':
            flash('You need admin privileges to access this page.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def log_activity(user_id, action, details=None):
    """Log user activity to the database."""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            c.execute('INSERT INTO activity_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)',
                     (user_id, action, details, now))
            conn.commit()
    except Exception as e:
        logger.error(f"Error logging activity: {e}")

def get_db_connection():
    """Get a database connection with foreign keys enabled."""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute('PRAGMA foreign_keys = ON')
        conn.row_factory = sqlite3.Row
        logger.debug("Database connection established")
        return conn
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        raise

def init_db():
    """Initialize the SQLite database and create necessary tables."""
    try:
        if not os.path.exists(DB_DIR):
            os.makedirs(DB_DIR)
            logger.debug(f"Created database directory: {DB_DIR}")

        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Create users table
            c.execute('''CREATE TABLE IF NOT EXISTS users (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         username TEXT UNIQUE NOT NULL,
                         email TEXT UNIQUE NOT NULL,
                         password_hash TEXT NOT NULL,
                         role TEXT NOT NULL DEFAULT 'staff',
                         created_at TEXT NOT NULL,
                         last_login TEXT)''')
            
            # Create activity_logs table
            c.execute('''CREATE TABLE IF NOT EXISTS activity_logs (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         user_id INTEGER,
                         action TEXT NOT NULL,
                         details TEXT,
                         timestamp TEXT NOT NULL,
                         FOREIGN KEY(user_id) REFERENCES users(id))''')

            # Create existing tables
            c.execute('''CREATE TABLE IF NOT EXISTS products (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         name TEXT NOT NULL,
                         quantity INTEGER NOT NULL,
                         price REAL NOT NULL,
                         expiry_date TEXT NOT NULL,
                         supplier_id INTEGER,
                         created_by INTEGER,
                         updated_by INTEGER,
                         created_at TEXT NOT NULL,
                         updated_at TEXT,
                         FOREIGN KEY(supplier_id) REFERENCES suppliers(id),
                         FOREIGN KEY(created_by) REFERENCES users(id),
                         FOREIGN KEY(updated_by) REFERENCES users(id))''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS suppliers (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         name TEXT NOT NULL,
                         contact TEXT,
                         email TEXT,
                         address TEXT,
                         created_by INTEGER,
                         created_at TEXT NOT NULL,
                         FOREIGN KEY(created_by) REFERENCES users(id))''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS bills (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         customer_name TEXT NOT NULL,
                         customer_phone TEXT,
                         customer_email TEXT,
                         total_amount REAL NOT NULL,
                         bill_date TEXT NOT NULL,
                         payment_method TEXT,
                         created_by INTEGER,
                         FOREIGN KEY(created_by) REFERENCES users(id))''')
            
            c.execute('''CREATE TABLE IF NOT EXISTS bill_items (
                         id INTEGER PRIMARY KEY AUTOINCREMENT,
                         bill_id INTEGER,
                         product_id INTEGER,
                         quantity INTEGER,
                         unit_price REAL NOT NULL,
                         FOREIGN KEY(bill_id) REFERENCES bills(id),
                         FOREIGN KEY(product_id) REFERENCES products(id))''')
            
            # Create default admin user if not exists
            c.execute('SELECT COUNT(*) FROM users WHERE role = "admin"')
            if c.fetchone()[0] == 0:
                admin_password = generate_password_hash('admin123')  # Change this in production
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                try:
                    c.execute('INSERT INTO users (username, email, password_hash, role, created_at) VALUES (?, ?, ?, ?, ?)',
                             ('admin', 'admin@example.com', admin_password, 'admin', now))
                    conn.commit()
                    logger.info("Created default admin user")
                except sqlite3.IntegrityError:
                    logger.info("Default admin user already exists")
                    conn.rollback()
            
            conn.commit()
            logger.debug(f"Database initialized at {DB_PATH}")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
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

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[
        DataRequired(),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(),
        EqualTo('password', message='Passwords must match')
    ])

class EditUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    role = SelectField('Role', choices=[('staff', 'Staff'), ('admin', 'Admin')], validators=[DataRequired()])

@app.route('/')
@login_required
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
            
            # Low stock products (less than 10 items)
            c.execute('SELECT COUNT(*) FROM products WHERE quantity < 10')
            low_stock_count = c.fetchone()[0]
            
            # Recent activities
            c.execute('''SELECT u.username, al.action, al.details, al.timestamp 
                        FROM activity_logs al 
                        JOIN users u ON al.user_id = u.id 
                        ORDER BY al.timestamp DESC LIMIT 5''')
            recent_activities = c.fetchall()
            
        return render_template('index.html', 
                             products_count=products_count,
                             expired_count=expired_count,
                             bills_count=bills_count,
                             low_stock_count=low_stock_count,
                             recent_activities=recent_activities)
    except Exception as e:
        logger.error(f"Error fetching dashboard data: {e}")
        flash('An error occurred while loading the dashboard.', 'error')
        return render_template('index.html')

@app.route('/billing', methods=['GET', 'POST'])
@login_required
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

                # Start transaction
                try:
                    # Create bill
                    c.execute('''INSERT INTO bills 
                               (customer_name, total_amount, bill_date, created_by) 
                               VALUES (?, ?, ?, ?)''',
                             (customer_name, 0, bill_date, session['user_id']))
                    bill_id = c.lastrowid

                    # Process items
                    for prod_id, qty in zip(items, quantities):
                        try:
                            qty = int(qty)
                            if qty <= 0:
                                raise ValueError(f"Invalid quantity for product ID {prod_id}")

                            # Get product details and check stock
                            c.execute('SELECT price, quantity FROM products WHERE id = ?', (prod_id,))
                            product = c.fetchone()
                            if not product:
                                raise ValueError(f"Product ID {prod_id} not found")
                            
                            if product['quantity'] < qty:
                                raise ValueError(f"Not enough stock for product ID {prod_id}. Available: {product['quantity']}")

                            price = product['price']
                            item_total = price * qty
                            total_amount += item_total

                            # Update product quantity
                            c.execute('UPDATE products SET quantity = quantity - ? WHERE id = ?', (qty, prod_id))
                            
                            # Add bill item
                            c.execute('''INSERT INTO bill_items 
                                       (bill_id, product_id, quantity, unit_price) 
                                       VALUES (?, ?, ?, ?)''',
                                     (bill_id, prod_id, qty, price))

                        except ValueError as ve:
                            # Rollback and report error
                            conn.rollback()
                            flash(str(ve), 'error')
                            return redirect(url_for('billing'))

                    # Update bill total
                    c.execute('UPDATE bills SET total_amount = ? WHERE id = ?', (total_amount, bill_id))
                    conn.commit()

                    log_activity(session['user_id'], 'bill_created', f"Created bill #{bill_id}")
                    flash('Bill created successfully!', 'success')
                    return redirect(url_for('bill_history'))

                except Exception as e:
                    conn.rollback()
                    logger.error(f"Error processing bill: {e}")
                    flash('An error occurred while processing the bill.', 'error')
                    return redirect(url_for('billing'))

        except Exception as e:
            logger.error(f"Error in billing: {e}")
            flash('An error occurred while processing the bill.', 'error')
            return redirect(url_for('billing'))

    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT id, name, price, quantity 
                        FROM products 
                        WHERE quantity > 0 
                        AND expiry_date > ?''', (today,))
            products = c.fetchall()
        return render_template('billing.html', form=form, products=products, today=today)
    except Exception as e:
        logger.error(f"Error fetching products for billing: {e}")
        flash('An error occurred while loading products.', 'error')
        return redirect(url_for('index'))

@app.route('/bill_history')
@login_required
def bill_history():
    """Display all past bills."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 10  # Number of bills per page
        
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Get total number of bills
            c.execute('SELECT COUNT(*) FROM bills')
            total_bills = c.fetchone()[0]
            
            # Calculate pagination
            total_pages = (total_bills + per_page - 1) // per_page
            offset = (page - 1) * per_page
            
            # Get bills for current page
            c.execute('''SELECT b.id, b.customer_name, b.total_amount, b.bill_date,
                               u.username as created_by
                        FROM bills b
                        LEFT JOIN users u ON b.created_by = u.id
                        ORDER BY b.bill_date DESC
                        LIMIT ? OFFSET ?''', (per_page, offset))
            bills = c.fetchall()
            
            # Get items for these bills
            bills_dict = {}
            if bills:
                for bill in bills:
                    bill_id = bill['id']
                    bills_dict[bill_id] = {
                        'id': bill_id,
                        'customer_name': bill['customer_name'],
                        'total_amount': bill['total_amount'],
                        'bill_date': bill['bill_date'],
                        'created_by': bill['created_by'],
                        'items': []
                    }
                
                # Get all items for these bills
                bill_ids = tuple(bills_dict.keys())
                if len(bill_ids) == 1:
                    c.execute('''SELECT bi.bill_id, bi.quantity, bi.unit_price,
                                      p.name as product_name
                               FROM bill_items bi
                               JOIN products p ON bi.product_id = p.id
                               WHERE bi.bill_id = ?''', (bill_ids[0],))
                else:
                    c.execute('''SELECT bi.bill_id, bi.quantity, bi.unit_price,
                                      p.name as product_name
                               FROM bill_items bi
                               JOIN products p ON bi.product_id = p.id
                               WHERE bi.bill_id IN {}'''.format(bill_ids))
                
                items = c.fetchall()
                for item in items:
                    bill_id = item['bill_id']
                    if bill_id in bills_dict:
                        bills_dict[bill_id]['items'].append({
                            'product_name': item['product_name'],
                            'quantity': item['quantity'],
                            'unit_price': item['unit_price'],
                            'total': item['quantity'] * item['unit_price']
                        })
            
        return render_template('bill_history.html',
                             bills=bills_dict.values(),
                             page=page,
                             total_pages=total_pages)
    except Exception as e:
        logger.error(f"Error fetching bill history: {e}")
        flash('An error occurred while fetching bill history.', 'error')
        return redirect(url_for('index'))

@app.route('/inventory', methods=['GET', 'POST'])
@login_required
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
@login_required
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
@login_required
def delete_product(product_id):
    """Delete a product."""
    if session.get('user_role') != 'admin':
        flash('Only administrators can delete products.', 'error')
        return redirect(url_for('inventory'))
        
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            # Check if product exists
            c.execute('SELECT name FROM products WHERE id = ?', (product_id,))
            product = c.fetchone()
            if not product:
                flash('Product not found.', 'error')
                return redirect(url_for('inventory'))
            
            # Check if product is used in any bills
            c.execute('SELECT 1 FROM bill_items WHERE product_id = ?', (product_id,))
            if c.fetchone():
                flash('Cannot delete product as it is referenced in bills.', 'error')
                return redirect(url_for('inventory'))
            
            # Delete product
            c.execute('DELETE FROM products WHERE id = ?', (product_id,))
            conn.commit()
            
            log_activity(session['user_id'], 'product_deleted', f"Deleted product: {product['name']}")
            flash('Product deleted successfully!', 'success')
            
        return redirect(url_for('inventory'))
    except Exception as e:
        logger.error(f"Error deleting product: {e}")
        flash('An error occurred while deleting the product.', 'error')
        return redirect(url_for('inventory'))

@app.route('/expiry')
@login_required
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
@login_required
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
@login_required
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
@login_required
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

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Handle user login."""
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        try:
            with get_db_connection() as conn:
                c = conn.cursor()
                c.execute('SELECT id, username, password_hash, role FROM users WHERE username = ?', (form.username.data,))
                user = c.fetchone()
                
                if user and check_password_hash(user[2], form.password.data):
                    session['user_id'] = user[0]
                    session['username'] = user[1]
                    session['user_role'] = user[3]
                    
                    # Update last login
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    c.execute('UPDATE users SET last_login = ? WHERE id = ?', (now, user[0]))
                    conn.commit()
                    
                    log_activity(user[0], 'login')
                    flash(f'Welcome back, {user[1]}!', 'success')
                    
                    next_page = request.args.get('next')
                    return redirect(next_page if next_page else url_for('index'))
                else:
                    flash('Invalid username or password.', 'error')
        except Exception as e:
            logger.error(f"Login error: {e}")
            flash('An error occurred during login.', 'error')
    
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
@admin_required
def register():
    """Handle user registration (admin only)."""
    form = RegisterForm()
    if form.validate_on_submit():
        try:
            with get_db_connection() as conn:
                c = conn.cursor()
                # Check if username exists
                c.execute('SELECT 1 FROM users WHERE username = ?', (form.username.data,))
                if c.fetchone():
                    flash('Username already exists.', 'error')
                    return render_template('register.html', form=form)
                
                # Check if email exists
                c.execute('SELECT 1 FROM users WHERE email = ?', (form.email.data,))
                if c.fetchone():
                    flash('Email already registered.', 'error')
                    return render_template('register.html', form=form)
                
                # Create new user
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                password_hash = generate_password_hash(form.password.data)
                c.execute('''INSERT INTO users (username, email, password_hash, role, created_at)
                            VALUES (?, ?, ?, ?, ?)''',
                         (form.username.data, form.email.data, password_hash, 'staff', now))
                conn.commit()
                
                log_activity(session['user_id'], 'user_created', f"Created user: {form.username.data}")
                flash('User registered successfully!', 'success')
                return redirect(url_for('users'))
        except Exception as e:
            logger.error(f"Registration error: {e}")
            flash('An error occurred during registration.', 'error')
    
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    """Handle user logout."""
    if 'user_id' in session:
        log_activity(session['user_id'], 'logout')
        session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))

@app.route('/users')
@admin_required
def users():
    """List all users (admin only)."""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT id, username, email, role, created_at, last_login 
                        FROM users ORDER BY created_at DESC''')
            users = c.fetchall()
        return render_template('users.html', users=users)
    except Exception as e:
        logger.error(f"Error fetching users: {e}")
        flash('An error occurred while fetching users.', 'error')
        return redirect(url_for('index'))

@app.route('/profile')
@login_required
def profile():
    """Show user profile."""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('''SELECT username, email, role, created_at, last_login 
                        FROM users WHERE id = ?''', (session['user_id'],))
            user = c.fetchone()
            
            # Get recent activity
            c.execute('''SELECT action, details, timestamp 
                        FROM activity_logs 
                        WHERE user_id = ? 
                        ORDER BY timestamp DESC LIMIT 10''', (session['user_id'],))
            activities = c.fetchall()
            
        return render_template('profile.html', user=user, activities=activities)
    except Exception as e:
        logger.error(f"Error fetching profile: {e}")
        flash('An error occurred while fetching profile.', 'error')
        return redirect(url_for('index'))

@app.route('/change_password', methods=['POST'])
@login_required
def change_password():
    """Handle password change requests."""
    try:
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        if not all([current_password, new_password, confirm_password]):
            flash('All password fields are required.', 'error')
            return redirect(url_for('profile'))

        if new_password != confirm_password:
            flash('New passwords do not match.', 'error')
            return redirect(url_for('profile'))

        if len(new_password) < 8:
            flash('New password must be at least 8 characters long.', 'error')
            return redirect(url_for('profile'))

        with get_db_connection() as conn:
            c = conn.cursor()
            c.execute('SELECT password_hash FROM users WHERE id = ?', (session['user_id'],))
            user = c.fetchone()

            if not check_password_hash(user[0], current_password):
                flash('Current password is incorrect.', 'error')
                return redirect(url_for('profile'))

            password_hash = generate_password_hash(new_password)
            c.execute('UPDATE users SET password_hash = ? WHERE id = ?',
                     (password_hash, session['user_id']))
            conn.commit()

            log_activity(session['user_id'], 'password_changed')
            flash('Password updated successfully!', 'success')

        return redirect(url_for('profile'))
    except Exception as e:
        logger.error(f"Error changing password: {e}")
        flash('An error occurred while changing password.', 'error')
        return redirect(url_for('profile'))

@app.route('/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete a user (admin only)."""
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            # Check if user exists and is not an admin
            c.execute('SELECT role FROM users WHERE id = ?', (user_id,))
            user = c.fetchone()
            
            if not user:
                flash('User not found.', 'error')
                return redirect(url_for('users'))
            
            if user[0] == 'admin':
                flash('Cannot delete admin user.', 'error')
                return redirect(url_for('users'))
            
            # Delete user's activity logs
            c.execute('DELETE FROM activity_logs WHERE user_id = ?', (user_id,))
            
            # Delete user
            c.execute('DELETE FROM users WHERE id = ?', (user_id,))
            conn.commit()
            
            log_activity(session['user_id'], 'user_deleted', f"Deleted user ID: {user_id}")
            flash('User deleted successfully!', 'success')
            
        return redirect(url_for('users'))
    except Exception as e:
        logger.error(f"Error deleting user: {e}")
        flash('An error occurred while deleting the user.', 'error')
        return redirect(url_for('users'))

@app.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """Edit a user (admin only)."""
    form = EditUserForm()
    
    try:
        with get_db_connection() as conn:
            c = conn.cursor()
            
            if request.method == 'GET':
                c.execute('SELECT username, email, role FROM users WHERE id = ?', (user_id,))
                user = c.fetchone()
                if not user:
                    flash('User not found.', 'error')
                    return redirect(url_for('users'))
                
                form.username.data = user['username']
                form.email.data = user['email']
                form.role.data = user['role']
            
            if form.validate_on_submit():
                # Check if username exists for other users
                c.execute('SELECT 1 FROM users WHERE username = ? AND id != ?', (form.username.data, user_id))
                if c.fetchone():
                    flash('Username already exists.', 'error')
                    return render_template('edit_user.html', form=form, user_id=user_id)
                
                # Check if email exists for other users
                c.execute('SELECT 1 FROM users WHERE email = ? AND id != ?', (form.email.data, user_id))
                if c.fetchone():
                    flash('Email already registered.', 'error')
                    return render_template('edit_user.html', form=form, user_id=user_id)
                
                # Update user
                c.execute('''UPDATE users 
                           SET username = ?, email = ?, role = ?
                           WHERE id = ?''',
                         (form.username.data, form.email.data, form.role.data, user_id))
                conn.commit()
                
                log_activity(session['user_id'], 'user_updated', f"Updated user: {form.username.data}")
                flash('User updated successfully!', 'success')
                return redirect(url_for('users'))
                
        return render_template('edit_user.html', form=form, user_id=user_id)
    except Exception as e:
        logger.error(f"Error editing user: {e}")
        flash('An error occurred while editing the user.', 'error')
        return redirect(url_for('users'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)