from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from ..forms import ProductForm, SupplierForm
from ..models.database import get_db
from ..utils.decorators import login_required
from ..utils.logging import log_activity

inventory = Blueprint('inventory', __name__)

@inventory.route('/')
@login_required
def index():
    """List all products."""
    try:
        with get_db() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Get filter parameters
            filter_type = request.args.get('filter', '')
            
            # Base query
            query = """
                SELECT p.*, s.name as supplier_name 
                FROM products p 
                LEFT JOIN suppliers s ON p.supplier_id = s.id
            """
            
            # Apply filters
            if filter_type == 'expired':
                query += " WHERE p.expiry_date < CURDATE()"
            elif filter_type == 'low_stock':
                query += " WHERE p.quantity <= p.min_quantity"
            elif filter_type == 'scheduled':
                query += " WHERE p.is_scheduled = TRUE"
            
            query += " ORDER BY p.name"
            
            cursor.execute(query)
            products = cursor.fetchall()
            
            # Get current date for expiry comparison
            now = datetime.now().date()
            
        return render_template('inventory/index.html', products=products, now=now)
    except Exception as e:
        flash('An error occurred while fetching products.', 'error')
        return render_template('inventory/index.html', products=[])

@inventory.route('/products/add', methods=['GET', 'POST'])
@login_required
def add_product():
    """Add a new product."""
    form = ProductForm()
    try:
        with get_db() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT id, name FROM suppliers ORDER BY name')
            suppliers = cursor.fetchall()
            form.supplier_id.choices = [(0, '-- Select Supplier --')] + [(s['id'], s['name']) for s in suppliers]
    except Exception as e:
        flash(f'An error occurred while fetching suppliers: {str(e)}', 'error')
        return redirect(url_for('inventory.index'))

    if form.validate_on_submit():
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                
                # Convert supplier_id to None if it's 0
                supplier_id = None if form.supplier_id.data == 0 else form.supplier_id.data
                
                cursor.execute('''INSERT INTO products 
                            (name, description, quantity, min_quantity, price, expiry_date, 
                             supplier_id, is_scheduled, schedule_type, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
                         (form.name.data, form.description.data, form.quantity.data, 
                          form.min_quantity.data, form.price.data, form.expiry_date.data, 
                          supplier_id, form.is_scheduled.data,
                          form.schedule_type.data if form.is_scheduled.data else None,
                          now))
                conn.commit()
                
                log_activity(session['user_id'], 'product_created', f"Created product: {form.name.data}")
                flash('Product added successfully!', 'success')
                return redirect(url_for('inventory.index'))
        except Exception as e:
            flash(f'An error occurred while adding the product: {str(e)}', 'error')
    
    return render_template('inventory/add_product.html', form=form)

@inventory.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    """Edit a product."""
    form = ProductForm()
    try:
        with get_db() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT id, name FROM suppliers ORDER BY name')
            suppliers = cursor.fetchall()
            form.supplier_id.choices = [(0, '-- Select Supplier --')] + [(s['id'], s['name']) for s in suppliers]
            
            if request.method == 'GET':
                cursor.execute('SELECT * FROM products WHERE id = %s', (product_id,))
                product = cursor.fetchone()
                if not product:
                    flash('Product not found.', 'error')
                    return redirect(url_for('inventory.index'))
                
                form.name.data = product['name']
                form.description.data = product['description']
                form.quantity.data = product['quantity']
                form.min_quantity.data = product['min_quantity']
                form.price.data = product['price']
                form.expiry_date.data = product['expiry_date']
                form.supplier_id.data = product['supplier_id'] or 0
                form.is_scheduled.data = product['is_scheduled']
                form.schedule_type.data = product['schedule_type']
            
            if form.validate_on_submit():
                # Convert supplier_id to None if it's 0
                supplier_id = None if form.supplier_id.data == 0 else form.supplier_id.data
                
                cursor.execute('''UPDATE products 
                           SET name = %s, description = %s, quantity = %s, min_quantity = %s,
                               price = %s, expiry_date = %s, supplier_id = %s,
                               is_scheduled = %s, schedule_type = %s
                           WHERE id = %s''',
                         (form.name.data, form.description.data, form.quantity.data,
                          form.min_quantity.data, form.price.data, form.expiry_date.data,
                          supplier_id, form.is_scheduled.data,
                          form.schedule_type.data if form.is_scheduled.data else None,
                          product_id))
                conn.commit()
                
                log_activity(session['user_id'], 'product_updated', f"Updated product: {form.name.data}")
                flash('Product updated successfully!', 'success')
                return redirect(url_for('inventory.index'))
                
        return render_template('inventory/edit_product.html', form=form, product=product)
    except Exception as e:
        flash(f'An error occurred while editing the product: {str(e)}', 'error')
        return redirect(url_for('inventory.index'))

@inventory.route('/products/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    """Delete a product."""
    try:
        with get_db() as conn:
            cursor = conn.cursor(dictionary=True)
            # Check if product exists
            cursor.execute('SELECT name FROM products WHERE id = %s', (product_id,))
            product = cursor.fetchone()
            
            if not product:
                flash('Product not found.', 'error')
                return redirect(url_for('inventory.index'))
            
            # Delete product
            cursor.execute('DELETE FROM products WHERE id = %s', (product_id,))
            conn.commit()
            
            log_activity(session['user_id'], 'product_deleted', f"Deleted product: {product['name']}")
            flash('Product deleted successfully!', 'success')
            
        return redirect(url_for('inventory.index'))
    except Exception as e:
        flash(f'An error occurred while deleting the product: {str(e)}', 'error')
        return redirect(url_for('inventory.index'))

@inventory.route('/suppliers')
@login_required
def suppliers():
    """List all suppliers."""
    try:
        with get_db() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT * FROM suppliers ORDER BY name')
            suppliers = cursor.fetchall()
        return render_template('inventory/suppliers.html', suppliers=suppliers)
    except Exception as e:
        flash('An error occurred while fetching suppliers.', 'error')
        return render_template('inventory/suppliers.html', suppliers=[])

@inventory.route('/suppliers/add', methods=['GET', 'POST'])
@login_required
def add_supplier():
    """Add a new supplier."""
    form = SupplierForm()
    if form.validate_on_submit():
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute('''INSERT INTO suppliers 
                            (name, contact_person, phone, email, address, created_at)
                            VALUES (%s, %s, %s, %s, %s, %s)''',
                         (form.name.data, form.contact_person.data, form.phone.data,
                          form.email.data, form.address.data, now))
                conn.commit()
                
                log_activity(session['user_id'], 'supplier_created', f"Created supplier: {form.name.data}")
                flash('Supplier added successfully!', 'success')
                return redirect(url_for('inventory.suppliers'))
        except Exception as e:
            flash(f'An error occurred while adding the supplier: {str(e)}', 'error')
    
    return render_template('inventory/add_supplier.html', form=form)

@inventory.route('/suppliers/edit/<int:supplier_id>', methods=['GET', 'POST'])
@login_required
def edit_supplier(supplier_id):
    """Edit a supplier."""
    form = SupplierForm()
    try:
        with get_db() as conn:
            cursor = conn.cursor(dictionary=True)
            
            if request.method == 'GET':
                cursor.execute('SELECT * FROM suppliers WHERE id = %s', (supplier_id,))
                supplier = cursor.fetchone()
                if not supplier:
                    flash('Supplier not found.', 'error')
                    return redirect(url_for('inventory.suppliers'))
                
                form.name.data = supplier['name']
                form.contact_person.data = supplier['contact_person']
                form.phone.data = supplier['phone']
                form.email.data = supplier['email']
                form.address.data = supplier['address']
            
            if form.validate_on_submit():
                cursor.execute('''UPDATE suppliers 
                           SET name = %s, contact_person = %s, phone = %s, 
                               email = %s, address = %s
                           WHERE id = %s''',
                         (form.name.data, form.contact_person.data, form.phone.data,
                          form.email.data, form.address.data, supplier_id))
                conn.commit()
                
                log_activity(session['user_id'], 'supplier_updated', f"Updated supplier: {form.name.data}")
                flash('Supplier updated successfully!', 'success')
                return redirect(url_for('inventory.suppliers'))
                
        return render_template('inventory/edit_supplier.html', form=form, supplier_id=supplier_id)
    except Exception as e:
        flash(f'An error occurred while editing the supplier: {str(e)}', 'error')
        return redirect(url_for('inventory.suppliers'))

@inventory.route('/suppliers/delete/<int:supplier_id>', methods=['POST'])
@login_required
def delete_supplier(supplier_id):
    """Delete a supplier."""
    try:
        with get_db() as conn:
            cursor = conn.cursor(dictionary=True)
            # Check if supplier exists and has no products
            cursor.execute('SELECT name FROM suppliers WHERE id = %s', (supplier_id,))
            supplier = cursor.fetchone()
            
            if not supplier:
                flash('Supplier not found.', 'error')
                return redirect(url_for('inventory.suppliers'))
            
            cursor.execute('SELECT COUNT(*) as count FROM products WHERE supplier_id = %s', (supplier_id,))
            if cursor.fetchone()['count'] > 0:
                flash('Cannot delete supplier with associated products.', 'error')
                return redirect(url_for('inventory.suppliers'))
            
            # Delete supplier
            cursor.execute('DELETE FROM suppliers WHERE id = %s', (supplier_id,))
            conn.commit()
            
            log_activity(session['user_id'], 'supplier_deleted', f"Deleted supplier: {supplier['name']}")
            flash('Supplier deleted successfully!', 'success')
            
        return redirect(url_for('inventory.suppliers'))
    except Exception as e:
        flash(f'An error occurred while deleting the supplier: {str(e)}', 'error')
        return redirect(url_for('inventory.suppliers')) 