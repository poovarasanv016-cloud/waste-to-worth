import sqlite3
import os
import hashlib

DB_PATH = os.path.join(os.path.dirname(__file__), 'food_waste.db')

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db = get_db()
    db.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'Donor',
            phone TEXT,
            address TEXT,
            created_at TEXT
        );

        CREATE TABLE IF NOT EXISTS food_donations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donor_id INTEGER NOT NULL,
            food_name TEXT NOT NULL,
            quantity TEXT NOT NULL,
            food_type TEXT NOT NULL,
            available_date TEXT,
            expiry_time TEXT,
            pickup_location TEXT,
            contact_details TEXT,
            food_image TEXT,
            status TEXT DEFAULT 'Available',
            created_at TEXT,
            FOREIGN KEY(donor_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS food_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            donation_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            status TEXT DEFAULT 'Pending',
            requested_at TEXT,
            FOREIGN KEY(donation_id) REFERENCES food_donations(id),
            FOREIGN KEY(receiver_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS feedbacks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            created_at TEXT,
            FOREIGN KEY(request_id) REFERENCES food_requests(id),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    ''')

    # Add profile fields to existing databases without losing current user data.
    existing_columns = {row['name'] for row in db.execute('PRAGMA table_info(users)').fetchall()}
    for column, definition in (
        ('date_of_birth', 'TEXT'),
        ('gender', 'TEXT'),
        ('profile_photo', 'TEXT'),
    ):
        if column not in existing_columns:
            db.execute(f'ALTER TABLE users ADD COLUMN {column} {definition}')

    # Add food photo field to existing donation databases.
    food_columns = {row['name'] for row in db.execute('PRAGMA table_info(food_donations)').fetchall()}
    if 'food_image' not in food_columns:
        db.execute("ALTER TABLE food_donations ADD COLUMN food_image TEXT")

    # Seed admin
    admin_pw = hashlib.sha256('admin123'.encode()).hexdigest()
    existing = db.execute("SELECT id FROM users WHERE email='admin@foodwaste.com'").fetchone()
    if not existing:
        db.execute('''
            INSERT INTO users (name, email, password, role, phone, address, created_at)
            VALUES ('Admin', 'admin@foodwaste.com', ?, 'Admin', '9999999999', 'Chennai', datetime('now'))
        ''', (admin_pw,))

    # Seed sample donors
    donors = [
        ('Ravi Kumar', 'ravi@example.com', 'Donor', '9876543210', 'Anna Nagar, Chennai'),
        ('Priya Sharma', 'priya@example.com', 'Donor', '9876543211', 'T Nagar, Chennai'),
        ('NGO HelpHands', 'ngo@helphand.com', 'NGO', '9876543212', 'Adyar, Chennai'),
    ]
    for n, e, r, p, a in donors:
        if not db.execute("SELECT id FROM users WHERE email=?", (e,)).fetchone():
            db.execute('''
                INSERT INTO users (name, email, password, role, phone, address, created_at)
                VALUES (?,?,?,?,?,?,datetime('now'))
            ''', (n, e, hashlib.sha256('password123'.encode()).hexdigest(), r, p, a))

    db.commit()

    # Seed sample donations
    sample_foods = db.execute("SELECT COUNT(*) FROM food_donations").fetchone()[0]
    if sample_foods == 0:
        donor1 = db.execute("SELECT id FROM users WHERE email='ravi@example.com'").fetchone()
        donor2 = db.execute("SELECT id FROM users WHERE email='priya@example.com'").fetchone()
        if donor1 and donor2:
            foods = [
                (donor1['id'], 'Rice & Curry', '20 plates', 'Cooked Food', '2024-12-20', '2024-12-20 20:00', 'Anna Nagar, Chennai', '9876543210', 'Available'),
                (donor1['id'], 'Chapati', '30 pieces', 'Cooked Food', '2024-12-21', '2024-12-21 18:00', 'Anna Nagar, Chennai', '9876543210', 'Available'),
                (donor2['id'], 'Vegetable Rice', '10 kg', 'Cooked Food', '2024-12-22', '2024-12-22 15:00', 'T Nagar, Chennai', '9876543211', 'Available'),
                (donor2['id'], 'Fresh Fruits', '5 kg', 'Fruits & Vegetables', '2024-12-23', '2024-12-25 00:00', 'T Nagar, Chennai', '9876543211', 'Available'),
                (donor1['id'], 'Bread Loaves', '10 loaves', 'Bakery', '2024-12-20', '2024-12-21 12:00', 'Anna Nagar, Chennai', '9876543210', 'Available'),
            ]
            for f in foods:
                db.execute('''
                    INSERT INTO food_donations
                    (donor_id, food_name, quantity, food_type, available_date, expiry_time,
                     pickup_location, contact_details, status, created_at)
                    VALUES (?,?,?,?,?,?,?,?,?,datetime('now'))
                ''', f)
            db.commit()
    db.close()
