import os
import sqlite3
from datetime import datetime, timedelta
import random

def get_db_path():
    """Get the database path from environment or use default."""
    base_dir = os.path.abspath(os.path.dirname(__file__))
    db_dir = os.path.join(base_dir, 'database')
    return os.environ.get('DB_PATH', os.path.join(db_dir, 'medical_shop.db'))

def connect_to_db(db_path):
    """Connect to the database."""
    conn = sqlite3.connect(db_path)
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def create_sample_suppliers(conn, num_suppliers=5):
    """Create sample suppliers."""
    print("\nCreating sample suppliers...")
    
    suppliers = [
        ("MediPharma", "contact@medipharma.com, +91-9876543210"),
        ("HealthCare Distributors", "sales@healthcaredist.com, +91-8765432109"),
        ("Global Meds", "info@globalmeds.com, +91-7654321098"),
        ("Wellness Supplies", "orders@wellnesssupplies.com, +91-6543210987"),
        ("Medicare Solutions", "support@medicaresolutions.com, +91-5432109876")
    ]
    
    cursor = conn.cursor()
    for name, contact in suppliers:
        try:
            cursor.execute("INSERT INTO suppliers (name, contact) VALUES (?, ?)", (name, contact))
            print(f"Added supplier: {name}")
        except sqlite3.IntegrityError:
            print(f"Supplier '{name}' already exists.")
    
    conn.commit()
    
    # Get all supplier IDs for future reference
    cursor.execute("SELECT id FROM suppliers")
    supplier_ids = [row[0] for row in cursor.fetchall()]
    return supplier_ids

def create_sample_products(conn, supplier_ids, num_products=15):
    """Create sample products with future expiry dates."""
    print("\nCreating sample products...")
    
    products = [
        ("Paracetamol 500mg", 100, 5.50),
        ("Ibuprofen 400mg", 75, 8.25),
        ("Amoxicillin 250mg", 50, 12.75),
        ("Cetirizine 10mg", 60, 4.99),
        ("Omeprazole 20mg", 30, 15.50),
        ("Multivitamin Tablets", 90, 9.99),
        ("Calcium + Vitamin D3", 60, 7.75),
        ("Diabetic Test Strips", 50, 35.99),
        ("Blood Pressure Monitor", 5, 1250.00),
        ("Digital Thermometer", 15, 150.00),
        ("First Aid Kit", 10, 350.00),
        ("Hand Sanitizer 500ml", 40, 120.00),
        ("Face Masks (Pack of 10)", 30, 80.00),
        ("Cough Syrup 100ml", 25, 45.50),
        ("Pain Relief Gel 30g", 20, 65.75)
    ]
    
    cursor = conn.cursor()
    today = datetime.now()
    
    for name, quantity, price in products:
        # Generate a random expiry date in the future (3 months to 3 years)
        days_to_add = random.randint(90, 1095)  # Between 3 months and 3 years
        expiry_date = (today + timedelta(days=days_to_add)).strftime('%Y-%m-%d')
        
        # Randomly assign a supplier
        supplier_id = random.choice(supplier_ids) if supplier_ids else None
        
        try:
            cursor.execute(
                "INSERT INTO products (name, quantity, price, expiry_date, supplier_id) VALUES (?, ?, ?, ?, ?)",
                (name, quantity, price, expiry_date, supplier_id)
            )
            print(f"Added product: {name} (Qty: {quantity}, Price: ₹{price:.2f}, Expires: {expiry_date})")
        except sqlite3.IntegrityError:
            print(f"Product '{name}' already exists.")
    
    conn.commit()
    
    # Get product IDs for bill creation
    cursor.execute("SELECT id, price FROM products WHERE quantity > 0")
    products = cursor.fetchall()
    return products

def create_sample_bills(conn, products, num_bills=5):
    """Create sample bills with items."""
    if not products:
        print("\nNo products available to create bills.")
        return
    
    print("\nCreating sample bills...")
    
    customer_names = [
        "Raj Kumar", "Priya Singh", "Arun Sharma", "Deepa Patel", 
        "Vikram Mehta", "Anita Gupta", "Suresh Reddy", "Meena Iyer"
    ]
    
    cursor = conn.cursor()
    today = datetime.now()
    
    for i in range(num_bills):
        # Create a random date in the last 30 days
        days_ago = random.randint(0, 30)
        bill_date = (today - timedelta(days=days_ago)).strftime('%Y-%m-%d')
        
        # Select a random customer
        customer_name = random.choice(customer_names)
        
        # Create the bill first with zero amount (will update later)
        cursor.execute(
            "INSERT INTO bills (customer_name, total_amount, bill_date) VALUES (?, ?, ?)",
            (customer_name, 0.0, bill_date)
        )
        bill_id = cursor.lastrowid
        
        # Add 1-5 random items to the bill
        num_items = random.randint(1, 5)
        total_amount = 0.0
        
        # Shuffle products to get random ones
        bill_products = random.sample(products, min(num_items, len(products)))
        
        for product_id, price in bill_products:
            # Random quantity between 1 and 3
            quantity = random.randint(1, 3)
            
            # Add bill item
            cursor.execute(
                "INSERT INTO bill_items (bill_id, product_id, quantity) VALUES (?, ?, ?)",
                (bill_id, product_id, quantity)
            )
            
            # Update product quantity
            cursor.execute(
                "UPDATE products SET quantity = quantity - ? WHERE id = ?",
                (quantity, product_id)
            )
            
            # Add to total amount
            total_amount += price * quantity
        
        # Update the bill with the correct total
        cursor.execute(
            "UPDATE bills SET total_amount = ? WHERE id = ?",
            (total_amount, bill_id)
        )
        
        print(f"Created bill #{i+1} for {customer_name} on {bill_date} with {num_items} items. Total: ₹{total_amount:.2f}")
    
    conn.commit()

def main():
    """Run the sample data generator."""
    print("=" * 50)
    print("MEDICAL SHOP SAMPLE DATA GENERATOR")
    print("=" * 50)
    
    db_path = get_db_path()
    print(f"Database path: {db_path}")
    
    try:
        conn = connect_to_db(db_path)
        print("Connected to database successfully.")
        
        supplier_ids = create_sample_suppliers(conn)
        products = create_sample_products(conn, supplier_ids)
        create_sample_bills(conn, products)
        
        print("\n" + "=" * 50)
        print("Sample data generation complete!")
        print("=" * 50)
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    main()