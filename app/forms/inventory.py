from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SubmitField, EmailField
from wtforms.validators import DataRequired, Email

class SupplierForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    contact_person = StringField('Contact Person', validators=[DataRequired()])
    phone = StringField('Phone', validators=[DataRequired()])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    address = TextAreaField('Address', validators=[DataRequired()])
    submit = SubmitField('Submit') 