import sqlite3

from app import app, DB_PATH


def test_checkout_creates_order_record():
    client = app.test_client()

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute('DELETE FROM orders')
        conn.commit()

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

    assert response.status_code == 302
    assert response.headers['Location'].startswith('/invoice/')

    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            'SELECT customer_name, customer_email, items, total FROM orders WHERE customer_name = ?',
            ('Aisha',),
        ).fetchone()

    assert row is not None
    assert row[0] == 'Aisha'
    assert row[1] == 'aisha@example.com'
    assert 'Custard Pudding parfait' in row[2]
    assert float(row[3]) > 0
