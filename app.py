from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
import sqlite3
from datetime import datetime
import os
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this in production!

# Flask-Login Setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

DB_NAME = "finance.db"

class User(UserMixin):
    def __init__(self, id, email, name):
        self.id = id
        self.email = email
        self.name = name

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT id, email, name FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    if user_data:
        return User(user_data[0], user_data[1], user_data[2])
    return None

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # Create Users Table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                name TEXT NOT NULL
            )
        ''')

        # Update Budget Table to include user_id
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS budget (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                month_str TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users (id),
                UNIQUE(user_id, month_str)
            )
        ''')
        
        # Update Expenses Table to include user_id
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                item TEXT NOT NULL,
                cost REAL NOT NULL,
                quantity INTEGER DEFAULT 1,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Migrations for existing tables (if any)
        try:
            cursor.execute('ALTER TABLE expenses ADD COLUMN user_id INTEGER DEFAULT 1')
        except sqlite3.OperationalError:
            pass
            
        try:
            cursor.execute('ALTER TABLE budget ADD COLUMN user_id INTEGER DEFAULT 1')
        except sqlite3.OperationalError:
            pass

        conn.commit()

# --- Auth Routes ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute('SELECT id, email, password, name FROM users WHERE email = ?', (email,))
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data and check_password_hash(user_data[2], password):
            user = User(user_data[0], user_data[1], user_data[3])
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Invalid email or password')
            
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')
        
        hashed_password = generate_password_hash(password)
        
        try:
            conn = sqlite3.connect(DB_NAME)
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (email, password, name) VALUES (?, ?, ?)', 
                         (email, hashed_password, name))
            conn.commit()
            conn.close()
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Email already exists!')
            
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# --- App Routes ---

@app.route('/')
@login_required
def index():
    return render_template('index.html', user=current_user)

@app.route('/api/budget', methods=['GET', 'POST'])
@login_required
def handle_budget():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    current_month = datetime.now().strftime('%Y-%m')
    
    if request.method == 'POST':
        data = request.json
        amount = float(data.get('amount', 0))
        # Upsert budget for the month for CURRENT USER
        cursor.execute('''
            INSERT INTO budget (user_id, amount, month_str) VALUES (?, ?, ?)
            ON CONFLICT(user_id, month_str) DO UPDATE SET amount = ?
        ''', (current_user.id, amount, current_month, amount))
        conn.commit()
        conn.close()
        return jsonify({"message": "Budget set successfully", "amount": amount})
    
    else:
        cursor.execute('SELECT amount FROM budget WHERE user_id = ? AND month_str = ?', (current_user.id, current_month))
        row = cursor.fetchone()
        conn.close()
        return jsonify({"amount": row[0] if row else 0})

@app.route('/api/expenses', methods=['GET', 'POST'])
@login_required
def handle_expenses():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        data = request.json
        item = data.get('item')
        cost = float(data.get('cost', 0))
        quantity = int(data.get('quantity', 1))
        local_time = datetime.now()
        
        cursor.execute('INSERT INTO expenses (user_id, item, cost, quantity, date_added) VALUES (?, ?, ?, ?, ?)', 
                     (current_user.id, item, cost, quantity, local_time))
        conn.commit()
        conn.close()
        return jsonify({"message": "Expense added"})
    
    else:
        cursor.execute('SELECT id, item, cost, quantity, date_added FROM expenses WHERE user_id = ? ORDER BY date_added DESC', (current_user.id,))
        rows = cursor.fetchall()
        expenses = [{"id": r[0], "item": r[1], "cost": r[2], "quantity": r[3], "date": r[4]} for r in rows]
        conn.close()
        return jsonify(expenses)

@app.route('/api/balance', methods=['GET'])
@login_required
def get_balance():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    current_month = datetime.now().strftime('%Y-%m')
    
    # Get budget for current user
    cursor.execute('SELECT amount FROM budget WHERE user_id = ? AND month_str = ?', (current_user.id, current_month))
    budget_row = cursor.fetchone()
    budget = budget_row[0] if budget_row else 0
    
    # Get total expenses for current user
    cursor.execute("SELECT SUM(cost) FROM expenses WHERE user_id = ? AND strftime('%Y-%m', date_added) = ?", (current_user.id, current_month))
    expense_row = cursor.fetchone()
    total_expenses = expense_row[0] if expense_row and expense_row[0] else 0
    
    conn.close()
    
    return jsonify({
        "budget": budget,
        "total_expenses": total_expenses,
        "remaining": budget - total_expenses
    })

@app.route('/api/reset', methods=['DELETE'])
@login_required
def reset_data():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM budget WHERE user_id = ?', (current_user.id,))
    cursor.execute('DELETE FROM expenses WHERE user_id = ?', (current_user.id,))
    conn.commit()
    conn.close()
    return jsonify({"message": "Data reset successfully"})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
