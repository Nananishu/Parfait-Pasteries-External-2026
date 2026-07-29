import json
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = 'parfait_pastries_secret'

def initialise_database():

    with sqlite3.connect('bakery.db') as conn:
        cursor = conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            invoice_number TEXT,
            customer_name TEXT,
            items TEXT,
            addons TEXT,
            total REAL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        conn.commit()

        def load_data():
    with open('data/pasteries.json') as file:
        pastries = json.load(file)
    with open('data/addons.json') as file:
        addons = json.load(file)
    return pastries, addons

def calculate_total(cart, selected_addons=None):
    total = sum(item['price'] * item['quantity'] for item in cart.values())
    if selected_addons:
        total += sum(selected_addons.values())

        # 50% discount logic
    discount_applied = False
    if total > 0: # Applied to all instore/click & collect as per mockup
        total = total * 0.5
        discount_applied = True

    return total, discount_applied

@app.route('/')
def index():
    cart = session.get('cart', {})
    selected_addons = session.get('selected_addons', {})
    pastries, addons = load_data()
    total, discount_applied = calculate_total(cart, selected_addons)
    return render_template('index.html', pastries=pastries, addons=addons,
                           cart=cart, total=total, selected_addons=selected_addons, discount_applied=discount_applied)

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    pastry = request.form['pastry']
    pastries, addons = load_data()
    cart = session.get('cart', {})
    
    if pastry in cart:
        cart[pastry]['quantity'] += 1
    else:
        cart[pastry] = {'price': pastries[pastry]['price'], 'quantity': 1}