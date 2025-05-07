from flask import Blueprint, render_template, request, redirect, url_for
from .models.medicine import Medicine
from .models import db

inventory_bp = Blueprint('inventory', __name__)

@inventory_bp.route('/inventory')
def inventory():
    inventory_list = Medicine.query.all()
    return render_template('inventory.html', inventory=inventory_list)

@inventory_bp.route('/inventory/add', methods=['POST'])
def add_medicine():
    name = request.form.get('name')
    price = float(request.form.get('price'))
    schedule = request.form.get('schedule')
    new_medicine = Medicine(name=name, price=price, schedule=schedule)
    db.session.add(new_medicine)
    db.session.commit()
    return redirect(url_for('inventory.inventory'))

@inventory_bp.route('/inventory/delete/<int:medicine_id>')
def delete_medicine(medicine_id):
    medicine = Medicine.query.get_or_404(medicine_id)
    db.session.delete(medicine)
    db.session.commit()
    return redirect(url_for('inventory.inventory'))
