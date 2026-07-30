import json
import sqlite3
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, session, url_for

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'bakery.db'
DATA_DIR = BASE_DIR / 'data'

# This starts the Flask app and gives it a secret key so the cart can be remembered in the session.
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = 'parfait_pastries_secret'


# This function creates the orders table if it does not already exist, so the app can save order data.
def initialise_database():
    with sqlite3.connect(DB_PATH) as conn:
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


# This loads the pastry and addon information from JSON files, which keeps the data easy to update.
def load_data():
    with open(DATA_DIR / 'pastries.json', encoding='utf-8') as file:
        pastries = json.load(file)
    with open(DATA_DIR / 'addons.json', encoding='utf-8') as file:
        addons = json.load(file)
    return pastries, addons


def get_view_context(selected_addons=None):
    cart = session.get('cart', {})
    selected_addons = session.get('selected_addons', {}) if selected_addons is None else selected_addons
    pastries, addons = load_data()
    total, discount_applied = calculate_total(cart, selected_addons)
    return {
        'pastries': pastries,
        'addons': addons,
        'cart': cart,
        'total': total,
        'selected_addons': selected_addons,
        'discount_applied': discount_applied,
    }


# This works out the total price and applies the 50% discount to make the checkout look like the mockup.
def calculate_total(cart, selected_addons=None):
    total = sum(item['price'] * item['quantity'] for item in cart.values())
    if selected_addons:
        total += sum(selected_addons.values())

    # Discount applied to all items as per the mockup
    discount_applied = total > 0
    if discount_applied:
        total *= 0.5

    return total, discount_applied


# This route loads the homepage and sends the bakery data to the homepage template.
@app.route('/')
def index():
    context = get_view_context()
    return render_template('index.html', **context)


# This route loads the addons page, where the customer can see extra items and the order summary.
@app.route('/addons')
def addons_page():
    context = get_view_context()
    return render_template('addons.html', **context)


# This route loads the best sellers page and passes the same cart information through to the template.
@app.route('/best-sellers')
def best_sellers_page():
    context = get_view_context(selected_addons={})
    return render_template('best_sellers.html', **context)


# This route receives the selected pastry from the form and adds it into the cart session.
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


# This route removes an item from the cart when the user clicks the delete button.
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