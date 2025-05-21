from flask import Blueprint, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from datetime import datetime, timedelta
from ..forms import BillingForm
from ..models.database import get_db
from ..utils.decorators import login_required
from ..utils.logging import log_activity
import json
import pdfkit
import os
from io import BytesIO

billing = Blueprint('billing', __name__)

@billing.route('/')
@login_required
def index():
    """List all bills with date filtering."""
    try:
        filter_type = request.args.get('filter', 'all')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        with get_db() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Base query
            query = '''SELECT b.*, u.username as created_by_name 
                      FROM bills b 
                      LEFT JOIN users u ON b.created_by = u.id'''
            params = []
            
            # Add date filtering
            if filter_type == 'today':
                query += " WHERE DATE(b.bill_date) = CURDATE()"
            elif filter_type == 'yesterday':
                query += " WHERE DATE(b.bill_date) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)"
            elif filter_type == 'this_week':
                query += " WHERE YEARWEEK(b.bill_date) = YEARWEEK(CURDATE())"
            elif filter_type == 'this_month':
                query += " WHERE MONTH(b.bill_date) = MONTH(CURDATE()) AND YEAR(b.bill_date) = YEAR(CURDATE())"
            elif filter_type == 'this_year':
                query += " WHERE YEAR(b.bill_date) = YEAR(CURDATE())"
            elif filter_type == 'custom' and start_date and end_date:
                query += " WHERE DATE(b.bill_date) BETWEEN %s AND %s"
                params.extend([start_date, end_date])
            
            query += " ORDER BY b.bill_date DESC"
            cursor.execute(query, params)
            bills = cursor.fetchall()
            
        return render_template('billing/index.html', bills=bills, 
                             filter_type=filter_type, 
                             start_date=start_date, 
                             end_date=end_date)
    except Exception as e:
        flash('An error occurred while fetching bills.', 'error')
        return render_template('billing/index.html', bills=[])

@billing.route('/new', methods=['GET', 'POST'])
@login_required
def new_bill():
    """Create a new bill."""
    form = BillingForm()
    if form.validate_on_submit():
        try:
            items = json.loads(request.form.get('items', '[]'))
            if not items:
                flash('Please add at least one product to the bill.', 'error')
                return redirect(url_for('billing.new_bill'))
            
            with get_db() as conn:
                cursor = conn.cursor(dictionary=True)
                
                # Create bill
                cursor.execute('''INSERT INTO bills 
                            (customer_name, customer_phone, customer_email, 
                             total_amount, bill_date, payment_method, created_by)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)''',
                         (form.customer_name.data, form.customer_phone.data,
                          form.customer_email.data, 0, datetime.now().date(),
                          form.payment_method.data, session['user_id']))
                
                bill_id = cursor.lastrowid
                total_amount = 0
                
                # Add bill items
                for item in items:
                    product_id = item['id']
                    quantity = item['quantity']
                    
                    # Get product details
                    cursor.execute('SELECT price, quantity FROM products WHERE id = %s', (product_id,))
                    product = cursor.fetchone()
                    
                    if not product:
                        raise Exception(f"Product {product_id} not found")
                    
                    if product['quantity'] < quantity:
                        raise Exception(f"Insufficient stock for product {product_id}")
                    
                    # Update product quantity
                    cursor.execute('UPDATE products SET quantity = quantity - %s WHERE id = %s',
                                 (quantity, product_id))
                    
                    # Add bill item
                    cursor.execute('''INSERT INTO bill_items 
                                (bill_id, product_id, quantity, unit_price)
                                VALUES (%s, %s, %s, %s)''',
                             (bill_id, product_id, quantity, product['price']))
                    
                    total_amount += product['price'] * quantity
                
                # Update bill total
                cursor.execute('UPDATE bills SET total_amount = %s WHERE id = %s',
                             (total_amount, bill_id))
                
                log_activity(session['user_id'], 'bill_created', f"Created bill #{bill_id}")
                flash('Bill created successfully!', 'success')
                return redirect(url_for('billing.view_bill', bill_id=bill_id))
                
        except Exception as e:
            flash(f'An error occurred while creating the bill: {str(e)}', 'error')
            return redirect(url_for('billing.new_bill'))
    
    return render_template('billing/new_bill.html', form=form)

@billing.route('/bills/<int:bill_id>')
@login_required
def view_bill(bill_id):
    """View a bill."""
    try:
        with get_db() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Get bill details
            cursor.execute('''SELECT b.*, u.username as created_by_name 
                        FROM bills b 
                        LEFT JOIN users u ON b.created_by = u.id 
                        WHERE b.id = %s''', (bill_id,))
            bill = cursor.fetchone()
            
            if not bill:
                flash('Bill not found.', 'error')
                return redirect(url_for('billing.index'))
            
            # Get bill items
            cursor.execute('''SELECT bi.*, p.name as product_name 
                        FROM bill_items bi 
                        JOIN products p ON bi.product_id = p.id 
                        WHERE bi.bill_id = %s''', (bill_id,))
            items = cursor.fetchall()
            
        return render_template('billing/view_bill.html', bill=bill, items=items)
    except Exception as e:
        flash('An error occurred while fetching the bill.', 'error')
        return redirect(url_for('billing.index'))

@billing.route('/bills/<int:bill_id>/pdf')
@login_required
def download_bill_pdf(bill_id):
    """Download bill as PDF."""
    try:
        with get_db() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Get bill details
            cursor.execute('''SELECT b.*, u.username as created_by_name 
                        FROM bills b 
                        LEFT JOIN users u ON b.created_by = u.id 
                        WHERE b.id = %s''', (bill_id,))
            bill = cursor.fetchone()
            
            if not bill:
                flash('Bill not found.', 'error')
                return redirect(url_for('billing.index'))
            
            # Get bill items
            cursor.execute('''SELECT bi.*, p.name as product_name 
                        FROM bill_items bi 
                        JOIN products p ON bi.product_id = p.id 
                        WHERE bi.bill_id = %s''', (bill_id,))
            items = cursor.fetchall()
            
            # Generate HTML
            html = render_template('billing/bill_pdf.html', bill=bill, items=items)
            
            # Convert to PDF
            pdf = pdfkit.from_string(html, False)
            
            # Create BytesIO object
            pdf_file = BytesIO(pdf)
            pdf_file.seek(0)
            
            return send_file(
                pdf_file,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=f'bill_{bill_id}.pdf'
            )
            
    except Exception as e:
        flash('An error occurred while generating PDF.', 'error')
        return redirect(url_for('billing.view_bill', bill_id=bill_id))

@billing.route('/bills/<int:bill_id>/delete', methods=['POST'])
@login_required
def delete_bill(bill_id):
    """Delete a bill."""
    try:
        with get_db() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Get bill items
            cursor.execute('SELECT product_id, quantity FROM bill_items WHERE bill_id = %s', (bill_id,))
            items = cursor.fetchall()
            
            # Restore product quantities
            for item in items:
                cursor.execute('UPDATE products SET quantity = quantity + %s WHERE id = %s',
                             (item['quantity'], item['product_id']))
            
            # Delete bill items
            cursor.execute('DELETE FROM bill_items WHERE bill_id = %s', (bill_id,))
            
            # Delete bill
            cursor.execute('DELETE FROM bills WHERE id = %s', (bill_id,))
            
            log_activity(session['user_id'], 'bill_deleted', f"Deleted bill #{bill_id}")
            flash('Bill deleted successfully!', 'success')
            
        return redirect(url_for('billing.index'))
    except Exception as e:
        flash('An error occurred while deleting the bill.', 'error')
        return redirect(url_for('billing.index'))

@billing.route('/products/search')
@login_required
def search_products():
    """Search products for billing."""
    query = request.args.get('q', '')
    try:
        with get_db() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''
                SELECT id, name, CAST(price AS DECIMAL(10,2)) as price, quantity, is_scheduled, schedule_type as schedule_category
                FROM products 
                WHERE (name LIKE %s OR description LIKE %s) 
                AND quantity > 0 
                AND expiry_date > CURDATE()
                ORDER BY name 
                LIMIT 10
            ''', (f'%{query}%', f'%{query}%'))
            products = cursor.fetchall()
            
            # Convert price to float for each product
            for product in products:
                product['price'] = float(product['price'])
                
        return jsonify(products)
    except Exception as e:
        return jsonify([])

@billing.route('/export-pdf')
@login_required
def export_bills_pdf():
    """Export filtered bills as PDF."""
    try:
        filter_type = request.args.get('filter', 'all')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        with get_db() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Base query
            query = '''SELECT b.*, u.username as created_by_name 
                      FROM bills b 
                      LEFT JOIN users u ON b.created_by = u.id'''
            params = []
            
            # Add date filtering
            if filter_type == 'today':
                query += " WHERE DATE(b.bill_date) = CURDATE()"
            elif filter_type == 'yesterday':
                query += " WHERE DATE(b.bill_date) = DATE_SUB(CURDATE(), INTERVAL 1 DAY)"
            elif filter_type == 'this_week':
                query += " WHERE YEARWEEK(b.bill_date) = YEARWEEK(CURDATE())"
            elif filter_type == 'this_month':
                query += " WHERE MONTH(b.bill_date) = MONTH(CURDATE()) AND YEAR(b.bill_date) = YEAR(CURDATE())"
            elif filter_type == 'this_year':
                query += " WHERE YEAR(b.bill_date) = YEAR(CURDATE())"
            elif filter_type == 'custom' and start_date and end_date:
                query += " WHERE DATE(b.bill_date) BETWEEN %s AND %s"
                params.extend([start_date, end_date])
            
            query += " ORDER BY b.bill_date DESC"
            cursor.execute(query, params)
            bills = cursor.fetchall()
            
            if not bills:
                flash('No bills found for the selected filter.', 'warning')
                return redirect(url_for('billing.index'))
            
            # Get items for each bill
            for bill in bills:
                cursor.execute('''SELECT bi.*, p.name as product_name 
                            FROM bill_items bi 
                            JOIN products p ON bi.product_id = p.id 
                            WHERE bi.bill_id = %s''', (bill['id'],))
                bill['items'] = cursor.fetchall()
            
            # Generate HTML
            html = render_template('billing/bills_pdf.html', 
                                 bills=bills,
                                 filter_type=filter_type,
                                 start_date=start_date,
                                 end_date=end_date,
                                 now=datetime.now())
            
            # Configure PDF options
            options = {
                'page-size': 'A4',
                'margin-top': '20mm',
                'margin-right': '20mm',
                'margin-bottom': '20mm',
                'margin-left': '20mm',
                'encoding': 'UTF-8',
                'no-outline': None,
                'quiet': ''
            }
            
            # Convert to PDF
            try:
                pdf = pdfkit.from_string(html, False, options=options)
            except Exception as e:
                print(f"PDF generation error: {str(e)}")
                flash('Error generating PDF. Please check if wkhtmltopdf is installed.', 'error')
                return redirect(url_for('billing.index'))
            
            # Create BytesIO object
            pdf_file = BytesIO(pdf)
            pdf_file.seek(0)
            
            # Generate filename based on filter
            if filter_type == 'custom':
                filename = f'bills_{start_date}_to_{end_date}.pdf'
            else:
                filename = f'bills_{filter_type}.pdf'
            
            return send_file(
                pdf_file,
                mimetype='application/pdf',
                as_attachment=True,
                download_name=filename
            )
            
    except Exception as e:
        print(f"Export error: {str(e)}")
        flash('An error occurred while generating PDF.', 'error')
        return redirect(url_for('billing.index')) 