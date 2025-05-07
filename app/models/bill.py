from . import db

class Bill(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    date = db.Column(db.String(100), nullable=False)
    total_price = db.Column(db.Float, nullable=False)
    items = db.Column(db.Text, nullable=False)  # JSON string of items

    def __repr__(self):
        return f"<Bill {self.customer_name} - {self.date}>"