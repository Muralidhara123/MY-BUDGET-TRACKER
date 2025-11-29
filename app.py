from flask import Flask, render_template, request, jsonify
import sqlite3
from datetime import datetime
import os

app = Flask(__name__)
DB_NAME = "finance.db"

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS budget (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                amount REAL NOT NULL,
                month_str TEXT UNIQUE NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                item TEXT NOT NULL,
                cost REAL NOT NULL,
                quantity INTEGER DEFAULT 1,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Migration: Attempt to add quantity column if it doesn't exist (for existing DBs)
        try:
            cursor.execute('ALTER TABLE expenses ADD COLUMN quantity INTEGER DEFAULT 1')
        except sqlite3.OperationalError:
            pass # Column already exists
            
        conn.commit()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/budget', methods=['GET', 'POST'])
def handle_budget():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    current_month = datetime.now().strftime('%Y-%m')
    
    if request.method == 'POST':
        data = request.json
        amount = float(data.get('amount', 0))
        # Upsert budget for the month
        cursor.execute('''
            INSERT INTO budget (amount, month_str) VALUES (?, ?)
            ON CONFLICT(month_str) DO UPDATE SET amount = ?
        ''', (amount, current_month, amount))
        conn.commit()
        conn.close()
        return jsonify({"message": "Budget set successfully", "amount": amount})
    
    else:
        cursor.execute('SELECT amount FROM budget WHERE month_str = ?', (current_month,))
        row = cursor.fetchone()
        conn.close()
        return jsonify({"amount": row[0] if row else 0})

@app.route('/api/expenses', methods=['GET', 'POST'])
def handle_expenses():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        data = request.json
        item = data.get('item')
        cost = float(data.get('cost', 0))
        quantity = int(data.get('quantity', 1))
        
        # Calculate total cost for this entry (Unit Cost * Quantity) or is Cost the total?
        # Usually "how much cost it is" implies total or unit. 
        # Let's assume the user enters the TOTAL cost for the batch, or Unit cost?
        # "what i brought and how much cost it is" -> usually "I bought 2 apples for $5".
        # But if I buy 2 apples, maybe I want to say "Apples", Qty: 2, Cost: 5 (Total).
        # OR Cost: 2.5 (Unit).
        # Let's stick to: User enters Cost (Total) and Quantity. 
        # If they want unit cost, they can do math. 
        # Actually, standard is usually Unit Price * Qty = Total.
        # But for a simple expense tracker: "I spent $50 on 2 shirts". 
        # So Cost is the amount deducted from budget. Quantity is just metadata.
        
        # Use local system time explicitly
        local_time = datetime.now()
        
        cursor.execute('INSERT INTO expenses (item, cost, quantity, date_added) VALUES (?, ?, ?, ?)', (item, cost, quantity, local_time))
        conn.commit()
        conn.close()
        return jsonify({"message": "Expense added"})
    
    else:
        cursor.execute('SELECT id, item, cost, quantity, date_added FROM expenses ORDER BY date_added DESC')
        rows = cursor.fetchall()
        expenses = [{"id": r[0], "item": r[1], "cost": r[2], "quantity": r[3], "date": r[4]} for r in rows]
        conn.close()
        return jsonify(expenses)

@app.route('/api/balance', methods=['GET'])
def get_balance():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    current_month = datetime.now().strftime('%Y-%m')
    
    # Get budget
    cursor.execute('SELECT amount FROM budget WHERE month_str = ?', (current_month,))
    budget_row = cursor.fetchone()
    budget = budget_row[0] if budget_row else 0
    
    # Get total expenses
    # Ideally filter by month, but for simplicity let's sum all for now or filter by month in SQL
    # Let's filter by month to be correct "monthly expenditures"
    cursor.execute("SELECT SUM(cost) FROM expenses WHERE strftime('%Y-%m', date_added) = ?", (current_month,))
    expense_row = cursor.fetchone()
    total_expenses = expense_row[0] if expense_row and expense_row[0] else 0
    
    conn.close()
    
    return jsonify({
        "budget": budget,
        "total_expenses": total_expenses,
        "remaining": budget - total_expenses
    })

@app.route('/api/reset', methods=['DELETE'])
def reset_data():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM budget')
    cursor.execute('DELETE FROM expenses')
    conn.commit()
    conn.close()
    return jsonify({"message": "Data reset successfully"})

if __name__ == '__main__':
    init_db()
    # Host 0.0.0.0 makes it accessible on the network
    app.run(debug=True, host='0.0.0.0', port=5000)
