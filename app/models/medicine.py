from . import db

class Medicine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    price = db.Column(db.Float, nullable=False)
    schedule = db.Column(db.String(10))

    def __repr__(self):
        return f"<Medicine {self.name}>"