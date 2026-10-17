import sqlite3
import tempfile
from pathlib import Path

import app as bakery_app
from app import app


with tempfile.TemporaryDirectory() as temp_dir:
    test_dir = Path(temp_dir)
    bakery_app.DB_PATH = test_dir / 'bakery.db'
    bakery_app.LEGACY_DB_PATH = test_dir / 'legacy.db'
    bakery_app.INVOICES_DIR = test_dir / 'invoices'
    bakery_app.initialise_database()

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
    with sqlite3.connect(bakery_app.DB_PATH) as conn:
        row = conn.execute(
            'SELECT customer_name, items, total FROM orders WHERE customer_name = ?',
            ('Aisha',),
        ).fetchone()
    print('ROW', row)
