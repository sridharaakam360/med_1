from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from datetime import datetime
from ..forms import RegisterForm, EditUserForm
from ..models.database import get_db
from ..utils.decorators import admin_required
from ..utils.logging import log_activity
from werkzeug.security import generate_password_hash

admin = Blueprint('admin', __name__)

@admin.route('/users')
@admin_required
def users():
    """List all users (admin only)."""
    try:
        with get_db() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute('''SELECT id, username, email, role, created_at, last_login 
                        FROM users ORDER BY created_at DESC''')
            users = cursor.fetchall()
        return render_template('admin/users.html', users=users)
    except Exception as e:
        flash('An error occurred while fetching users.', 'error')
        return redirect(url_for('main.index'))

@admin.route('/users/register', methods=['GET', 'POST'])
@admin_required
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
                    return render_template('admin/register.html', form=form)
                
                # Check if email exists
                cursor.execute('SELECT 1 FROM users WHERE email = %s', (form.email.data,))
                if cursor.fetchone():
                    flash('Email already registered.', 'error')
                    return render_template('admin/register.html', form=form)
                
                # Create new user
                now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                password_hash = generate_password_hash(form.password.data)
                cursor.execute('''INSERT INTO users (username, email, password_hash, role, created_at)
                            VALUES (%s, %s, %s, %s, %s)''',
                         (form.username.data, form.email.data, password_hash, 'staff', now))
                
                log_activity(session['user_id'], 'user_created', f"Created user: {form.username.data}")
                flash('User registered successfully!', 'success')
                return redirect(url_for('admin.users'))
        except Exception as e:
            flash('An error occurred during registration.', 'error')
    
    return render_template('admin/register.html', form=form)

@admin.route('/users/edit/<int:user_id>', methods=['GET', 'POST'])
@admin_required
def edit_user(user_id):
    """Edit a user (admin only)."""
    form = EditUserForm()
    
    try:
        with get_db() as conn:
            cursor = conn.cursor(dictionary=True)
            
            if request.method == 'GET':
                cursor.execute('SELECT username, email, role FROM users WHERE id = %s', (user_id,))
                user = cursor.fetchone()
                if not user:
                    flash('User not found.', 'error')
                    return redirect(url_for('admin.users'))
                
                form.username.data = user['username']
                form.email.data = user['email']
                form.role.data = user['role']
            
            if form.validate_on_submit():
                # Check if username exists for other users
                cursor.execute('SELECT 1 FROM users WHERE username = %s AND id != %s', 
                             (form.username.data, user_id))
                if cursor.fetchone():
                    flash('Username already exists.', 'error')
                    return render_template('admin/edit_user.html', form=form, user_id=user_id)
                
                # Check if email exists for other users
                cursor.execute('SELECT 1 FROM users WHERE email = %s AND id != %s', 
                             (form.email.data, user_id))
                if cursor.fetchone():
                    flash('Email already registered.', 'error')
                    return render_template('admin/edit_user.html', form=form, user_id=user_id)
                
                # Update user
                cursor.execute('''UPDATE users 
                           SET username = %s, email = %s, role = %s
                           WHERE id = %s''',
                         (form.username.data, form.email.data, form.role.data, user_id))
                
                log_activity(session['user_id'], 'user_updated', f"Updated user: {form.username.data}")
                flash('User updated successfully!', 'success')
                return redirect(url_for('admin.users'))
                
        return render_template('admin/edit_user.html', form=form, user_id=user_id)
    except Exception as e:
        flash('An error occurred while editing the user.', 'error')
        return redirect(url_for('admin.users'))

@admin.route('/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    """Delete a user (admin only)."""
    try:
        with get_db() as conn:
            cursor = conn.cursor(dictionary=True)
            # Check if user exists and is not an admin
            cursor.execute('SELECT role FROM users WHERE id = %s', (user_id,))
            user = cursor.fetchone()
            
            if not user:
                flash('User not found.', 'error')
                return redirect(url_for('admin.users'))
            
            if user['role'] == 'admin':
                flash('Cannot delete admin user.', 'error')
                return redirect(url_for('admin.users'))
            
            # Delete user's activity logs
            cursor.execute('DELETE FROM activity_logs WHERE user_id = %s', (user_id,))
            
            # Delete user
            cursor.execute('DELETE FROM users WHERE id = %s', (user_id,))
            
            log_activity(session['user_id'], 'user_deleted', f"Deleted user ID: {user_id}")
            flash('User deleted successfully!', 'success')
            
        return redirect(url_for('admin.users'))
    except Exception as e:
        flash('An error occurred while deleting the user.', 'error')
        return redirect(url_for('admin.users')) 