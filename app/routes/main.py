from flask import Blueprint, render_template
from ..models.database import get_db
from ..utils.decorators import login_required
from datetime import datetime, timedelta

main = Blueprint('main', __name__)

@main.route('/')
@login_required
def index():
    """Render the dashboard with statistics."""
    try:
        with get_db() as conn:
            cursor = conn.cursor(dictionary=True)
            
            # Get total products count
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_count,
                    SUM(CASE WHEN quantity <= min_quantity THEN 1 ELSE 0 END) as low_stock_count,
                    SUM(CASE WHEN expiry_date < CURDATE() THEN 1 ELSE 0 END) as expired_count,
                    SUM(CASE WHEN is_scheduled = TRUE THEN 1 ELSE 0 END) as scheduled_count
                FROM products
            ''')
            product_stats = cursor.fetchone()
            
            # Get expiring soon (within 1 month)
            cursor.execute('''
                SELECT COUNT(*) as expiring_soon
                FROM products
                WHERE expiry_date >= CURDATE() AND expiry_date < DATE_ADD(CURDATE(), INTERVAL 1 MONTH)
            ''')
            expiring_soon = cursor.fetchone()['expiring_soon']
            
            # Get today's sales
            cursor.execute('''
                SELECT 
                    COALESCE(SUM(total_amount), 0) as total_sales,
                    COUNT(*) as total_bills,
                    COALESCE(SUM(CASE WHEN payment_method = 'cash' THEN total_amount ELSE 0 END), 0) as cash_sales,
                    COALESCE(SUM(CASE WHEN payment_method = 'card' THEN total_amount ELSE 0 END), 0) as card_sales,
                    COALESCE(SUM(CASE WHEN payment_method = 'upi' THEN total_amount ELSE 0 END), 0) as upi_sales
                FROM bills 
                WHERE DATE(bill_date) = CURDATE()
            ''')
            sales_stats = cursor.fetchone()
            
            stats = {
                'total_products': product_stats['total_count'] or 0,
                'expired_products': product_stats['expired_count'] or 0,
                'low_stock_items': product_stats['low_stock_count'] or 0,
                'scheduled_products': product_stats['scheduled_count'] or 0,
                'expiring_soon': expiring_soon or 0,
                'today_sales': sales_stats['total_sales'] or 0,
                'today_bills': sales_stats['total_bills'] or 0,
                'cash_sales': sales_stats['cash_sales'] or 0,
                'card_sales': sales_stats['card_sales'] or 0,
                'upi_sales': sales_stats['upi_sales'] or 0
            }
            
            return render_template('main/index.html', 
                                 stats=stats)
                                 
    except Exception as e:
        print(f"Error in dashboard: {str(e)}")
        return render_template('main/index.html', 
                             stats={
                                 'total_products': 0,
                                 'expired_products': 0,
                                 'low_stock_items': 0,
                                 'scheduled_products': 0,
                                 'expiring_soon': 0,
                                 'today_sales': 0,
                                 'today_bills': 0,
                                 'cash_sales': 0,
                                 'card_sales': 0,
                                 'upi_sales': 0
                             }) 