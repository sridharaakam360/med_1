from flask import Blueprint, render_template, request, redirect, url_for
from datetime import datetime
from reportlab.pdfgen import canvas
from .models.medicine import Medicine
from .models.bill import Bill
from .models import db
import json, os

billing_bp = Blueprint('billing', __name__)

@billing_bp.route('/billing')
def billing():
    inventory = Medicine.query.all()
    return render_template('billing.html', inventory=inventory)

@billing_bp.route('/billing/submit', methods=['POST'])
def submit_bill():
    customer_name = request.form.get('customer_name')
    items = request.form.getlist('items')
    total_price = sum([float(i.split('|')[1]) for i in items])
    now = datetime.now().strftime('%Y-%m-%d %H:%M')

    bill = Bill(
        customer_name=customer_name,
        date=now,
        total_price=total_price,
        items=json.dumps(items)
    )
    db.session.add(bill)
    db.session.commit()

    pdf_path = os.path.join('app', 'static', 'invoice.pdf')
    c = canvas.Canvas(pdf_path)
    c.drawString(100, 800, f"Medical Shop Invoice - {now}")
    c.drawString(100, 780, f"Customer: {customer_name}")
    y = 760
    for item in items:
        name, price = item.split('|')
        c.drawString(100, y, f"{name} - ₹{price}")
        y -= 20
    c.drawString(100, y - 10, f"Total: ₹{total_price}")
    c.save()

    return redirect(url_for('billing.print_bill'))

@billing_bp.route('/billing/print')
def print_bill():
    return render_template('print_bill.html')
