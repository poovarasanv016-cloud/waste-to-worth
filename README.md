# 🌿 Food Waste Management System

A full-featured web application built with **Python Flask** (frontend/server) and **SQLite** (database).

## 📁 Project Structure

```
food_waste_mgmt/
├── app.py              ← Main Flask application (all routes)
├── database.py         ← SQLite DB init + seeding
├── requirements.txt    ← Dependencies
├── food_waste.db       ← Auto-created SQLite database
├── static/
│   ├── css/style.css   ← Full custom stylesheet
│   └── js/main.js      ← Tab switching + notifications
└── templates/
    ├── base.html            ← Navbar + footer layout
    ├── index.html           ← Landing page
    ├── login.html           ← Login form
    ├── register.html        ← Registration form
    ├── dashboard.html       ← User dashboard
    ├── listings.html        ← Food listings with filters
    ├── donate.html          ← Add food donation
    ├── profile.html         ← User profile
    ├── feedback.html        ← Feedback form
    ├── history.html         ← Donation history
    ├── waste_tracking.html  ← Tracking dashboard
    ├── admin_dashboard.html ← Admin home
    ├── admin_users.html     ← Manage users
    ├── admin_donations.html ← View all donations
    └── admin_requests.html  ← Approve/reject requests
```

## 🚀 Setup & Run

```bash
# 1. Install Flask
pip install -r requirements.txt

# 2. Run the app
python app.py
```

Open your browser at: **http://127.0.0.1:5000**

## 🔑 Demo Login Credentials

| Role     | Email                    | Password     |
|----------|--------------------------|--------------|
| Admin    | admin@foodwaste.com      | admin123     |
| Donor    | ravi@example.com         | password123  |
| Donor    | priya@example.com        | password123  |
| Receiver | ngo@helphand.com         | password123  |

## ✨ Features

1. **User Auth** — Register/Login/Logout with role-based access (Donor, Receiver, Admin)
2. **Food Donation** — Add surplus food with name, quantity, type, expiry, location
3. **Food Listings** — Search & filter all available donations
4. **Food Request** — Receivers request food; status: Pending → Approved → Completed
5. **Admin Panel** — Manage users, donations, approve/reject requests
6. **Waste Tracking** — Dashboard with totals, monthly stats, environmental impact
7. **Notifications** — In-app bell notifications for request updates
8. **Donation History** — View donated and received food history
9. **Feedback System** — Star rating + comments after receiving food
