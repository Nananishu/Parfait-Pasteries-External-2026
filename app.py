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