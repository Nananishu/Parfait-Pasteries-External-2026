import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, flash, redirect, render_template, request, session, url_for

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'
DB_PATH = BASE_DIR / 'bakery.db'

app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = 'parfait_pastries_secret'


def initialise_database():
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            '''
            CREATE TABLE IF NOT EXISTS orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT UNIQUE,
                customer_name TEXT,
                customer_email TEXT,
                customer_phone TEXT,
                delivery_address TEXT,
                items TEXT,
                addons TEXT,
                total REAL,
                date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            '''
        )

        existing_columns = [
            row[1] for row in cursor.execute('PRAGMA table_info(orders)').fetchall()
        ]

        for column_name in ['customer_email', 'customer_phone', 'delivery_address', 'addons']:
            if column_name not in existing_columns:
                cursor.execute(
                    f'ALTER TABLE orders ADD COLUMN {column_name} TEXT'
                )

        conn.commit()


def load_data():
    with (DATA_DIR / 'pasteries.json').open(encoding='utf-8') as file:
        pastries = json.load(file)
    with (DATA_DIR / 'addons.json').open(encoding='utf-8') as file:
        addons = json.load(file)
    return pastries, addons


def calculate_total(cart, selected_addons=None):
    total = sum(item['price'] * item['quantity'] for item in cart.values())
    if selected_addons:
        total += sum(selected_addons.values())

    discount_applied = total > 0
    if discount_applied:
        total *= 0.7

    return round(total, 2), discount_applied


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


@app.route('/feedback', methods=['GET', 'POST'])
def feedback_page():
    cart = session.get('cart', {})
    pastries, addons = load_data()
    total, discount_applied = calculate_total(cart, {})

    locations = ['Ormiston', 'Manukau', 'Botany', 'Papatoetoe', 'Manurewa']
    selected_location = 'Ormiston'
    rating = 5
    comments = ''
    feedback_submitted = False
    feedback_location = ''

    if request.method == 'POST':
        selected_location = request.form.get('location', selected_location)
        rating = request.form.get('rating', rating)
        comments = request.form.get('comments', '').strip()
        feedback_submitted = True
        feedback_location = selected_location

    return render_template(
        'feedback.html',
        pastries=pastries,
        addons=addons,
        cart=cart,
        total=total,
        discount_applied=discount_applied,
        locations=locations,
        selected_location=selected_location,
        rating=rating,
        comments=comments,
        feedback_submitted=feedback_submitted,
        feedback_location=feedback_location,
    )


@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    pastry = request.form['pastry']
    pastries, addons = load_data()
    cart = session.get('cart', {})

    item_data = pastries.get(pastry) or addons.get(pastry)
    if item_data is None:
        flash(f'Item "{pastry}" was not found.')
        return redirect(url_for('addons_page'))

    if pastry in cart:
        cart[pastry]['quantity'] += 1
    else:
        cart[pastry] = {'price': item_data['price'], 'quantity': 1}

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


@app.route('/checkout', methods=['POST'])
def checkout():
    cart = session.get('cart', {})
    if not cart:
        flash('Your cart is empty.')
        return redirect(url_for('addons_page'))

    customer_name = request.form.get('customer_name', '').strip() or 'Walk-in Customer'
    customer_email = request.form.get('customer_email', '').strip()
    customer_phone = request.form.get('customer_phone', '').strip()
    delivery_address = request.form.get('delivery_address', '').strip()
    total, _ = calculate_total(cart, {})
    invoice_number = f'PP-{datetime.now().strftime("%Y%m%d%H%M%S")}-{uuid.uuid4().hex[:6].upper()}'

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            '''
            INSERT INTO orders (
                invoice_number, customer_name, customer_email, customer_phone,
                delivery_address, items, total
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                invoice_number,
                customer_name,
                customer_email,
                customer_phone,
                delivery_address,
                json.dumps(cart),
                total,
            ),
        )
        conn.commit()

    session.pop('cart', None)
    session.modified = True
    return redirect(url_for('invoice_page', invoice_number=invoice_number))


@app.route('/invoice/<invoice_number>')
def invoice_page(invoice_number):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        order = conn.execute(
            'SELECT * FROM orders WHERE invoice_number = ?',
            (invoice_number,),
        ).fetchone()

    if order is None:
        abort(404)

    order = dict(order)
    order['items'] = json.loads(order['items']) if order['items'] else {}
    return render_template('invoice.html', order=order)


@app.route('/order_history')
def order_history_page():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        orders = conn.execute(
            'SELECT * FROM orders ORDER BY date DESC'
        ).fetchall()
    return render_template('order_history.html', orders=orders)


if __name__ == '__main__':
    initialise_database()
    app.run(debug=True)