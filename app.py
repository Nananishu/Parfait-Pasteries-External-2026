import json
import sqlite3
from flask import Flask, flash, redirect, render_template, request, session, url_for

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = 'parfait_pastries_secret'


def initialise_database():
    with sqlite3.connect('bakery.db') as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT,
                customer_name TEXT,
                items TEXT,
                addons TEXT,
                total REAL,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )
        conn.commit()


def load_data():
    with open('data/pasteries.json', encoding='utf-8') as file:
        pastries = json.load(file)
    with open('data/addons.json', encoding='utf-8') as file:
        addons = json.load(file)
    return pastries, addons


def calculate_total(cart, selected_addons=None):
    total = sum(item['price'] * item['quantity'] for item in cart.values())
    if selected_addons:
        total += sum(selected_addons.values())

    # Discount applied to all items as per the mockup
    discount_applied = total > 0
    if discount_applied:
        total *= 0.5

    return total, discount_applied


@app.route('/')
def index():
    cart = session.get('cart', {})
    selected_addons = session.get('selected_addons', {})
    pastries, addons = load_data()
    total, discount_applied = calculate_total(cart, selected_addons)
    return render_template(
        'index.html',
        pastries=pastries,
        addons=addons,
        cart=cart,
        total=total,
        selected_addons=selected_addons,
        discount_applied=discount_applied,
    )


@app.route('/addons')
def addons_page():
    cart = session.get('cart', {})
    selected_addons = session.get('selected_addons', {})
    pastries, addons = load_data()
    total, discount_applied = calculate_total(cart, selected_addons)
    return render_template(
        'addons.html',
        pastries=pastries,
        addons=addons,
        cart=cart,
        total=total,
        selected_addons=selected_addons,
        discount_applied=discount_applied,
    )


@app.route('/best-sellers')
def best_sellers_page():
    cart = session.get('cart', {})
    pastries, addons = load_data()
    total, discount_applied = calculate_total(cart, {})
    return render_template(
        'best_sellers.html',
        pastries=pastries,
        addons=addons,
        cart=cart,
        total=total,
        discount_applied=discount_applied,
    )


@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    pastry = request.form['pastry']
    pastries, _ = load_data()
    cart = session.get('cart', {})

    if pastry in cart:
        cart[pastry]['quantity'] += 1
    else:
        cart[pastry] = {'price': pastries[pastry]['price'], 'quantity': 1}

    session['cart'] = cart
    session.modified = True
    flash(f'Added {pastry} to your cart! 🍰')
    return redirect(url_for('addons_page'))


@app.route('/remove_from_cart/<item>')
def remove_from_cart(item):
    cart = session.get('cart', {})
    if item in cart:
        del cart[item]
        session['cart'] = cart
        session.modified = True
    return redirect(url_for('addons_page'))


if __name__ == '__main__':
    initialise_database()
    app.run(debug=True)