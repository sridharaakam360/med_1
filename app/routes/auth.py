from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import datetime
from ..forms import LoginForm, RegisterForm
from ..models.database import get_db
from ..utils.decorators import admin_required, login_required
from ..utils.logging import log_activity
import random, smtplib, ssl
from email.mime.text import MIMEText

auth = Blueprint('auth', __name__)
limiter = Limiter(key_func=get_remote_address)

@auth.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute")
def login():
    """Handle user login."""
    if 'user_id' in session:
        return redirect(url_for('main.index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        try:
            with get_db() as conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute('SELECT id, username, password, role FROM users WHERE username = %s', 
                             (form.username.data,))
                user = cursor.fetchone()
                
                if user and check_password_hash(user['password'], form.password.data):
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['is_admin'] = user['role'] == 'admin'
                    
                    # Update last login
                    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    cursor.execute('UPDATE users SET last_login = %s WHERE id = %s', 
                                 (now, user['id']))
                    
                    log_activity(user['id'], 'login')
                    flash(f'Welcome back, {user["username"]}!', 'success')
                    
                    next_page = request.args.get('next')
                    return redirect(next_page if next_page else url_for('main.index'))
                else:
                    flash('Invalid username or password.', 'error')
        except Exception as e:
            flash('An error occurred during login.', 'error')
    
    return render_template('auth/login.html', form=form)

@auth.route('/register', methods=['GET', 'POST'])
@admin_required
@limiter.limit("20 per day")
def register():
    """Handle user registration (admin only)."""
    form = RegisterForm()
    if form.validate_on_submit():
        try:
            with get_db() as conn:
                cursor = conn.cursor(dictionary=True)
                # Check if username exists
                cursor.execute('SELECT 1 FROM users WHERE username = %s', (form.username.data,))
                if cursor.fetchone():
                    flash('Username already exists.', 'error')
                    return render_template('auth/register.html', form=form)
                
                # Check if email exists
                cursor.execute('SELECT 1 FROM users WHERE email = %s', (form.email.data,))
                if cursor.fetchone():
                    flash('Email already registered.', 'error')
                    return render_template('auth/register.html', form=form)
                
                # Create new user
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                password_hash = generate_password_hash(form.password.data)
                cursor.execute('''INSERT INTO users (username, email, password, role, created_at)
                            VALUES (%s, %s, %s, %s, %s)''',
                         (form.username.data, form.email.data, password_hash, 'staff', now))
                
                log_activity(session['user_id'], 'user_created', f"Created user: {form.username.data}")
                flash('User registered successfully!', 'success')
                return redirect(url_for('admin.users'))
        except Exception as e:
            flash('An error occurred during registration.', 'error')
    
    return render_template('auth/register.html', form=form)

@auth.route('/logout')
def logout():
    """Handle user logout."""
    if 'user_id' in session:
        log_activity(session['user_id'], 'logout')
        session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('auth.login'))

@auth.route('/profile')
def profile():
    """Display user profile."""
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
    
    try:
        with get_db() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('SELECT username, email, role, created_at, last_login FROM users WHERE id = %s',
                         (session['user_id'],))
            user = cursor.fetchone()
            
            if user:
                return render_template('auth/profile.html', user=user)
            else:
                flash('User not found.', 'error')
                return redirect(url_for('main.index'))
    except Exception as e:
        flash('An error occurred while fetching profile.', 'error')
        return redirect(url_for('main.index'))

@auth.route('/change-password', methods=['POST'])
@login_required
def change_password():
    user_id = session['user_id']
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    if not current_password or not new_password or not confirm_password:
        flash('All fields are required.', 'danger')
        return redirect(url_for('auth.profile'))
    if new_password != confirm_password:
        flash('New passwords do not match.', 'danger')
        return redirect(url_for('auth.profile'))
    with get_db() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT password FROM users WHERE id = %s', (user_id,))
        user = cursor.fetchone()
        if not user or not check_password_hash(user['password'], current_password):
            flash('Current password is incorrect.', 'danger')
            return redirect(url_for('auth.profile'))
        cursor.execute('UPDATE users SET password = %s WHERE id = %s', (generate_password_hash(new_password), user_id))
        conn.commit()
    flash('Password changed successfully.', 'success')
    return redirect(url_for('auth.profile'))

@auth.route('/forgot-password', methods=['POST'])
def forgot_password():
    email = request.form.get('email')
    if not email:
        flash('Email is required.', 'danger')
        return redirect(url_for('auth.login'))
    with get_db() as conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute('SELECT id FROM users WHERE email = %s', (email,))
        user = cursor.fetchone()
        if not user:
            flash('No user found with that email.', 'danger')
            return redirect(url_for('auth.login'))
    otp = str(random.randint(100000, 999999))
    session['reset_otp'] = otp
    session['reset_email'] = email
    # Send OTP via email
    send_otp_email(email, otp)
    flash('OTP sent to your email. Please check your inbox.', 'info')
    return redirect(url_for('auth.verify_otp'))

@auth.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        otp = request.form.get('otp')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        if not otp or not new_password or not confirm_password:
            flash('All fields are required.', 'danger')
            return redirect(url_for('auth.verify_otp'))
        if new_password != confirm_password:
            flash('Passwords do not match.', 'danger')
            return redirect(url_for('auth.verify_otp'))
        if otp != session.get('reset_otp'):
            flash('Invalid OTP.', 'danger')
            return redirect(url_for('auth.verify_otp'))
        email = session.get('reset_email')
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET password = %s WHERE email = %s', (generate_password_hash(new_password), email))
            conn.commit()
        session.pop('reset_otp', None)
        session.pop('reset_email', None)
        flash('Password reset successful. You can now log in.', 'success')
        return redirect(url_for('auth.login'))
    return render_template('auth/verify_otp.html')

def send_otp_email(to_email, otp):
    # Use SMTP config from app config
    smtp_server = current_app.config.get('SMTP_SERVER', 'smtp.gmail.com')
    smtp_port = current_app.config.get('SMTP_PORT', 465)
    smtp_user = current_app.config.get('SMTP_USER')
    smtp_password = current_app.config.get('SMTP_PASSWORD')
    from_email = smtp_user
    msg = MIMEText(f'Your OTP for password reset is: {otp}')
    msg['Subject'] = 'Password Reset OTP'
    msg['From'] = from_email
    msg['To'] = to_email
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
        server.login(smtp_user, smtp_password)
        server.sendmail(from_email, [to_email], msg.as_string()) 
        