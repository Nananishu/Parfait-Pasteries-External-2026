import sqlite3
from contextlib import closing

import app as bakery_app
from app import app, initialise_database


def test_add_to_cart_shows_flash_message():
    client = app.test_client()

    response = client.post(
        '/add_to_cart',
        data={'pastry': 'Custard Pudding parfait'},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b'Added Custard Pudding parfait to your cart!' in response.data


def test_checkout_creates_order_record(tmp_path, monkeypatch):
    db_path = tmp_path / 'bakery.db'
    invoices_dir = tmp_path / 'invoices'
    monkeypatch.setattr(bakery_app, 'DB_PATH', db_path)
    monkeypatch.setattr(bakery_app, 'LEGACY_DB_PATH', tmp_path / 'legacy.db')
    monkeypatch.setattr(bakery_app, 'INVOICES_DIR', invoices_dir)
    initialise_database()

    client = app.test_client()

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
    assert response.headers['Location'].endswith('/addons')

    with closing(sqlite3.connect(db_path)) as conn, conn:
        row = conn.execute(
            'SELECT invoice_number, customer_name, customer_email, items, total FROM orders WHERE customer_name = ?',
            ('Aisha',),
        ).fetchone()

    assert row is not None
    assert row[0].startswith('INV_Aisha_')
    assert row[1] == 'Aisha'
    assert row[2] == 'aisha@example.com'
    assert 'Custard Pudding parfait' in row[3]
    assert float(row[4]) > 0
    assert (invoices_dir / f'{row[0]}.txt').is_file()


def test_initialise_database_migrates_legacy_orders_once(tmp_path, monkeypatch):
    db_path = tmp_path / 'bakery.db'
    legacy_db_path = tmp_path / 'data' / 'bakery.db'
    legacy_db_path.parent.mkdir()
    with closing(sqlite3.connect(legacy_db_path)) as conn, conn:
        conn.execute(
            '''
            CREATE TABLE orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_number TEXT,
                customer_name TEXT,
                items TEXT,
                addons TEXT,
                total REAL,
                date TIMESTAMP
            )
            '''
        )
        conn.execute(
            '''
            INSERT INTO orders (invoice_number, customer_name, items, addons, total, date)
            VALUES (?, ?, ?, ?, ?, ?)
            ''',
            (
                'PP-20260831120626-3DE6FB',
                'Nisheeta',
                '{"Rose Bouquet": {"price": 34.0, "quantity": 1}}',
                None,
                23.8,
                '2026-08-31 00:06:26',
            ),
        )

    monkeypatch.setattr(bakery_app, 'DB_PATH', db_path)
    monkeypatch.setattr(bakery_app, 'LEGACY_DB_PATH', legacy_db_path)
    monkeypatch.setattr(bakery_app, 'INVOICES_DIR', tmp_path / 'invoices')

    initialise_database()
    initialise_database()

    with closing(sqlite3.connect(db_path)) as conn, conn:
        rows = conn.execute(
            'SELECT invoice_number, customer_name, date FROM orders'
        ).fetchall()

    assert rows == [
        ('PP-20260831120626-3DE6FB', 'Nisheeta', '2026-08-31 00:06:26')
    ]
