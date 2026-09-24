import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, session, url_for

# This file sets up the bakery website and connects it to the database.
# It stores orders, loads menu items, and handles the shopping cart.

# These paths tell the app where its data files and database are saved.
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / 'data'
DB_PATH = DATA_DIR / 'bakery.db'
INVOICES_DIR = DATA_DIR / 'invoices'

# This creates the Flask app and gives it a secret key for saving cart data.
app = Flask(__name__, static_folder='static', static_url_path='/static')
app.secret_key = 'parfait_pastries_secret'


# This function makes sure the database and invoice folder exist before the app uses them.
def initialise_database():
    INVOICES_DIR.mkdir(parents=True, exist_ok=True)
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

        # If older databases were created without some columns, this adds them in.
        existing_columns = [
            row[1] for row in cursor.execute('PRAGMA table_info(orders)').fetchall()
        ]

        for column_name in ['customer_email', 'customer_phone', 'delivery_address', 'addons']:
            if column_name not in existing_columns:
                cursor.execute(
                    f'ALTER TABLE orders ADD COLUMN {column_name} TEXT'
                )

        conn.commit()


# Run the database setup when the app starts.
initialise_database()


# This loads the bakery menu and add-on list from JSON files.
def load_data():
    with (DATA_DIR / 'pasteries.json').open(encoding='utf-8') as file:
        pastries = json.load(file)
    with (DATA_DIR / 'addons.json').open(encoding='utf-8') as file:
        addons = json.load(file)
    return pastries, addons


# This adds up the cart price and applies the 30% discount if something was ordered.
def calculate_total(cart, selected_addons=None):
    total = sum(item['price'] * item['quantity'] for item in cart.values())
    if selected_addons:
        total += sum(selected_addons.values())

    discount_applied = total > 0
    if discount_applied:
        total *= 0.7

    return round(total, 2), discount_applied


# This is the home page. It loads the products and shows the cart total at the top.
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


# This page shows the add-ons section and keeps the same cart and total logic.
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


# This page displays the shop's best sellers.
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


# This page lets customers leave feedback and store their rating and comments.
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


# This route adds a pastry or add-on to the shopping cart.
@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    pastry = request.form['pastry']
    pastries, addons = load_data()
    cart = session.get('cart', {})

    # It checks whether the selected item exists in the product list.
    item_data = pastries.get(pastry) or addons.get(pastry)
    if item_data is None:
        flash(f'Item "{pastry}" was not found.')
        return redirect(url_for('addons_page'))

    # If the item is already in the cart, increase the quantity. Otherwise, add it fresh.
    if pastry in cart:
        cart[pastry]['quantity'] += 1
    else:
        cart[pastry] = {'price': item_data['price'], 'quantity': 1}

    session['cart'] = cart
    session.modified = True
    flash(f'Added {pastry} to your cart! 🍰')
    return redirect(url_for('addons_page'))


# This removes one item from the cart completely.
@app.route('/remove_from_cart/<item>')
def remove_from_cart(item):
    cart = session.get('cart', {})
    if item in cart:
        del cart[item]
        session['cart'] = cart
        session.modified = True
    return redirect(url_for('addons_page'))


# This finalizes the order, saves it to the database, and creates a text invoice.
@app.route('/checkout', methods=['POST'])
def checkout():
    cart = session.get('cart', {})
    if not cart:
        flash('Your cart is empty.')
        return redirect(url_for('addons_page'))

    # These lines collect the customer details from the checkout form.
    customer_name = request.form.get('customer_name', '').strip() or 'Walk-in Customer'
    customer_email = request.form.get('customer_email', '').strip()
    customer_phone = request.form.get('customer_phone', '').strip()
    delivery_address = request.form.get('delivery_address', '').strip()
    pastries, addon_catalogue = load_data()

    # Split items into pastries and add-ons so the invoice looks clean.
    items = {name: details for name, details in cart.items() if name in pastries}
    addons = {name: details for name, details in cart.items() if name in addon_catalogue}
    subtotal = sum(item['price'] * item['quantity'] for item in cart.values())
    total, _ = calculate_total(cart, {})
    timestamp = datetime.now()

    # This makes a simple invoice name using the customer's name.
    customer_slug = ''.join(
        character for character in customer_name if character.isalnum() or character == '_'
    ) or 'Customer'
    invoice_number = (
        f'INV_{customer_slug}_{timestamp.strftime("%Y-%m-%d_%H%M%S")}_'
        f'{uuid.uuid4().hex[:6].upper()}'
    )

    # Save the order into SQLite so it can be seen later in order history.
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            '''
            INSERT INTO orders (
                invoice_number, customer_name, customer_email, customer_phone,
                delivery_address, items, addons, total
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                invoice_number,
                customer_name,
                customer_email,
                customer_phone,
                delivery_address,
                json.dumps(items),
                json.dumps(addons),
                total,
            ),
        )
        conn.commit()

    # Build the text invoice that customers can read or save.
    invoice_lines = [
        f'Date: {timestamp.strftime("%Y-%m-%d %H:%M:%S")}',
        f'Invoice Number: {invoice_number}',
        f'Customer: {customer_name}',
        '',
        'Parfait Pasteries',
        '-' * 50,
        '',
        'Items:',
    ]
    for name, item in items.items():
        line_total = item['price'] * item['quantity']
        invoice_lines.append(
            f'  {name}: {item["quantity"]} x ${item["price"]:.2f} = ${line_total:.2f}'
        )

    invoice_lines.extend(['', 'Add-ons:'])
    if addons:
        for name, item in addons.items():
            line_total = item['price'] * item['quantity']
            invoice_lines.append(
                f'  {name}: {item["quantity"]} x ${item["price"]:.2f} = ${line_total:.2f}'
            )
    else:
        invoice_lines.append('  None')

    invoice_lines.extend([
        '',
        f'Subtotal: ${subtotal:.2f}',
        f'Total: ${total:.2f}',
        '',
    ])
    invoice_path = INVOICES_DIR / f'{invoice_number}.txt'
    invoice_path.write_text('\n'.join(invoice_lines), encoding='utf-8')

    # Clear the cart after a successful purchase.
    session.pop('cart', None)
    session.modified = True
    flash(f'Purchase saved. Invoice {invoice_number} was saved to data/invoices.')
    return redirect(url_for('addons_page'))


# This shows all saved orders from the database in date order.
@app.route('/order_history')
def order_history_page():
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        orders = conn.execute(
            'SELECT * FROM orders ORDER BY date DESC'
        ).fetchall()
    return render_template('order_history.html', orders=orders)


# This starts the app when the file is run directly.
if __name__ == '__main__':
    initialise_database()
    app.run(debug=True)