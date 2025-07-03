
"""
O-kharcha - Smart Expenditure Management System for Nepal
Developer: Bigyan Bhandari
All Rights Reserved © 2025
Made with love for Nepal 🇳🇵
"""

from flask import Flask, request, jsonify, render_template, redirect, url_for, send_from_directory, session
import sqlite3
import re
import json
from datetime import datetime, timedelta
import os
from functools import wraps
import hashlib

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'okharcha-secret-key-nepal')

# Developer/Admin access control
ADMIN_USERS = {
    'Bigyan Bhandari': 'YOUARETHEPHILOSOPHER',
    'manager': 'CLEANMONEY'
}

def hash_password(password):
    """Hash password for storage"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, hashed):
    """Verify password against hash"""
    return hashlib.sha256(password.encode()).hexdigest() == hashed

def authenticate_user(username, password):
    """Authenticate regular user"""
    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()
    cursor.execute('SELECT password_hash FROM users WHERE username = ?', (username,))
    result = cursor.fetchone()
    conn.close()
    
    if result and verify_password(password, result[0]):
        return True
    return False

def authenticate_admin(username, password):
    """Authenticate admin user"""
    return ADMIN_USERS.get(username) == password

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def require_admin(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin_user' not in session:
            return jsonify({'error': 'Admin authentication required'}), 401
        return f(*args, **kwargs)
    return decorated_function

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Database initialization
def init_db():
    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()

    # Create users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            email TEXT,
            full_name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Check if existing tables need migration
    cursor.execute("PRAGMA table_info(expenses)")
    expenses_columns = [column[1] for column in cursor.fetchall()]
    
    if 'user_id' not in expenses_columns:
        # Migration needed - backup and recreate tables
        print("🔄 Migrating database schema...")
        
        # Backup existing data
        cursor.execute('SELECT * FROM expenses')
        old_expenses = cursor.fetchall()
        
        cursor.execute('SELECT * FROM budget')
        old_budget = cursor.fetchall()
        
        # Drop old tables
        cursor.execute('DROP TABLE IF EXISTS expenses')
        cursor.execute('DROP TABLE IF EXISTS budget')
        cursor.execute('DROP TABLE IF EXISTS daily_notes')
        cursor.execute('DROP TABLE IF EXISTS travel_expenses')
        cursor.execute('DROP TABLE IF EXISTS money_collection')

    # Create expenses table with user_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL DEFAULT 1,
            amount REAL NOT NULL,
            description TEXT,
            category TEXT DEFAULT 'general',
            date TEXT NOT NULL,
            type TEXT DEFAULT 'expense',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Create budget table with user_id
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budget (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL DEFAULT 1,
            monthly_limit REAL NOT NULL,
            current_spent REAL DEFAULT 0,
            month_year TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Create daily notes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL DEFAULT 1,
            note TEXT NOT NULL,
            date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Create daily memos table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_memos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL DEFAULT 1,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            priority INTEGER DEFAULT 1,
            date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Create bills table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL DEFAULT 1,
            bill_type TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            due_date TEXT,
            paid_date TEXT,
            status TEXT DEFAULT 'pending',
            month_year TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Create travel expenses table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS travel_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL DEFAULT 1,
            destination TEXT NOT NULL,
            amount REAL NOT NULL,
            description TEXT,
            date TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Create money collection table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS money_collection (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL DEFAULT 1,
            amount REAL NOT NULL,
            from_person TEXT,
            description TEXT,
            date TEXT NOT NULL,
            type TEXT DEFAULT 'received',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    conn.commit()
    conn.close()

def get_user_id():
    """Get current user's ID from session"""
    if 'user' not in session:
        return None
    
    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE username = ?', (session['user'],))
    result = cursor.fetchone()
    conn.close()
    
    return result[0] if result else None

# SMS Parser for Nepali banks
def parse_sms_amount(sms_text):
    """Parse amount from SMS text using regex patterns for Nepali banks"""
    patterns = [
        r'(?:Rs\.?|NPR|रु\.?)\s*([0-9,]+(?:\.[0-9]{2})?)',
        r'(?:debited|credited|spent|received)\s+(?:Rs\.?|NPR|रु\.?)\s*([0-9,]+(?:\.[0-9]{2})?)',
        r'(?:amount|amt)\s+(?:Rs\.?|NPR|रु\.?)\s*([0-9,]+(?:\.[0-9]{2})?)',
        r'([0-9,]+(?:\.[0-9]{2})?)\s*(?:Rs\.?|NPR|रु\.?)',
    ]

    for pattern in patterns:
        match = re.search(pattern, sms_text, re.IGNORECASE)
        if match:
            amount_str = match.group(1).replace(',', '')
            try:
                return float(amount_str)
            except ValueError:
                continue
    return None

def get_current_month_year():
    return datetime.now().strftime('%Y-%m')

def get_monthly_budget(user_id):
    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()
    current_month = get_current_month_year()

    cursor.execute('SELECT monthly_limit, current_spent FROM budget WHERE user_id = ? AND month_year = ?', (user_id, current_month))
    result = cursor.fetchone()
    conn.close()

    if result:
        return result[0], result[1]
    return 0, 0

def update_monthly_spent(user_id, amount):
    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()
    current_month = get_current_month_year()

    # Check if budget entry exists for current month
    cursor.execute('SELECT id, monthly_limit, current_spent FROM budget WHERE user_id = ? AND month_year = ?', (user_id, current_month))
    result = cursor.fetchone()

    if result:
        # Update existing budget
        budget_id, monthly_limit, current_spent = result
        new_spent = current_spent + amount
        cursor.execute('''
            UPDATE budget SET current_spent = ? WHERE id = ?
        ''', (new_spent, budget_id))
    else:
        # Create new budget entry with 0 limit if none exists
        cursor.execute('''
            INSERT INTO budget (user_id, monthly_limit, current_spent, month_year)
            VALUES (?, 0, ?, ?)
        ''', (user_id, amount, current_month))

    conn.commit()
    conn.close()

# Routes
@app.route('/')
@login_required
def index():
    user = session.get('user')
    return render_template('index.html', user=user)

@app.route('/database-access')
def database_access():
    return render_template('admin_login.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/admin')
def admin_login():
    return render_template('admin_login.html')

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_user' not in session:
        return redirect(url_for('admin_login'))
    return render_template('admin_dashboard.html', admin_user=session['admin_user'])

@app.route('/api/register', methods=['POST'])
def api_register():
    """Handle user registration"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email', '')
    full_name = data.get('full_name', '')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    if len(password) < 6:
        return jsonify({'error': 'Password must be at least 6 characters'}), 400
    
    # Check if username already exists
    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
    if cursor.fetchone():
        conn.close()
        return jsonify({'error': 'Username already exists'}), 400
    
    # Create new user
    password_hash = hash_password(password)
    cursor.execute('''
        INSERT INTO users (username, password_hash, email, full_name)
        VALUES (?, ?, ?, ?)
    ''', (username, password_hash, email, full_name))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': f'Account created successfully! Welcome {username}!'
    })

@app.route('/api/login', methods=['POST'])
def api_login():
    """Handle user login"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    if authenticate_user(username, password):
        session['user'] = username
        return jsonify({
            'success': True,
            'message': f'Welcome back {username}! Login successful.',
            'user': username
        })
    else:
        return jsonify({'error': 'Invalid credentials'}), 401

@app.route('/api/admin/login', methods=['POST'])
def api_admin_login():
    """Handle admin login"""
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    
    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400
    
    if authenticate_admin(username, password):
        session['admin_user'] = username
        return jsonify({
            'success': True,
            'message': f'Admin access granted for {username}!',
            'admin_user': username
        })
    else:
        return jsonify({'error': 'Invalid admin credentials'}), 401

@app.route('/api/logout', methods=['POST'])
def api_logout():
    """Handle logout"""
    session.pop('user', None)
    session.pop('admin_user', None)
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/add_note', methods=['POST'])
@require_auth
def add_note():
    """Add daily note"""
    data = request.get_json()
    note = data.get('note', '')
    
    if not note:
        return jsonify({'error': 'Note content required'}), 400
    
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 401
    
    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        INSERT INTO daily_notes (user_id, note, date)
        VALUES (?, ?, ?)
    ''', (user_id, note, today))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': 'Daily note added successfully!'
    })

@app.route('/api/add_memo', methods=['POST'])
@require_auth
def add_memo():
    """Add daily memo"""
    data = request.get_json()
    title = data.get('title', '')
    content = data.get('content', '')
    priority = data.get('priority', 1)
    
    if not title or not content:
        return jsonify({'error': 'Title and content required'}), 400
    
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 401
    
    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()
    
    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        INSERT INTO daily_memos (user_id, title, content, priority, date)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, title, content, priority, today))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': 'Daily memo added successfully!'
    })

@app.route('/api/memos', methods=['GET'])
@require_auth
def get_memos():
    """Get user's daily memos"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 401
    
    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, title, content, priority, date, created_at FROM daily_memos 
        WHERE user_id = ? ORDER BY priority DESC, created_at DESC LIMIT 50
    ''', (user_id,))
    
    memos = cursor.fetchall()
    conn.close()
    
    memo_list = []
    for memo in memos:
        memo_list.append({
            'id': memo[0],
            'title': memo[1],
            'content': memo[2],
            'priority': memo[3],
            'date': memo[4],
            'created_at': memo[5]
        })
    
    return jsonify({'memos': memo_list})

@app.route('/api/add_bill', methods=['POST'])
@require_auth
def add_bill():
    """Add bill"""
    data = request.get_json()
    bill_type = data.get('bill_type', '')
    amount = data.get('amount', 0)
    description = data.get('description', '')
    due_date = data.get('due_date', '')
    
    if not bill_type or amount <= 0:
        return jsonify({'error': 'Bill type and valid amount required'}), 400
    
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 401
    
    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()
    
    current_month = get_current_month_year()
    cursor.execute('''
        INSERT INTO bills (user_id, bill_type, amount, description, due_date, month_year)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, bill_type, amount, description, due_date, current_month))
    
    conn.commit()
    conn.close()
    
    return jsonify({
        'success': True,
        'message': f'{bill_type} bill of Rs. {amount} added successfully!'
    })

@app.route('/api/bills', methods=['GET'])
@require_auth
def get_bills():
    """Get user's bills"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 401
    
    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, bill_type, amount, description, due_date, paid_date, status, month_year, created_at 
        FROM bills WHERE user_id = ? ORDER BY created_at DESC LIMIT 50
    ''', (user_id,))
    
    bills = cursor.fetchall()
    conn.close()
    
    bill_list = []
    for bill in bills:
        bill_list.append({
            'id': bill[0],
            'bill_type': bill[1],
            'amount': bill[2],
            'description': bill[3],
            'due_date': bill[4],
            'paid_date': bill[5],
            'status': bill[6],
            'month_year': bill[7],
            'created_at': bill[8]
        })
    
    return jsonify({'bills': bill_list})

@app.route('/api/pay_bill/<int:bill_id>', methods=['POST'])
@require_auth
def pay_bill(bill_id):
    """Mark bill as paid"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 401
    
    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()
    
    # Check if bill belongs to user
    cursor.execute('SELECT amount, bill_type FROM bills WHERE id = ? AND user_id = ?', (bill_id, user_id))
    result = cursor.fetchone()
    
    if not result:
        conn.close()
        return jsonify({'error': 'Bill not found'}), 404
    
    amount, bill_type = result
    today = datetime.now().strftime('%Y-%m-%d')
    
    # Mark as paid
    cursor.execute('''
        UPDATE bills SET status = 'paid', paid_date = ? WHERE id = ?
    ''', (today, bill_id))
    
    # Add to expenses
    cursor.execute('''
        INSERT INTO expenses (user_id, amount, description, category, date, type)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, amount, f'{bill_type} Bill Payment', 'bills', today, 'expense'))
    
    conn.commit()
    conn.close()
    
    # Update monthly spent
    update_monthly_spent(user_id, amount)
    
    return jsonify({
        'success': True,
        'message': f'{bill_type} bill marked as paid and added to expenses!'
    })

@app.route('/api/notes', methods=['GET'])
@require_auth
def get_notes():
    """Get user's daily notes"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 401
    
    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, note, date, created_at FROM daily_notes 
        WHERE user_id = ? ORDER BY created_at DESC LIMIT 30
    ''', (user_id,))
    
    notes = cursor.fetchall()
    conn.close()
    
    note_list = []
    for note in notes:
        note_list.append({
            'id': note[0],
            'note': note[1],
            'date': note[2],
            'created_at': note[3]
        })
    
    return jsonify({'notes': note_list})

@app.route('/api/parse_sms', methods=['POST'])
@require_auth
def parse_sms():
    """Parse SMS and extract expense information"""
    data = request.get_json()
    sms_text = data.get('message', '')

    if not sms_text:
        return jsonify({'error': 'No SMS text provided'}), 400

    # Check if SMS is from known bank
    bank_keywords = ['NIMB', 'NABILBNK', 'GLOBALIME', 'SANIMA', 'HIMALAYAN', 'NIC', 'STANDARD']
    is_bank_sms = any(keyword in sms_text.upper() for keyword in bank_keywords)

    if not is_bank_sms:
        return jsonify({'error': 'SMS not from recognized bank'}), 400

    amount = parse_sms_amount(sms_text)
    if amount is None:
        return jsonify({'error': 'Could not parse amount from SMS'}), 400

    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 401

    # Add expense automatically
    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()

    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        INSERT INTO expenses (user_id, amount, description, category, date, type)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, amount, sms_text[:100], 'auto-sms', today, 'expense'))

    conn.commit()
    conn.close()

    # Update monthly spent
    update_monthly_spent(user_id, amount)

    # Check budget warning
    monthly_limit, current_spent = get_monthly_budget(user_id)
    remaining = monthly_limit - current_spent
    warning = ""

    if remaining <= 0:
        warning = "⚠️ Budget exceeded! Please control your spending."
    elif remaining <= monthly_limit * 0.2:
        warning = f"⚠️ Warning: Only Rs. {remaining:.2f} left this month!"

    return jsonify({
        'success': True,
        'amount': amount,
        'remaining': remaining,
        'warning': warning,
        'message': f'Expense of Rs. {amount} added automatically from SMS'
    })

@app.route('/api/set_budget', methods=['POST'])
@require_auth
def set_budget():
    """Set monthly budget limit"""
    data = request.get_json()
    monthly_limit = data.get('limit', 0)

    if monthly_limit <= 0:
        return jsonify({'error': 'Invalid budget limit'}), 400

    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 401

    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()
    current_month = get_current_month_year()

    # Get current spent amount
    cursor.execute('SELECT current_spent FROM budget WHERE user_id = ? AND month_year = ?', (user_id, current_month))
    result = cursor.fetchone()
    current_spent = result[0] if result else 0

    cursor.execute('''
        INSERT OR REPLACE INTO budget (user_id, monthly_limit, current_spent, month_year)
        VALUES (?, ?, ?, ?)
    ''', (user_id, monthly_limit, current_spent, current_month))

    conn.commit()
    conn.close()

    remaining = monthly_limit - current_spent
    return jsonify({
        'success': True,
        'message': f'Monthly budget set to Rs. {monthly_limit}',
        'remaining': remaining
    })

@app.route('/api/add_expense', methods=['POST'])
@require_auth
def add_expense():
    """Add manual expense"""
    data = request.get_json()
    amount = data.get('amount', 0)
    description = data.get('description', '')
    category = data.get('category', 'general')

    if amount <= 0:
        return jsonify({'error': 'Invalid amount'}), 400

    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 401

    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()

    today = datetime.now().strftime('%Y-%m-%d')
    cursor.execute('''
        INSERT INTO expenses (user_id, amount, description, category, date, type)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, amount, description, category, today, 'expense'))

    conn.commit()
    conn.close()

    # Update monthly spent
    update_monthly_spent(user_id, amount)

    # Check budget warning
    monthly_limit, current_spent = get_monthly_budget(user_id)
    remaining = monthly_limit - current_spent
    warning = ""

    if remaining <= 0:
        warning = "⚠️ Budget exceeded! Please control your spending."
    elif remaining <= monthly_limit * 0.2:
        warning = f"⚠️ Warning: Only Rs. {remaining:.2f} left this month!"

    return jsonify({
        'success': True,
        'message': f'Expense of Rs. {amount} added successfully',
        'remaining': remaining,
        'warning': warning
    })

@app.route('/api/budget_status', methods=['GET'])
@require_auth
def budget_status():
    """Get current budget status"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 401

    monthly_limit, current_spent = get_monthly_budget(user_id)
    remaining = monthly_limit - current_spent

    # Calculate percentage spent
    percentage_spent = (current_spent / monthly_limit * 100) if monthly_limit > 0 else 0

    return jsonify({
        'monthly_limit': monthly_limit,
        'current_spent': current_spent,
        'remaining': remaining,
        'percentage_spent': percentage_spent
    })

@app.route('/api/expenses', methods=['GET'])
@require_auth
def get_expenses():
    """Get expenses with optional date range"""
    filter_type = request.args.get('filter', 'all')
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 401

    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()

    today = datetime.now()

    if filter_type == 'today':
        date_filter = today.strftime('%Y-%m-%d')
        cursor.execute('SELECT * FROM expenses WHERE user_id = ? AND date = ? ORDER BY created_at DESC', (user_id, date_filter))
    elif filter_type == 'week':
        week_start = (today - timedelta(days=7)).strftime('%Y-%m-%d')
        cursor.execute('SELECT * FROM expenses WHERE user_id = ? AND date >= ? ORDER BY created_at DESC', (user_id, week_start))
    elif filter_type == 'month':
        month_start = today.replace(day=1).strftime('%Y-%m-%d')
        cursor.execute('SELECT * FROM expenses WHERE user_id = ? AND date >= ? ORDER BY created_at DESC', (user_id, month_start))
    else:
        cursor.execute('SELECT * FROM expenses WHERE user_id = ? ORDER BY created_at DESC LIMIT 50', (user_id,))

    expenses = cursor.fetchall()
    conn.close()

    expense_list = []
    for expense in expenses:
        expense_list.append({
            'id': expense[0],
            'user_id': expense[1],
            'amount': expense[2],
            'description': expense[3],
            'category': expense[4],
            'date': expense[5],
            'type': expense[6],
            'created_at': expense[7]
        })

    return jsonify({'expenses': expense_list})

@app.route('/api/financial_advice', methods=['GET'])
@require_auth
def get_financial_advice():
    """Get financial advice and tips"""
    advice_list = [
        {
            'title': '50/30/20 Rule',
            'description': 'Allocate 50% for needs, 30% for wants, and 20% for savings and debt repayment.',
            'tip': 'Track your expenses to see if you are following this rule effectively.'
        },
        {
            'title': 'Emergency Fund',
            'description': 'Build an emergency fund covering 3-6 months of expenses.',
            'tip': 'Start with Rs. 1000 and gradually increase your emergency fund.'
        },
        {
            'title': 'Avoid Impulse Buying',
            'description': 'Wait 24 hours before making non-essential purchases.',
            'tip': 'Make a shopping list and stick to it to avoid unnecessary expenses.'
        },
        {
            'title': 'Track Daily Expenses',
            'description': 'Monitor your daily spending to identify patterns and areas for improvement.',
            'tip': 'Use O-kharcha to automatically track your bank SMS alerts.'
        },
        {
            'title': 'Review Monthly Budget',
            'description': 'Regularly review and adjust your monthly budget based on actual spending.',
            'tip': 'Analyze your spending categories to optimize your budget allocation.'
        }
    ]

    return jsonify({'financial_advice': advice_list})

@app.route('/api/fifty_thirty_twenty', methods=['GET'])
@require_auth
def fifty_thirty_twenty_analysis():
    """Analyze expenses using 50/30/20 rule"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 401

    monthly_limit, current_spent = get_monthly_budget(user_id)

    if monthly_limit == 0:
        return jsonify({'error': 'Please set a monthly budget first'}), 400

    # Calculate 50/30/20 allocations
    needs_budget = monthly_limit * 0.5
    wants_budget = monthly_limit * 0.3
    savings_budget = monthly_limit * 0.2

    # Get current month expenses by category
    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()
    current_month = get_current_month_year()

    cursor.execute('''
        SELECT category, SUM(amount) FROM expenses 
        WHERE user_id = ? AND strftime('%Y-%m', date) = ? AND type = 'expense'
        GROUP BY category
    ''', (user_id, current_month))

    category_spending = dict(cursor.fetchall())
    conn.close()

    # Categorize spending (simplified)
    needs_categories = ['food', 'utilities', 'rent', 'transport', 'auto-sms']
    wants_categories = ['entertainment', 'shopping', 'dining', 'travel']

    needs_spent = sum(category_spending.get(cat, 0) for cat in needs_categories)
    wants_spent = sum(category_spending.get(cat, 0) for cat in wants_categories)
    other_spent = current_spent - needs_spent - wants_spent

    return jsonify({
        'budget_breakdown': {
            'needs': {'allocated': needs_budget, 'spent': needs_spent, 'remaining': needs_budget - needs_spent},
            'wants': {'allocated': wants_budget, 'spent': wants_spent, 'remaining': wants_budget - wants_spent},
            'savings': {'allocated': savings_budget, 'spent': 0, 'remaining': savings_budget}
        },
        'other_spent': other_spent,
        'total_budget': monthly_limit,
        'total_spent': current_spent
    })

@app.route('/api/stats', methods=['GET'])
@require_auth
def get_dashboard_stats():
    """Get dashboard statistics"""
    user_id = get_user_id()
    if not user_id:
        return jsonify({'error': 'User not found'}), 401

    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()

    # Get current month stats
    current_month = get_current_month_year()

    # Total expenses this month
    cursor.execute('''
        SELECT COUNT(*), SUM(amount) FROM expenses 
        WHERE user_id = ? AND strftime('%Y-%m', date) = ? AND type = 'expense'
    ''', (user_id, current_month))
    expense_count, total_expenses = cursor.fetchone()
    total_expenses = total_expenses or 0

    # Total income this month
    cursor.execute('''
        SELECT SUM(amount) FROM expenses 
        WHERE user_id = ? AND strftime('%Y-%m', date) = ? AND type = 'income'
    ''', (user_id, current_month))
    total_income = cursor.fetchone()[0] or 0

    # Category-wise spending
    cursor.execute('''
        SELECT category, SUM(amount) FROM expenses 
        WHERE user_id = ? AND strftime('%Y-%m', date) = ? AND type = 'expense'
        GROUP BY category ORDER BY SUM(amount) DESC
    ''', (user_id, current_month))
    category_spending = cursor.fetchall()

    # Daily spending trend (last 7 days)
    cursor.execute('''
        SELECT date, SUM(amount) FROM expenses 
        WHERE user_id = ? AND date >= date('now', '-7 days') AND type = 'expense'
        GROUP BY date ORDER BY date
    ''', (user_id,))
    daily_trend = cursor.fetchall()

    conn.close()

    return jsonify({
        'expense_count': expense_count or 0,
        'total_expenses': total_expenses,
        'total_income': total_income,
        'category_spending': category_spending,
        'daily_trend': daily_trend,
        'net_balance': total_income - total_expenses
    })

# Admin Routes
@app.route('/api/admin/users', methods=['GET'])
@require_admin
def get_all_users():
    """Get all users and their statistics"""
    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()

    # Get all users with their statistics
    cursor.execute('''
        SELECT u.id, u.username, u.email, u.full_name, u.created_at,
               COUNT(e.id) as expense_count,
               COALESCE(SUM(CASE WHEN e.type = 'expense' THEN e.amount ELSE 0 END), 0) as total_expenses,
               COALESCE(SUM(CASE WHEN e.type = 'income' THEN e.amount ELSE 0 END), 0) as total_income
        FROM users u
        LEFT JOIN expenses e ON u.id = e.user_id
        GROUP BY u.id, u.username, u.email, u.full_name, u.created_at
        ORDER BY u.created_at DESC
    ''')
    
    users = cursor.fetchall()
    conn.close()

    user_list = []
    for user in users:
        user_list.append({
            'id': user[0],
            'username': user[1],
            'email': user[2],
            'full_name': user[3],
            'created_at': user[4],
            'expense_count': user[5],
            'total_expenses': user[6],
            'total_income': user[7],
            'net_balance': user[7] - user[6]
        })

    return jsonify({'users': user_list})

@app.route('/api/admin/user/<int:user_id>/expenses', methods=['GET'])
@require_admin
def get_user_expenses(user_id):
    """Get specific user's expenses"""
    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()

    cursor.execute('''
        SELECT e.*, u.username FROM expenses e
        JOIN users u ON e.user_id = u.id
        WHERE e.user_id = ?
        ORDER BY e.created_at DESC
        LIMIT 100
    ''', (user_id,))
    
    expenses = cursor.fetchall()
    conn.close()

    expense_list = []
    for expense in expenses:
        expense_list.append({
            'id': expense[0],
            'user_id': expense[1],
            'amount': expense[2],
            'description': expense[3],
            'category': expense[4],
            'date': expense[5],
            'type': expense[6],
            'created_at': expense[7],
            'username': expense[8]
        })

    return jsonify({'expenses': expense_list})

@app.route('/api/admin/delete/user/<int:user_id>', methods=['DELETE'])
@require_admin
def delete_user(user_id):
    """Delete user and all their data"""
    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()

    # Delete all user data
    cursor.execute('DELETE FROM expenses WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM budget WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM daily_notes WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM travel_expenses WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM money_collection WHERE user_id = ?', (user_id,))
    cursor.execute('DELETE FROM users WHERE id = ?', (user_id,))

    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'message': f'User and all associated data deleted successfully'
    })

@app.route('/api/admin/delete/expense/<int:expense_id>', methods=['DELETE'])
@require_admin
def delete_expense(expense_id):
    """Delete specific expense"""
    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()

    cursor.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
    
    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'message': 'Expense deleted successfully'
    })

@app.route('/api/admin/stats', methods=['GET'])
@require_admin
def get_admin_stats():
    """Get overall system statistics"""
    conn = sqlite3.connect('okharcha.db')
    cursor = conn.cursor()

    # Total users
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]

    # Total expenses
    cursor.execute('SELECT COUNT(*), SUM(amount) FROM expenses WHERE type = "expense"')
    total_expense_count, total_expense_amount = cursor.fetchone()
    total_expense_amount = total_expense_amount or 0

    # Total income
    cursor.execute('SELECT SUM(amount) FROM expenses WHERE type = "income"')
    total_income = cursor.fetchone()[0] or 0

    # Active users (users with expenses in last 30 days)
    cursor.execute('''
        SELECT COUNT(DISTINCT user_id) FROM expenses 
        WHERE created_at >= date('now', '-30 days')
    ''')
    active_users = cursor.fetchone()[0]

    conn.close()

    return jsonify({
        'total_users': total_users,
        'total_expense_count': total_expense_count or 0,
        'total_expense_amount': total_expense_amount,
        'total_income': total_income,
        'active_users': active_users,
        'net_balance': total_income - total_expense_amount
    })

if __name__ == '__main__':
    init_db()

    print("🪙 O-kharcha - Smart Expenditure Management System")
    print("📱 Developer: Bigyan Bhandari")
    print("🇳🇵 Made with love for Nepal")
    print("🔧 Multi-user database system initialized")

    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'True').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
