from flask_wtf import FlaskForm
from wtforms import StringField, IntegerField, FloatField, DateField, SelectField, PasswordField, EmailField, BooleanField, TextAreaField, SubmitField
from wtforms.validators import DataRequired, NumberRange, Email, Length, EqualTo, Optional

class ProductForm(FlaskForm):
    name = StringField('Product Name', validators=[DataRequired()])
    description = StringField('Description', validators=[Optional()])
    quantity = IntegerField('Quantity', validators=[DataRequired(), NumberRange(min=0)])
    min_quantity = IntegerField('Minimum Quantity', validators=[DataRequired(), NumberRange(min=0)])
    price = FloatField('Price', validators=[DataRequired(), NumberRange(min=0)])
    expiry_date = DateField('Expiry Date', validators=[DataRequired()])
    supplier_id = SelectField('Supplier', coerce=int, validators=[Optional()])
    is_scheduled = BooleanField('Scheduled Drug')
    schedule_type = SelectField('Schedule Type', 
                              choices=[('', 'Select Schedule Type'), 
                                     ('H', 'Schedule H'),
                                     ('H1', 'Schedule H1')],
                              validators=[Optional()])
    submit = SubmitField('Submit')

class SupplierForm(FlaskForm):
    name = StringField('Supplier Name', validators=[DataRequired()])
    contact_person = StringField('Contact Person', validators=[DataRequired()])
    phone = StringField('Phone Number', validators=[DataRequired()])
    email = EmailField('Email', validators=[Optional(), Email()])
    address = StringField('Address', validators=[Optional()])
    submit = SubmitField('Submit')

class BillingForm(FlaskForm):
    customer_name = StringField('Customer Name', validators=[
        DataRequired(),
        Length(min=2, max=100, message='Name must be between 2 and 100 characters')
    ])
    customer_phone = StringField('Phone Number', validators=[
        Length(max=15, message='Phone number must not exceed 15 characters')
    ])
    customer_email = EmailField('Email', validators=[
        Optional(),
        Email(message='Please enter a valid email address')
    ])
    payment_method = SelectField('Payment Method', choices=[
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('upi', 'UPI')
    ], validators=[DataRequired()])
    submit = SubmitField('Create Bill')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Login')

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
    submit = SubmitField('Register')

class EditUserForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=50)])
    email = EmailField('Email', validators=[DataRequired(), Email()])
    role = SelectField('Role', choices=[('staff', 'Staff'), ('admin', 'Admin')], validators=[DataRequired()])
    submit = SubmitField('Update User') 