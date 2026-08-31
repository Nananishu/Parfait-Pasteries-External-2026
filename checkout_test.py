import sqlite3
from app import app, DB_PATH, initialise_database

initialise_database()
conn = sqlite3.connect(DB_PATH)
conn.execute('DELETE FROM orders')
conn.commit()

with app.test_client() as client:
    with client.session_transaction() as session:
        session['cart'] = {
            'Custard Pudding parfait': {'price': 9.5, 'quantity': 1},
            'Rose Bouquet': {'price': 34.0, 'quantity': 1},
        }

    response = client.post(
        '/checkout',
        data={
            'customer_name': 'Aisha',
            'customer_email': 'aisha@example.com',
            'customer_phone': '0211234567',
            'delivery_address': '12 Main Road',
        },
        follow_redirects=False,
    )

    print('STATUS', response.status_code)
    print('LOCATION', response.headers.get('Location'))
    row = conn.execute(
        'SELECT customer_name, items, total FROM orders WHERE customer_name = ?',
        ('Aisha',),
    ).fetchone()
    print('ROW', row)
