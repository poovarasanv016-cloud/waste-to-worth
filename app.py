from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from database import init_db, get_db
import hashlib
import os
import re
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'food_waste_secret_key_2024'

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_current_user():
    if 'user_id' in session:
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE id = ?', (session['user_id'],)).fetchone()
        db.close()
        return user
    return None

@app.context_processor
def inject_user():
    return dict(current_user=get_current_user())

# ─── AUTH ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    db = get_db()
    stats = {
        'total_users': db.execute('SELECT COUNT(*) FROM users').fetchone()[0],
        'total_available': db.execute("SELECT COUNT(*) FROM food_donations WHERE status='Available'").fetchone()[0],
        'total_distributed': db.execute("SELECT COUNT(*) FROM food_requests WHERE status='Completed'").fetchone()[0],
        'pending_requests': db.execute("SELECT COUNT(*) FROM food_requests WHERE status='Pending'").fetchone()[0],
    }
    recent_foods = db.execute('''
        SELECT fd.*, u.name as donor_name
        FROM food_donations fd
        JOIN users u ON fd.donor_id = u.id
        WHERE fd.status = "Available"
        ORDER BY fd.created_at DESC LIMIT 5
    ''').fetchall()
    db.close()
    return render_template('index.html', stats=stats, recent_foods=recent_foods)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']
        role = request.form['role']
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()

        db = get_db()
        # Server-side validation as a second layer, so invalid/incomplete data
        # is rejected even when browser validation is bypassed.
        errors = {}
        if len(name) < 2:
            errors['name'] = True
        if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            errors['email'] = True
        if not re.match(r'^[0-9+\-\s()]{10,15}$', phone):
            errors['phone'] = True
        if len(password) < 8:
            errors['password'] = True
        if password != request.form.get('confirm_password', ''):
            errors['confirm_password'] = True
        if role not in ('Donor', 'NGO'):
            errors['role'] = True

        db = get_db()
        existing = db.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
        if existing:
            errors['email'] = True
            flash('Email already registered.', 'danger')

        if errors:
            db.close()
            return render_template('register.html', errors=errors)

        cursor = db.execute(
            'INSERT INTO users (name, email, password, role, phone, address, created_at) VALUES (?,?,?,?,?,?,?)',
            (name, email, hash_password(password), role, phone, address, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )
        new_user_id = cursor.lastrowid
        db.commit()
        db.close()

        # Automatically sign in newly registered users.
        session.clear()
        session['user_id'] = new_user_id
        session['role'] = role
        flash(f'Registration successful! Welcome, {name}!', 'success')
        return redirect(url_for('dashboard'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        db = get_db()
        user = db.execute('SELECT * FROM users WHERE email=? AND password=?',
                          (email, hash_password(password))).fetchone()
        db.close()
        if user:
            session['user_id'] = user['id']
            session['role'] = user['role']
            flash(f'Welcome back, {user["name"]}!', 'success')
            if user['role'] == 'Admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        flash('Invalid email or password.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully.', 'info')
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()
        date_of_birth = request.form.get('date_of_birth', '').strip() or None
        gender = request.form.get('gender', '').strip() or None
        if gender not in (None, 'Male', 'Female', 'Other', 'Prefer not to say'):
            gender = None

        photo = request.files.get('profile_photo')
        photo_name = None
        if photo and photo.filename:
            allowed_extensions = {'png', 'jpg', 'jpeg', 'webp'}
            safe_name = secure_filename(photo.filename)
            if '.' not in safe_name or safe_name.rsplit('.', 1)[1].lower() not in allowed_extensions:
                flash('Please upload a JPG, PNG, or WEBP image.', 'danger')
                user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
                db.close()
                return render_template('profile.html', user=user, now_date=datetime.now().strftime('%Y-%m-%d'))
            upload_dir = os.path.join(app.root_path, 'static', 'uploads', 'profile_photos')
            os.makedirs(upload_dir, exist_ok=True)
            extension = safe_name.rsplit('.', 1)[1].lower()
            photo_name = f"user_{session['user_id']}.{extension}"
            photo.save(os.path.join(upload_dir, photo_name))

        if photo_name:
            db.execute('UPDATE users SET name=?, phone=?, address=?, date_of_birth=?, gender=?, profile_photo=? WHERE id=?',
                       (name, phone, address, date_of_birth, gender, photo_name, session['user_id']))
        else:
            db.execute('UPDATE users SET name=?, phone=?, address=?, date_of_birth=?, gender=? WHERE id=?',
                       (name, phone, address, date_of_birth, gender, session['user_id']))
        db.commit()
        flash('Profile updated successfully.', 'success')
    user = db.execute('SELECT * FROM users WHERE id=?', (session['user_id'],)).fetchone()
    db.close()
    return render_template('profile.html', user=user, now_date=datetime.now().strftime('%Y-%m-%d'))


@app.route('/delete_account', methods=['POST'])
def delete_account():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    uid = session['user_id']
    db = get_db()
    user = db.execute('SELECT id, role, profile_photo FROM users WHERE id=?', (uid,)).fetchone()
    if not user:
        db.close()
        session.clear()
        return redirect(url_for('index'))

    # Keep the application accessible if this is the only admin account.
    if user['role'] == 'Admin':
        other_admins = db.execute("SELECT COUNT(*) FROM users WHERE role='Admin' AND id<>?", (uid,)).fetchone()[0]
        if other_admins == 0:
            db.close()
            flash('The only admin account cannot be deleted. Create another admin account first.', 'danger')
            return redirect(url_for('profile'))

    related_requests = [row['id'] for row in db.execute(
        'SELECT id FROM food_requests WHERE receiver_id=? OR donation_id IN (SELECT id FROM food_donations WHERE donor_id=?)',
        (uid, uid)).fetchall()]
    if related_requests:
        placeholders = ','.join('?' for _ in related_requests)
        db.execute(f'DELETE FROM feedbacks WHERE request_id IN ({placeholders}) OR user_id=?', (*related_requests, uid))
    else:
        db.execute('DELETE FROM feedbacks WHERE user_id=?', (uid,))
    db.execute('DELETE FROM food_requests WHERE receiver_id=? OR donation_id IN (SELECT id FROM food_donations WHERE donor_id=?)', (uid, uid))
    db.execute('DELETE FROM food_donations WHERE donor_id=?', (uid,))
    db.execute('DELETE FROM notifications WHERE user_id=?', (uid,))
    db.execute('DELETE FROM users WHERE id=?', (uid,))
    db.commit()
    db.close()

    if user['profile_photo']:
        photo_path = os.path.join(app.root_path, 'static', 'uploads', 'profile_photos', user['profile_photo'])
        try:
            if os.path.isfile(photo_path):
                os.remove(photo_path)
        except OSError:
            pass
    session.clear()
    flash('Your account has been deleted.', 'success')
    return redirect(url_for('index'))

# ─── DASHBOARD ───────────────────────────────────────────────────────────────

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    uid = session['user_id']
    role = session['role']

    my_donations = db.execute('''
        SELECT * FROM food_donations WHERE donor_id=? ORDER BY created_at DESC
    ''', (uid,)).fetchall()

    my_requests = db.execute('''
        SELECT fr.*, fd.food_name, fd.quantity, fd.pickup_location
        FROM food_requests fr
        JOIN food_donations fd ON fr.donation_id = fd.id
        WHERE fr.receiver_id=? ORDER BY fr.requested_at DESC
    ''', (uid,)).fetchall()

    # Requests for food donated by the signed-in user: donors manage these.
    donor_requests = db.execute('''
        SELECT fr.*, fd.food_name, fd.quantity, fd.pickup_location,
               u.name AS receiver_name, u.phone AS receiver_phone, u.email AS receiver_email
        FROM food_requests fr
        JOIN food_donations fd ON fr.donation_id = fd.id
        JOIN users u ON fr.receiver_id = u.id
        WHERE fd.donor_id=? ORDER BY fr.requested_at DESC
    ''', (uid,)).fetchall()

    notifications = db.execute('''
        SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 10
    ''', (uid,)).fetchall()
    db.execute('UPDATE notifications SET is_read=1 WHERE user_id=?', (uid,))
    db.commit()
    db.close()
    return render_template('dashboard.html', my_donations=my_donations,
                           my_requests=my_requests, donor_requests=donor_requests, notifications=notifications)

# ─── FOOD DONATIONS ──────────────────────────────────────────────────────────

@app.route('/donate', methods=['GET', 'POST'])
def donate():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        db = get_db()
        photo = request.files.get('food_image')
        photo_name = None
        if photo and photo.filename:
            allowed = {'png', 'jpg', 'jpeg', 'webp', 'gif'}
            ext = photo.filename.rsplit('.', 1)[-1].lower() if '.' in photo.filename else ''
            if ext not in allowed:
                flash('Please upload a JPG, PNG, WEBP, or GIF image.', 'danger')
                db.close()
                return render_template('donate.html')
            upload_dir = os.path.join(app.root_path, 'static', 'uploads', 'food_photos')
            os.makedirs(upload_dir, exist_ok=True)
            photo_name = f"food_{session['user_id']}_{int(datetime.now().timestamp())}.{ext}"
            photo.save(os.path.join(upload_dir, photo_name))

        db.execute('''
            INSERT INTO food_donations
            (donor_id, food_name, quantity, food_type, available_date, expiry_time,
             pickup_location, contact_details, food_image, status, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
        ''', (
            session['user_id'],
            request.form['food_name'],
            request.form['quantity'],
            request.form['food_type'],
            request.form['available_date'],
            request.form['expiry_time'],
            request.form['pickup_location'],
            request.form['contact_details'],
            photo_name,
            'Available',
            datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        ))
        db.commit()
        db.close()
        flash('Food donation listed successfully!', 'success')
        return redirect(url_for('listings'))
    return render_template('donate.html')

@app.route('/listings')
def listings():
    db = get_db()
    search = request.args.get('search', '')
    food_type = request.args.get('food_type', '')
    status_filter = request.args.get('status', '')

    # The Available Food page should contain only donations that are currently available.
    # Once a request is completed (or the donation moves to another status), it is
    # automatically removed from this page.
    query = '''
        SELECT fd.*, u.name as donor_name
        FROM food_donations fd
        JOIN users u ON fd.donor_id = u.id
        WHERE fd.status = 'Available'
    '''
    params = []
    if search:
        query += ' AND (fd.food_name LIKE ? OR fd.pickup_location LIKE ?)'
        params += [f'%{search}%', f'%{search}%']
    if food_type:
        query += ' AND fd.food_type = ?'
        params.append(food_type)
    # Status is intentionally not used here because this page is for available food only.
    query += ' ORDER BY fd.created_at DESC'

    foods = db.execute(query, params).fetchall()
    db.close()
    return render_template('listings.html', foods=foods, search=search,
                           food_type=food_type, status_filter=status_filter)

@app.route('/food/<int:did>')
def food_details(did):
    """Show the complete information for a food donation."""
    db = get_db()
    food = db.execute('''
        SELECT fd.*, u.name AS donor_name, u.email AS donor_email,
               u.phone AS donor_phone, u.address AS donor_address
        FROM food_donations fd
        JOIN users u ON fd.donor_id = u.id
        WHERE fd.id=?
    ''', (did,)).fetchone()
    db.close()

    if not food:
        flash('Food donation not found.', 'danger')
        return redirect(url_for('listings'))

    return render_template('food_details.html', food=food)

@app.route('/delete_donation/<int:did>', methods=['POST'])
def delete_donation(did):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    donation = db.execute('SELECT * FROM food_donations WHERE id=?', (did,)).fetchone()
    if donation and (donation['donor_id'] == session['user_id'] or session['role'] == 'Admin'):
        db.execute('DELETE FROM food_donations WHERE id=?', (did,))
        db.commit()
        flash('Donation removed.', 'info')
    db.close()
    return redirect(url_for('listings'))

# ─── REQUESTS ────────────────────────────────────────────────────────────────

@app.route('/request_food/<int:did>', methods=['POST'])
def request_food(did):
    if 'user_id' not in session:
        flash('Please login to request food.', 'warning')
        return redirect(url_for('login'))
    db = get_db()
    donation = db.execute('SELECT * FROM food_donations WHERE id=?', (did,)).fetchone()
    if not donation or donation['status'] != 'Available':
        flash('Food not available.', 'danger')
        db.close()
        return redirect(url_for('listings'))

    existing = db.execute('SELECT id FROM food_requests WHERE donation_id=? AND receiver_id=?',
                          (did, session['user_id'])).fetchone()
    if existing:
        flash('You already requested this food.', 'warning')
        db.close()
        return redirect(url_for('listings'))

    db.execute('''
        INSERT INTO food_requests (donation_id, receiver_id, status, requested_at)
        VALUES (?,?,?,?)
    ''', (did, session['user_id'], 'Pending', datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    db.execute('UPDATE food_donations SET status="Requested" WHERE id=?', (did,))

    donor_id = donation['donor_id']
    receiver = db.execute('SELECT name FROM users WHERE id=?', (session['user_id'],)).fetchone()
    db.execute('''
        INSERT INTO notifications (user_id, message, created_at)
        VALUES (?,?,?)
    ''', (donor_id,
          f'{receiver["name"]} has requested your donation: {donation["food_name"]}',
          datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    db.commit()
    db.close()
    flash('Food request submitted!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/feedbacks')
def feedbacks():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    uid = session['user_id']
    requests_list = db.execute('''
        SELECT fr.id, fr.status, fr.requested_at, fd.food_name, fd.quantity,
               fd.pickup_location,
               fb.id AS feedback_id, fb.rating, fb.comment, fb.created_at AS feedback_date
        FROM food_requests fr
        JOIN food_donations fd ON fr.donation_id = fd.id
        LEFT JOIN feedbacks fb ON fb.request_id = fr.id AND fb.user_id = ?
        WHERE fr.receiver_id=? AND fr.status='Completed'
        ORDER BY fr.requested_at DESC
    ''', (uid, uid)).fetchall()
    db.close()
    return render_template('feedbacks.html', requests_list=requests_list)

@app.route('/feedback/<int:req_id>', methods=['GET', 'POST'])
def feedback(req_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    req = db.execute('''
        SELECT fr.*, fd.food_name FROM food_requests fr
        JOIN food_donations fd ON fr.donation_id = fd.id
        WHERE fr.id=? AND fr.receiver_id=? AND fr.status='Completed'
    ''', (req_id, session['user_id'])).fetchone()

    if not req:
        flash('Request not found.', 'danger')
        db.close()
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        existing = db.execute(
            'SELECT id FROM feedbacks WHERE request_id=? AND user_id=?',
            (req_id, session['user_id'])
        ).fetchone()
        if existing:
            db.close()
            flash('You have already submitted feedback for this request.', 'info')
            return redirect(url_for('feedbacks'))

        rating = request.form.get('rating', type=int)
        comment = request.form.get('comment', '').strip()
        if rating not in (1, 2, 3, 4, 5):
            db.close()
            flash('Please select a rating from 1 to 5 stars.', 'danger')
            return render_template('feedback.html', req=req)

        db.execute('''
            INSERT INTO feedbacks (request_id, user_id, rating, comment, created_at)
            VALUES (?,?,?,?,?)
        ''', (req_id, session['user_id'], rating, comment,
              datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        db.commit()
        db.close()
        flash('Thank you for your feedback!', 'success')
        return redirect(url_for('feedbacks'))
    db.close()
    return render_template('feedback.html', req=req)

# ─── ADMIN ───────────────────────────────────────────────────────────────────

@app.route('/admin')
def admin_dashboard():
    if session.get('role') != 'Admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('index'))
    db = get_db()
    stats = {
        'total_users': db.execute('SELECT COUNT(*) FROM users').fetchone()[0],
        'total_available': db.execute("SELECT COUNT(*) FROM food_donations WHERE status='Available'").fetchone()[0],
        'total_distributed': db.execute("SELECT COUNT(*) FROM food_requests WHERE status='Completed'").fetchone()[0],
        'pending_requests': db.execute("SELECT COUNT(*) FROM food_requests WHERE status='Pending'").fetchone()[0],
        'completed': db.execute("SELECT COUNT(*) FROM food_requests WHERE status='Completed'").fetchone()[0],
        'total_donors': db.execute("SELECT COUNT(*) FROM users WHERE role='Donor'").fetchone()[0],
        'total_receivers': db.execute("SELECT COUNT(*) FROM users WHERE role='NGO'").fetchone()[0],
        'total_donations': db.execute('SELECT COUNT(*) FROM food_donations').fetchone()[0],
    }
    stats.update({
        'total_donated': stats['total_donations'],
        'total_saved': db.execute("SELECT COUNT(*) FROM food_requests WHERE status IN ('Approved','Completed')").fetchone()[0],
        'num_donors': db.execute('SELECT COUNT(DISTINCT donor_id) FROM food_donations').fetchone()[0],
        'num_requests': db.execute('SELECT COUNT(*) FROM food_requests').fetchone()[0],
    })

    # Report-page data is shown directly inside the admin dashboard.
    report_stats = {
        'total_donations': db.execute('SELECT COUNT(*) FROM food_donations').fetchone()[0],
        'completed': db.execute("SELECT COUNT(*) FROM food_donations WHERE status='Completed'").fetchone()[0],
        'pending': db.execute("SELECT COUNT(*) FROM food_requests WHERE status='Pending'").fetchone()[0],
        'approved': db.execute("SELECT COUNT(*) FROM food_requests WHERE status='Approved'").fetchone()[0],
        'rejected': db.execute("SELECT COUNT(*) FROM food_requests WHERE status='Rejected'").fetchone()[0],
        'total_users': db.execute('SELECT COUNT(*) FROM users').fetchone()[0],
    }
    monthly_rows = db.execute("""
        SELECT substr(created_at, 1, 7) AS month, COUNT(*) AS total
        FROM food_donations WHERE created_at IS NOT NULL
        GROUP BY month ORDER BY month DESC LIMIT 6
    """).fetchall()
    monthly_rows = list(reversed(monthly_rows))
    weekly_rows = db.execute("""
        SELECT strftime('%Y-W%W', created_at) AS week, COUNT(*) AS total
        FROM food_donations WHERE created_at IS NOT NULL
        GROUP BY week ORDER BY week DESC LIMIT 8
    """).fetchall()
    weekly_rows = list(reversed(weekly_rows))
    yearly_rows = db.execute("""
        SELECT substr(created_at, 1, 4) AS year, COUNT(*) AS total
        FROM food_donations WHERE created_at IS NOT NULL
        GROUP BY year ORDER BY year DESC LIMIT 6
    """).fetchall()
    yearly_rows = list(reversed(yearly_rows))
    food_rows = db.execute("""
        SELECT food_type, COUNT(*) AS total FROM food_donations
        GROUP BY food_type ORDER BY total DESC LIMIT 5
    """).fetchall()
    recent_reports = db.execute("""
        SELECT fd.created_at, fd.food_name, fd.quantity, donor.name AS donor_name,
               receiver.name AS receiver_name, fr.status
        FROM food_requests fr
        JOIN food_donations fd ON fd.id = fr.donation_id
        JOIN users donor ON donor.id = fd.donor_id
        JOIN users receiver ON receiver.id = fr.receiver_id
        ORDER BY fr.requested_at DESC LIMIT 100
    """).fetchall()
    db.close()
    return render_template('admin_dashboard.html', stats=stats,
        report_stats=report_stats, stats_report=report_stats,
        monthly_labels=[r['month'] or '' for r in monthly_rows],
        monthly_values=[r['total'] for r in monthly_rows],
        weekly_labels=[r['week'] or '' for r in weekly_rows],
        weekly_values=[r['total'] for r in weekly_rows],
        yearly_labels=[r['year'] or '' for r in yearly_rows],
        yearly_values=[r['total'] for r in yearly_rows],
        food_labels=[r['food_type'] or 'Other' for r in food_rows],
        food_values=[r['total'] for r in food_rows], reports=recent_reports)



@app.route('/report')
def report():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if session.get('role') != 'Admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    db = get_db()
    total_donations = db.execute('SELECT COUNT(*) FROM food_donations').fetchone()[0]
    completed = db.execute("SELECT COUNT(*) FROM food_donations WHERE status='Completed'").fetchone()[0]
    pending = db.execute("SELECT COUNT(*) FROM food_requests WHERE status='Pending'").fetchone()[0]
    approved = db.execute("SELECT COUNT(*) FROM food_requests WHERE status='Approved'").fetchone()[0]
    rejected = db.execute("SELECT COUNT(*) FROM food_requests WHERE status='Rejected'").fetchone()[0]
    total_users = db.execute('SELECT COUNT(*) FROM users').fetchone()[0]

    monthly_rows = db.execute("""
        SELECT substr(created_at, 1, 7) AS month, COUNT(*) AS total
        FROM food_donations WHERE created_at IS NOT NULL
        GROUP BY month ORDER BY month DESC LIMIT 6
    """).fetchall()
    monthly_rows = list(reversed(monthly_rows))
    weekly_rows = db.execute("""
        SELECT strftime('%Y-W%W', created_at) AS week, COUNT(*) AS total
        FROM food_donations WHERE created_at IS NOT NULL
        GROUP BY week ORDER BY week DESC LIMIT 8
    """).fetchall()
    weekly_rows = list(reversed(weekly_rows))
    yearly_rows = db.execute("""
        SELECT substr(created_at, 1, 4) AS year, COUNT(*) AS total
        FROM food_donations WHERE created_at IS NOT NULL
        GROUP BY year ORDER BY year DESC LIMIT 6
    """).fetchall()
    yearly_rows = list(reversed(yearly_rows))
    food_rows = db.execute("""
        SELECT food_type, COUNT(*) AS total FROM food_donations
        GROUP BY food_type ORDER BY total DESC LIMIT 5
    """).fetchall()
    recent_reports = db.execute("""
        SELECT fd.created_at, fd.food_name, fd.quantity, donor.name AS donor_name,
               receiver.name AS receiver_name, fr.status
        FROM food_requests fr
        JOIN food_donations fd ON fd.id = fr.donation_id
        JOIN users donor ON donor.id = fd.donor_id
        JOIN users receiver ON receiver.id = fr.receiver_id
        ORDER BY fr.requested_at DESC LIMIT 100
    """).fetchall()
    db.close()

    return render_template('report.html',
        report_stats={'total_donations': total_donations, 'completed': completed,
               'pending': pending, 'approved': approved, 'rejected': rejected,
               'total_users': total_users},
        monthly_labels=[r['month'] or '' for r in monthly_rows],
        monthly_values=[r['total'] for r in monthly_rows],
        weekly_labels=[r['week'] or '' for r in weekly_rows],
        weekly_values=[r['total'] for r in weekly_rows],
        yearly_labels=[r['year'] or '' for r in yearly_rows],
        yearly_values=[r['total'] for r in yearly_rows],
        food_labels=[r['food_type'] or 'Other' for r in food_rows],
        food_values=[r['total'] for r in food_rows], reports=recent_reports)


@app.route('/admin/feedbacks')
def admin_feedbacks():
    if session.get('role') != 'Admin':
        return redirect(url_for('index'))
    db = get_db()
    feedbacks = db.execute('''
        SELECT f.id, f.rating, f.comment, f.created_at,
               u.name AS user_name, u.email AS user_email,
               fd.food_name, d.name AS donor_name,
               fr.status AS request_status
        FROM feedbacks f
        JOIN users u ON f.user_id=u.id
        JOIN food_requests fr ON f.request_id=fr.id
        JOIN food_donations fd ON fr.donation_id=fd.id
        JOIN users d ON fd.donor_id=d.id
        ORDER BY f.created_at DESC
    ''').fetchall()
    stats = {
        'total': len(feedbacks),
        'five_star': sum(1 for f in feedbacks if f['rating'] == 5),
        'average': round(sum(f['rating'] for f in feedbacks) / len(feedbacks), 1) if feedbacks else 0
    }
    db.close()
    return render_template('admin_feedbacks.html', feedbacks=feedbacks, stats=stats)

@app.route('/admin/users')
def admin_users():
    if session.get('role') != 'Admin':
        return redirect(url_for('index'))
    db = get_db()
    users = db.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    db.close()
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/<int:uid>')
def admin_view_user(uid):
    if session.get('role') != 'Admin':
        return redirect(url_for('index'))
    db = get_db()
    user = db.execute('SELECT * FROM users WHERE id=?', (uid,)).fetchone()
    if not user:
        db.close()
        flash('User not found.', 'danger')
        return redirect(url_for('admin_users'))

    donated_foods = db.execute('''
        SELECT fd.*,
               (SELECT u.name FROM users u
                JOIN food_requests fr ON fr.receiver_id=u.id
                WHERE fr.donation_id=fd.id
                ORDER BY fr.requested_at DESC LIMIT 1) AS receiver_name
        FROM food_donations fd
        WHERE fd.donor_id=?
        ORDER BY fd.created_at DESC
    ''', (uid,)).fetchall()

    received_foods = db.execute('''
        SELECT fr.*, fd.food_name, fd.quantity, fd.food_type, fd.available_date,
               fd.expiry_time, fd.pickup_location, fd.contact_details,
               fd.status AS donation_status, d.name AS donor_name,
               d.phone AS donor_phone, d.email AS donor_email
        FROM food_requests fr
        JOIN food_donations fd ON fr.donation_id=fd.id
        JOIN users d ON fd.donor_id=d.id
        WHERE fr.receiver_id=?
        ORDER BY fr.requested_at DESC
    ''', (uid,)).fetchall()

    summary = {
        'donated': len(donated_foods),
        'received': len(received_foods),
        'completed_received': sum(1 for r in received_foods if r['status'] == 'Completed'),
        'completed_donations': sum(1 for d in donated_foods if d['status'] == 'Completed'),
    }
    db.close()
    return render_template('admin_user_view.html', user=user,
                           donated_foods=donated_foods, received_foods=received_foods,
                           summary=summary)

@app.route('/admin/donations')
def admin_donations():
    if session.get('role') != 'Admin':
        return redirect(url_for('index'))
    db = get_db()
    donations = db.execute('''
        SELECT fd.*, u.name as donor_name FROM food_donations fd
        JOIN users u ON fd.donor_id = u.id ORDER BY fd.created_at DESC
    ''').fetchall()
    db.close()
    return render_template('admin_donations.html', donations=donations)

@app.route('/admin/requests')
def admin_requests():
    if session.get('role') != 'Admin':
        return redirect(url_for('index'))
    db = get_db()
    requests_list = db.execute('''
        SELECT fr.*, fd.food_name, fd.quantity, fd.pickup_location,
               u.name as receiver_name, d.name as donor_name
        FROM food_requests fr
        JOIN food_donations fd ON fr.donation_id = fd.id
        JOIN users u ON fr.receiver_id = u.id
        JOIN users d ON fd.donor_id = d.id
        ORDER BY fr.requested_at DESC
    ''').fetchall()
    db.close()
    return render_template('admin_requests.html', requests_list=requests_list)

@app.route('/request_action/<int:rid>/<action>', methods=['POST'])
def donor_request_action(rid, action):
    if 'user_id' not in session:
        flash('Please login to manage food requests.', 'warning')
        return redirect(url_for('login'))
    if action not in ('approve', 'reject', 'complete'):
        flash('Invalid request action.', 'danger')
        return redirect(url_for('dashboard'))

    db = get_db()
    req = db.execute('''
        SELECT fr.*, fd.donor_id, fd.food_name
        FROM food_requests fr
        JOIN food_donations fd ON fr.donation_id=fd.id
        WHERE fr.id=?
    ''', (rid,)).fetchone()

    # Only the owner/donor of the food can manage requests for that donation.
    if not req or req['donor_id'] != session['user_id']:
        db.close()
        flash('Only the food donor can manage this request.', 'danger')
        return redirect(url_for('dashboard'))

    current_status = req['status']
    if action == 'approve' and current_status == 'Pending':
        new_status = 'Approved'
        db.execute('UPDATE food_requests SET status=? WHERE id=?', (new_status, rid))
        db.execute('UPDATE food_donations SET status="Distributed" WHERE id=?', (req['donation_id'],))
        message = f'Your request for {req["food_name"]} has been approved.'
    elif action == 'reject' and current_status == 'Pending':
        new_status = 'Rejected'
        db.execute('UPDATE food_requests SET status=? WHERE id=?', (new_status, rid))
        db.execute('UPDATE food_donations SET status="Available" WHERE id=?', (req['donation_id'],))
        message = f'Your request for {req["food_name"]} has been rejected.'
    elif action == 'complete' and current_status == 'Approved':
        new_status = 'Completed'
        db.execute('UPDATE food_requests SET status=? WHERE id=?', (new_status, rid))
        db.execute('UPDATE food_donations SET status="Completed" WHERE id=?', (req['donation_id'],))
        message = f'Your food request for {req["food_name"]} has been completed. Please leave feedback!'
    else:
        db.close()
        flash('This action is not available for the current request status.', 'warning')
        return redirect(url_for('dashboard'))

    db.execute('INSERT INTO notifications (user_id, message, created_at) VALUES (?,?,?)',
               (req['receiver_id'], message, datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
    db.commit()
    db.close()
    flash(f'Request {new_status.lower()}.', 'success')
    return redirect(url_for('dashboard'))


# Legacy admin action URLs no longer permit admin approval/rejection/completion.
@app.route('/admin/approve_request/<int:rid>', methods=['POST'])
@app.route('/admin/complete_request/<int:rid>', methods=['POST'])
def legacy_admin_request_action(rid):
    flash('Requests are managed by the food donor from their dashboard.', 'info')
    return redirect(url_for('admin_requests'))


@app.route('/admin/delete_user/<int:uid>', methods=['POST'])
def delete_user(uid):
    if session.get('role') != 'Admin':
        return redirect(url_for('index'))
    db = get_db()
    db.execute('DELETE FROM users WHERE id=?', (uid,))
    db.commit()
    db.close()
    flash('User deleted.', 'info')
    return redirect(url_for('admin_users'))

@app.route('/waste_tracking')
def waste_tracking():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    stats = {
        'total_donated': db.execute('SELECT COUNT(*) FROM food_donations').fetchone()[0],
        'total_distributed': db.execute("SELECT COUNT(*) FROM food_requests WHERE status='Completed'").fetchone()[0],
        'total_saved': db.execute("SELECT COUNT(*) FROM food_requests WHERE status IN ('Approved','Completed')").fetchone()[0],
        'num_donors': db.execute("SELECT COUNT(DISTINCT donor_id) FROM food_donations").fetchone()[0],
        'num_requests': db.execute("SELECT COUNT(*) FROM food_requests").fetchone()[0],
    }
    monthly = db.execute('''
        SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as cnt
        FROM food_donations GROUP BY month ORDER BY month DESC LIMIT 6
    ''').fetchall()
    feedbacks = db.execute('''
        SELECT f.*, u.name FROM feedbacks f JOIN users u ON f.user_id=u.id
        ORDER BY f.created_at DESC LIMIT 10
    ''').fetchall()
    db.close()
    return render_template('waste_tracking.html', stats=stats, monthly=monthly, feedbacks=feedbacks)

@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    db = get_db()
    uid = session['user_id']
    donated = db.execute('''
        SELECT fd.*, (SELECT u.name FROM food_requests fr
                      JOIN users u ON fr.receiver_id=u.id
                      WHERE fr.donation_id=fd.id LIMIT 1) as recipient
        FROM food_donations fd WHERE fd.donor_id=? ORDER BY fd.created_at DESC
    ''', (uid,)).fetchall()
    received = db.execute('''
        SELECT fr.*, fd.food_name, fd.quantity, u.name as donor_name
        FROM food_requests fr
        JOIN food_donations fd ON fr.donation_id=fd.id
        JOIN users u ON fd.donor_id=u.id
        WHERE fr.receiver_id=? ORDER BY fr.requested_at DESC
    ''', (uid,)).fetchall()
    db.close()
    return render_template('history.html', donated=donated, received=received)

@app.route('/notifications_count')
def notifications_count():
    if 'user_id' not in session:
        return jsonify({'count': 0})
    db = get_db()
    count = db.execute('SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0',
                       (session['user_id'],)).fetchone()[0]
    db.close()
    return jsonify({'count': count})

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
