from flask import (
    Flask, request, redirect, url_for, session,
    render_template_string, flash, jsonify
)
import sqlite3
import os
import secrets
from datetime import datetime, timedelta
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

# ============================================================
# DATA4MINES - MANUAL INVESTMENT MANAGEMENT SYSTEM
# ============================================================

app = Flask(__name__)

app.secret_key = os.environ.get(
    "SECRET_KEY",
    "CHANGE_THIS_TO_A_LONG_RANDOM_SECRET_KEY"
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Use /data/ on Cyclic, use local folder on PC
DB_PATH = '/data/data4mines.db' if os.path.exists('/data') else os.path.join(BASE_DIR, "data4mines.db")

ADMIN_PHONE = "0792759363"
ADMIN_PASSWORD = "twix1831"

REFERRAL_REWARD = 5000
WITHDRAWAL_TAX_PERCENT = 5


# ============================================================
# DATABASE
# ============================================================

def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    db = get_db()

    db.executescript("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        balance INTEGER DEFAULT 0,
        referral_code TEXT UNIQUE NOT NULL,
        referred_by INTEGER,
        referral_reward_paid INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL,
        FOREIGN KEY (referred_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS machines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        series TEXT NOT NULL,
        image TEXT DEFAULT '',
        purchase_amount INTEGER NOT NULL,
        withdrawal_amount INTEGER NOT NULL,
        days INTEGER NOT NULL,
        stock INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS user_machines (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        machine_id INTEGER NOT NULL,
        purchase_amount INTEGER NOT NULL,
        withdrawal_amount INTEGER NOT NULL,
        purchased_at TEXT NOT NULL,
        maturity_at TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (machine_id) REFERENCES machines(id)
    );

    CREATE TABLE IF NOT EXISTS deposits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        payment_number TEXT NOT NULL,
        sender_name TEXT NOT NULL,
        reference TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        admin_note TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        approved_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS withdrawals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        tax INTEGER DEFAULT 0,
        net_amount INTEGER DEFAULT 0,
        phone TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        admin_note TEXT DEFAULT '',
        created_at TEXT NOT NULL,
        approved_at TEXT,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        amount INTEGER NOT NULL,
        description TEXT NOT NULL,
        status TEXT DEFAULT 'approved',
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS payment_numbers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        number TEXT UNIQUE NOT NULL,
        names TEXT NOT NULL,
        active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS chats (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        sender TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS admin_users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        phone TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)

    # Primary admin
    existing = db.execute(
        "SELECT id FROM users WHERE phone = ?",
        (ADMIN_PHONE,)
    ).fetchone()

    if not existing:
        db.execute("""
            INSERT INTO users
            (name, phone, password_hash, balance, referral_code,
             is_admin, created_at)
            VALUES (?, ?, ?, 0, ?, 1, ?)
        """, (
            "DATA4MINES Administrator",
            ADMIN_PHONE,
            generate_password_hash(ADMIN_PASSWORD),
            "ADMIN-" + secrets.token_hex(4).upper(),
            now()
        ))
    else:
        db.execute(
            "UPDATE users SET is_admin = 1 WHERE phone = ?",
            (ADMIN_PHONE,)
        )

    # Primary deposit number
    payment = db.execute(
        "SELECT id FROM payment_numbers WHERE number = ?",
        (ADMIN_PHONE,)
    ).fetchone()

    if not payment:
        db.execute("""
            INSERT INTO payment_numbers
            (number, names, active, created_at)
            VALUES (?, ?, 1, ?)
        """, (
            ADMIN_PHONE,
            "Nuwahereza Christine",
            now()
        ))

    # Default machines
    machine_count = db.execute(
        "SELECT COUNT(*) AS c FROM machines"
    ).fetchone()["c"]

    if machine_count == 0:
        machines = [
            (
                "DATA4MINES Starter",
                "M1",
                "m1.jpg",
                10000,
                13000,
                7,
                100
            ),
            (
                "DATA4MINES Bronze",
                "M2",
                "m2.jpg",
                20000,
                28000,
                10,
                100
            ),
            (
                "DATA4MINES Silver",
                "M3",
                "m3.jpg",
                50000,
                75000,
                15,
                100
            ),
            (
                "DATA4MINES Gold",
                "M4",
                "m4.jpg",
                100000,
                160000,
                20,
                100
            ),
            (
                "DATA4MINES Platinum",
                "M5",
                "m5.jpg",
                250000,
                425000,
                30,
                100
            ),
            (
                "DATA4MINES Diamond",
                "M6",
                "m6.jpg",
                500000,
                900000,
                45,
                100
            ),
        ]

        for machine in machines:
            db.execute("""
                INSERT INTO machines
                (name, series, image, purchase_amount,
                 withdrawal_amount, days, stock, active, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
            """, (*machine, now()))

    db.commit()
    db.close()


# ============================================================
# HELPERS
# ============================================================

def current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    db = get_db()
    user = db.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()
    db.close()

    return user


def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not current_user():
            return redirect(url_for("login"))
        return func(*args, **kwargs)
    return wrapper


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        user = current_user()

        if not user or not user["is_admin"]:
            flash("Administrator access required.", "error")
            return redirect(url_for("dashboard"))

        return func(*args, **kwargs)

    return wrapper


def money(value):
    return f"{int(value or 0):,} UGX"


# ============================================================
# CSS / LAYOUT
# ============================================================

STYLE = """
<style>
* {
    box-sizing: border-box;
}

html {
    font-size: 16px;
}

body {
    margin: 0;
    font-family: Arial, Helvetica, sans-serif;
    background: #06120d;
    color: #f5f5f5;
    font-size: 16px;
}

a {
    color: inherit;
    text-decoration: none;
}

.nav {
    background: #071a11;
    border-bottom: 1px solid #214936;
    padding: 15px 20px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    position: sticky;
    top: 0;
    z-index: 50;
}

.logo {
    font-size: 22px;
    font-weight: bold;
}

.logo span {
    color: #00e676;
}

.navlinks {
    display: flex;
    gap: 12px;
    flex-wrap: wrap;
}

.navlinks a {
    padding: 9px 12px;
    border-radius: 8px;
}

.navlinks a:hover {
    background: #123b27;
}

.container {
    width: min(1150px, 94%);
    margin: 25px auto;
}

.card {
    background: #0b2116;
    border: 1px solid #205238;
    border-radius: 16px;
    padding: 20px;
    margin-bottom: 20px;
}

.grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 16px;
}

.stats {
    font-size: 26px;
    font-weight: bold;
    margin-top: 8px;
}

.muted {
    color: #a9b8af;
}

.btn {
    display: inline-block;
    border: 0;
    border-radius: 9px;
    padding: 12px 16px;
    background: #00c853;
    color: white;
    cursor: pointer;
    font-size: 16px;
    font-weight: bold;
}

.btn:hover {
    background: #00a844;
}

.btn-danger {
    background: #d32f2f;
}

.btn-warning {
    background: #e09b00;
}

.btn-secondary {
    background: #315343;
}

input,
select,
textarea {
    width: 100%;
    padding: 12px;
    border-radius: 8px;
    border: 1px solid #37634a;
    background: #07170f;
    color: white;
    font-size: 16px;
    margin: 6px 0 14px;
}

textarea {
    min-height: 100px;
    resize: vertical;
}

label {
    font-weight: bold;
}

table {
    width: 100%;
    border-collapse: collapse;
}

th,
td {
    padding: 12px 8px;
    border-bottom: 1px solid #214936;
    text-align: left;
}

.machine-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 18px;
}

.machine {
    background: #0b2116;
    border: 1px solid #286043;
    border-radius: 15px;
    overflow: hidden;
}

.machine img {
    width: 100%;
    height: 180px;
    object-fit: cover;
    background: #13251b;
}

.machine-body {
    padding: 16px;
}

.badge {
    display: inline-block;
    padding: 5px 9px;
    border-radius: 20px;
    background: #173f2a;
    margin: 3px;
}

.success {
    color: #00e676;
}

.warning {
    color: #ffc107;
}

.danger {
    color: #ff5252;
}

.flash {
    padding: 13px;
    margin-bottom: 15px;
    border-radius: 9px;
    background: #173f2a;
}

.chat {
    max-height: 450px;
    overflow-y: auto;
}

.chat-message {
    padding: 10px;
    margin: 8px 0;
    border-radius: 10px;
    background: #132c1e;
}

.chat-admin {
    background: #174a2d;
}

canvas {
    max-width: 100%;
}

.footer {
    text-align: center;
    padding: 30px;
    color: #81958a;
}

@media (max-width: 800px) {
    body {
        font-size: 16px;
    }

    .nav {
        align-items: flex-start;
        gap: 12px;
        flex-direction: column;
    }

    .navlinks {
        width: 100%;
        overflow-x: auto;
        flex-wrap: nowrap;
    }

    .navlinks a {
        white-space: nowrap;
    }

    .grid,
    .machine-grid {
        grid-template-columns: 1fr;
    }

    .container {
        width: 94%;
        margin: 16px auto;
    }

    .card {
        padding: 16px;
    }

    table {
        display: block;
        overflow-x: auto;
        white-space: nowrap;
    }

    .machine img {
        height: 210px;
    }
}
</style>
"""


# ============================================================
# PAGE TEMPLATE
# ============================================================

PAGE = """
<!doctype html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport"
      content="width=device-width, initial-scale=1.0">
<title>{{ title }} - DATA4MINES</title>
""" + STYLE + """
</head>

<body>

<nav class="nav">

<div class="logo">
DATA4<span>MINES</span>
</div>

{% if user %}
<div class="navlinks">

<a href="{{ url_for('dashboard') }}">Dashboard</a>
<a href="{{ url_for('shop') }}">🛒 Shop</a>
<a href="{{ url_for('my_machines') }}">⚙ My Machines</a>
<a href="{{ url_for('rewards') }}">🎁 Rewards</a>
<a href="{{ url_for('deposit') }}">Deposit</a>
<a href="{{ url_for('withdraw') }}">Withdraw</a>
<a href="{{ url_for('notifications') }}">🔔</a>
<a href="{{ url_for('chat') }}">💬</a>

{% if user["is_admin"] %}
<a href="{{ url_for('admin') }}">Admin</a>
{% endif %}

<a href="{{ url_for('logout') }}">Logout</a>

</div>
{% endif %}

</nav>

<div class="container">

{% with messages = get_flashed_messages(with_categories=true) %}
{% for category, message in messages %}
<div class="flash">{{ message }}</div>
{% endfor %}
{% endwith %}

{{ content|safe }}

</div>

<div class="footer">
DATA4MINES &copy; {{ year }}
</div>

</body>
</html>
"""


def page(title, content, **context):
    user = current_user()

    return render_template_string(
        PAGE,
        title=title,
        content=render_template_string(
            content,
            **context
        ),
        user=user,
        year=datetime.now().year
    )


# ============================================================
# LOGIN
# ============================================================

@app.route("/")
def index():
    if current_user():
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        db = get_db()

        user = db.execute(
            "SELECT * FROM users WHERE phone = ? AND active = 1",
            (phone,)
        ).fetchone()

        db.close()

        if user and check_password_hash(
            user["password_hash"],
            password
        ):
            session.clear()
            session["user_id"] = user["id"]

            return redirect(url_for("dashboard"))

        flash("Invalid phone number or password.", "error")

    return page(
        "Login",
        """
        <div class="card" style="max-width:500px;margin:50px auto;">

        <h1>DATA4MINES</h1>

        <p class="muted">
        Sign in to your account.
        </p>

        <form method="post">

        <label>Phone number</label>
        <input name="phone"
               placeholder="07XXXXXXXX"
               required>

        <label>Password</label>
        <input type="password"
               name="password"
               required>

        <button class="btn">
        Login
        </button>

        </form>

        <hr>

        <p>
        Don't have an account?
        <a class="success"
           href="{{ url_for('register') }}">
           Register
        </a>
        </p>

        </div>
        """
    )


# ============================================================
# REGISTER
# ============================================================

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        referral = request.form.get("referral", "").strip()

        if not name or not phone or not password:
            flash("All required fields must be completed.", "error")
            return redirect(url_for("register"))

        db = get_db()

        existing = db.execute(
            "SELECT id FROM users WHERE phone = ?",
            (phone,)
        ).fetchone()

        if existing:
            db.close()
            flash("This phone number is already registered.", "error")
            return redirect(url_for("register"))

        referred_by = None

        if referral:
            referrer = db.execute(
                "SELECT id FROM users WHERE referral_code = ?",
                (referral,)
            ).fetchone()

            if referrer:
                referred_by = referrer["id"]

        code = "D4M-" + secrets.token_hex(5).upper()

        db.execute("""
            INSERT INTO users
            (name, phone, password_hash, balance,
             referral_code, referred_by, created_at)
            VALUES (?, ?, ?, 0, ?, ?, ?)
        """, (
            name,
            phone,
            generate_password_hash(password),
            code,
            referred_by,
            now()
        ))

        db.commit()
        db.close()

        flash("Registration successful. You can now login.", "success")

        return redirect(url_for("login"))

    return page(
        "Register",
        """
        <div class="card" style="max-width:550px;margin:auto;">

        <h1>Create account</h1>

        <form method="post">

        <label>Full name</label>
        <input name="name" required>

        <label>Phone number</label>
        <input name="phone"
               placeholder="07XXXXXXXX"
               required>

        <label>Password</label>
        <input type="password"
               name="password"
               minlength="6"
               required>

        <label>Referral code</label>
        <input name="referral"
               placeholder="Optional">

        <button class="btn">
        Register
        </button>

        </form>

        </div>
        """
    )


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():

    user = current_user()
    db = get_db()

    machines = db.execute("""
        SELECT um.*, m.name, m.series, m.image
        FROM user_machines um
        JOIN machines m ON m.id = um.machine_id
        WHERE um.user_id = ?
        ORDER BY um.id DESC
        LIMIT 5
    """, (user["id"],)).fetchall()

    deposits = db.execute("""
        SELECT COALESCE(SUM(amount), 0) total
        FROM deposits
        WHERE user_id = ? AND status = 'approved'
    """, (user["id"],)).fetchone()["total"]

    withdrawals = db.execute("""
        SELECT COALESCE(SUM(amount), 0) total
        FROM withdrawals
        WHERE user_id = ? AND status = 'approved'
    """, (user["id"],)).fetchone()["total"]

    db.close()

    return page(
        "Dashboard",
        """
        <h1>Welcome, {{ user["name"] }}</h1>

        <div class="grid">

        <div class="card">
        <div class="muted">Available Balance</div>
        <div class="stats">{{ "{:,}".format(user["balance"]) }} UGX</div>
        </div>

        <div class="card">
        <div class="muted">Approved Deposits</div>
        <div class="stats">{{ "{:,}".format(deposits) }} UGX</div>
        </div>

        <div class="card">
        <div class="muted">Approved Withdrawals</div>
        <div class="stats">{{ "{:,}".format(withdrawals) }} UGX</div>
        </div>

        </div>

        <div class="card">

        <h2>Quick actions</h2>

        <a class="btn" href="{{ url_for('shop') }}">
        🛒 Shop
        </a>

        <a class="btn btn-secondary"
           href="{{ url_for('my_machines') }}">
        ⚙ My Machines
        </a>

        <a class="btn btn-secondary"
           href="{{ url_for('rewards') }}">
        🎁 Rewards
        </a>

        </div>

        <div class="card">

        <h2>My Machines</h2>

        {% if machines %}

        <div class="machine-grid">

        {% for machine in machines %}

        <div class="machine">

        <img src="{{ url_for(
            'static',
            filename='machines/' + machine['image']
        ) }}"
        onerror="this.style.display='none'">

        <div class="machine-body">

        <h3>{{ machine["name"] }}</h3>

        <p>Series: {{ machine["series"] }}</p>

        <p>
        Purchase:
        {{ "{:,}".format(machine["purchase_amount"]) }} UGX
        </p>

        <p class="success">
        Withdrawal:
        {{ "{:,}".format(machine["withdrawal_amount"]) }} UGX
        </p>

        </div>
        </div>

        {% endfor %}

        </div>

        {% else %}

        <p>You have not purchased a machine yet.</p>

        <a class="btn"
           href="{{ url_for('shop') }}">
           Open Shop
        </a>

        {% endif %}

        </div>
        """,
        user=user,
        machines=machines,
        deposits=deposits,
        withdrawals=withdrawals
    )


# ============================================================
# SHOP
# ============================================================

@app.route("/shop")
@login_required
def shop():

    db = get_db()

    machines = db.execute("""
        SELECT *
        FROM machines
        WHERE active = 1
        ORDER BY id ASC
    """).fetchall()

    db.close()

    return page(
        "Shop",
        """
        <h1>🛒 DATA4MINES Shop</h1>

        <p class="muted">
        Purchase an available machine using your approved balance.
        Machine purchases do not require separate administrator approval.
        </p>

        <div class="machine-grid">

        {% for machine in machines %}

        <div class="machine">

        <img
        src="{{ url_for(
            'static',
            filename='machines/' + machine['image']
        ) }}"
        onerror="this.src='https://via.placeholder.com/600x350?text=DATA4MINES'">

        <div class="machine-body">

        <span class="badge">
        {{ machine["series"] }}
        </span>

        <h2>{{ machine["name"] }}</h2>

        <p>
        Purchase amount:
        <strong>
        {{ "{:,}".format(machine["purchase_amount"]) }} UGX
        </strong>
        </p>

        <p>
        Total withdrawal:
        <strong class="success">
        {{ "{:,}".format(machine["withdrawal_amount"]) }} UGX
        </strong>
        </p>

        <p>
        Duration:
        {{ machine["days"] }} days
        </p>

        <p>
        Stock:
        {% if machine["stock"] > 0 %}
        <span class="success">
        {{ machine["stock"] }}
        </span>
        {% else %}
        <span class="danger">Out of stock</span>
        {% endif %}
        </p>

        {% if machine["stock"] > 0 %}

        <form method="post"
              action="{{ url_for(
                  'buy_machine',
                  machine_id=machine['id']
              ) }}">

        <button class="btn"
                type="submit">
        Purchase Machine
        </button>

        </form>

        {% endif %}

        </div>
        </div>

        {% endfor %}

        </div>
        """,
        machines=machines
    )


@app.route("/buy-machine/<int:machine_id>", methods=["POST"])
@login_required
def buy_machine(machine_id):

    user = current_user()
    db = get_db()

    machine = db.execute(
        "SELECT * FROM machines WHERE id = ? AND active = 1",
        (machine_id,)
    ).fetchone()

    if not machine:
        db.close()
        flash("Machine not found.", "error")
        return redirect(url_for("shop"))

    if machine["stock"] <= 0:
        db.close()
        flash("This machine is out of stock.", "error")
        return redirect(url_for("shop"))

    if user["balance"] < machine["purchase_amount"]:
        db.close()
        flash("Insufficient approved balance.", "error")
        return redirect(url_for("shop"))

    purchased = datetime.now()
    maturity = purchased + timedelta(days=machine["days"])

    db.execute("""
        UPDATE users
        SET balance = balance - ?
        WHERE id = ?
    """, (
        machine["purchase_amount"],
        user["id"]
    ))

    db.execute("""
        UPDATE machines
        SET stock = stock - 1
        WHERE id = ?
    """, (machine_id,))

    db.execute("""
        INSERT INTO user_machines
        (user_id, machine_id, purchase_amount,
         withdrawal_amount, purchased_at,
         maturity_at, status)
        VALUES (?, ?, ?, ?, ?, ?, 'active')
    """, (
        user["id"],
        machine["id"],
        machine["purchase_amount"],
        machine["withdrawal_amount"],
        purchased.strftime("%Y-%m-%d %H:%M:%S"),
        maturity.strftime("%Y-%m-%d %H:%M:%S")
    ))

    db.execute("""
        INSERT INTO transactions
        (user_id, type, amount, description, status, created_at)
        VALUES (?, 'machine_purchase', ?, ?, 'approved', ?)
    """, (
        user["id"],
        machine["purchase_amount"],
        f"Purchased {machine['name']}",
        now()
    ))

    # Referral reward
    if user["referred_by"] and not user["referral_reward_paid"]:

        referrer = db.execute("""
            SELECT id
            FROM users
            WHERE id = ?
        """, (user["referred_by"],)).fetchone()

        if referrer:
            db.execute("""
                UPDATE users
                SET balance = balance + ?
                WHERE id = ?
            """, (
                REFERRAL_REWARD,
                referrer["id"]
            ))

            db.execute("""
                UPDATE users
                SET referral_reward_paid = 1
                WHERE id = ?
            """, (user["id"],))

            db.execute("""
                INSERT INTO transactions
                (user_id, type, amount,
                 description, status, created_at)
                VALUES (?, 'referral_reward', ?,
                        'Referral reward', 'approved', ?)
            """, (
                referrer["id"],
                REFERRAL_REWARD,
                now()
            ))

    db.commit()
    db.close()

    flash(
        "Machine purchased successfully.",
        "success"
    )

    return redirect(url_for("my_machines"))


# ============================================================
# MY MACHINES
# ============================================================

@app.route("/my-machines")
@login_required
def my_machines():

    user = current_user()
    db = get_db()

    machines = db.execute("""
        SELECT um.*, m.name, m.series, m.image
        FROM user_machines um
        JOIN machines m ON m.id = um.machine_id
        WHERE um.user_id = ?
        ORDER BY um.id DESC
    """, (user["id"],)).fetchall()

    db.close()

    return page(
        "My Machines",
        """
        <h1>⚙ My Machines</h1>

        {% if machines %}

        <div class="machine-grid">

        {% for machine in machines %}

        <div class="machine">

        <img
        src="{{ url_for(
            'static',
            filename='machines/' + machine['image']
        ) }}"
        onerror="this.style.display='none'">

        <div class="machine-body">

        <h2>{{ machine["name"] }}</h2>

        <p>Series: {{ machine["series"] }}</p>

        <p>
        Purchased:
        {{ "{:,}".format(machine["purchase_amount"]) }} UGX
        </p>

        <p>
        Total withdrawal:
        {{ "{:,}".format(machine["withdrawal_amount"]) }} UGX
        </p>

        <p>
        Purchased:
        {{ machine["purchased_at"] }}
        </p>

        <p>
        Matures:
        {{ machine["maturity_at"] }}
        </p>

        <span class="badge">
        {{ machine["status"] }}
        </span>

        </div>
        </div>

        {% endfor %}

        </div>

        {% else %}

        <div class="card">
        <p>No machines purchased yet.</p>
        <a class="btn"
           href="{{ url_for('shop') }}">
           Visit Shop
        </a>
        </div>

        {% endif %}
        """,
        machines=machines
    )


# ============================================================
# DEPOSIT
# ============================================================

@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():

    user = current_user()
    db = get_db()

    numbers = db.execute("""
        SELECT *
        FROM payment_numbers
        WHERE active = 1
        ORDER BY id ASC
    """).fetchall()

    if request.method == "POST":

        amount_text = request.form.get("amount", "")
        sender_name = request.form.get(
            "sender_name", ""
        ).strip()
        reference = request.form.get(
            "reference", ""
        ).strip()

        try:
            amount = int(amount_text)
        except ValueError:
            amount = 0

        if amount <= 0:
            flash("Enter a valid deposit amount.", "error")
            db.close()
            return redirect(url_for("deposit"))

        if not sender_name or not reference:
            flash(
                "Sender name and transaction reference are required.",
                "error"
            )
            db.close()
            return redirect(url_for("deposit"))

        payment_number = numbers[0]["number"] if numbers else ADMIN_PHONE

        db.execute("""
            INSERT INTO deposits
            (user_id, amount, payment_number,
             sender_name, reference,
             status, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """, (
            user["id"],
            amount,
            payment_number,
            sender_name,
            reference,
            now()
        ))

        db.commit()
        db.close()

        flash(
            "Deposit submitted. It will appear in your balance after administrator approval.",
            "success"
        )

        return redirect(url_for("dashboard"))

    db.close()

    return page(
        "Deposit",
        """
        <h1>Deposit</h1>

        <div class="card">

        <h2>Send money to</h2>

        {% for number in numbers %}

        <div class="card">

        <strong>{{ number["number"] }}</strong>

        <br>

        {{ number["names"] }}

        </div>

        {% endfor %}

        <p class="muted">
        After sending money, submit the transaction details below.
        Your balance changes only after administrator approval.
        </p>

        </div>

        <div class="card">

        <form method="post">

        <label>Amount (UGX)</label>
        <input type="number"
               name="amount"
               min="1"
               required>

        <label>Sender name</label>
        <input name="sender_name"
               required>

        <label>Transaction reference / TX ID</label>
        <input name="reference"
               required>

        <button class="btn">
        Submit Deposit
        </button>

        </form>

        </div>
        """,
        numbers=numbers
    )


# ============================================================
# WITHDRAW
# ============================================================

@app.route("/withdraw", methods=["GET", "POST"])
@login_required
def withdraw():

    user = current_user()

    if request.method == "POST":

        try:
            amount = int(request.form.get("amount", "0"))
        except ValueError:
            amount = 0

        phone = request.form.get(
            "phone", ""
        ).strip()

        if amount <= 0:
            flash("Enter a valid amount.", "error")
            return redirect(url_for("withdraw"))

        if amount > user["balance"]:
            flash("Insufficient balance.", "error")
            return redirect(url_for("withdraw"))

        if not phone:
            flash("Enter the withdrawal phone number.", "error")
            return redirect(url_for("withdraw"))

        tax = int(amount * WITHDRAWAL_TAX_PERCENT / 100)
        net = amount - tax

        db = get_db()

        # Reserve the amount immediately.
        db.execute("""
            UPDATE users
            SET balance = balance - ?
            WHERE id = ?
        """, (
            amount,
            user["id"]
        ))

        db.execute("""
            INSERT INTO withdrawals
            (user_id, amount, tax, net_amount,
             phone, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?)
        """, (
            user["id"],
            amount,
            tax,
            net,
            phone,
            now()
        ))

        db.commit()
        db.close()

        flash(
            "Withdrawal submitted and is pending administrator approval.",
            "success"
        )

        return redirect(url_for("dashboard"))

    return page(
        "Withdraw",
        """
        <div class="card">

        <h1>Withdraw</h1>

        <p>
        Available balance:
        <strong>
        {{ "{:,}".format(user["balance"]) }} UGX
        </strong>
        </p>

        <p class="muted">
        Withdrawal requests require administrator approval.
        A {{ tax }}% tax is calculated on the requested amount.
        </p>

        <form method="post">

        <label>Amount (UGX)</label>

        <input type="number"
               name="amount"
               min="1"
               max="{{ user['balance'] }}"
               required>

        <label>Phone number</label>

        <input name="phone"
               placeholder="07XXXXXXXX"
               required>

        <button class="btn">
        Request Withdrawal
        </button>

        </form>

        </div>
        """,
        user=user,
        tax=WITHDRAWAL_TAX_PERCENT
    )


# ============================================================
# REWARDS / REFERRALS
# ============================================================

@app.route("/rewards")
@login_required
def rewards():

    user = current_user()

    referral_link = (
        request.host_url.rstrip("/")
        + "/register?ref="
        + user["referral_code"]
    )

    db = get_db()

    referred = db.execute("""
        SELECT name, phone, created_at,
               referral_reward_paid
        FROM users
        WHERE referred_by = ?
        ORDER BY id DESC
    """, (user["id"],)).fetchall()

    db.close()

    return page(
        "Rewards",
        """
        <div class="card">

        <h1>🎁 Referral Rewards</h1>

        <h2>Reward: 5,000 UGX</h2>

        <p>
        Share your referral link.
        The referral reward becomes eligible when the invited
        user purchases a machine.
        </p>

        <input value="{{ referral_link }}"
               readonly
               onclick="this.select()">

        <button class="btn"
        onclick="navigator.clipboard.writeText(
            '{{ referral_link }}'
        )">
        Copy Referral Link
        </button>

        </div>

        <div class="card">

        <h2>Your Referrals</h2>

        {% if referred %}

        <table>

        <tr>
        <th>Name</th>
        <th>Phone</th>
        <th>Reward</th>
        </tr>

        {% for person in referred %}

        <tr>
        <td>{{ person["name"] }}</td>
        <td>{{ person["phone"] }}</td>

        <td>
        {% if person["referral_reward_paid"] %}
        <span class="success">5,000 UGX paid</span>
        {% else %}
        <span class="warning">
        Waiting for machine purchase
        </span>
        {% endif %}
        </td>

        </tr>

        {% endfor %}

        </table>

        {% else %}

        <p>No referrals yet.</p>

        {% endif %}

        </div>
        """,
        referral_link=referral_link,
        referred=referred
    )


# ============================================================
# NOTIFICATIONS
# ============================================================

@app.route("/notifications")
@login_required
def notifications():

    db = get_db()

    items = db.execute("""
        SELECT *
        FROM notifications
        ORDER BY id DESC
        LIMIT 50
    """).fetchall()

    db.close()

    return page(
        "Notifications",
        """
        <h1>🔔 Notifications</h1>

        {% for item in items %}

        <div class="card">

        <h3>{{ item["title"] }}</h3>

        <p>{{ item["message"] }}</p>

        <small class="muted">
        {{ item["created_at"] }}
        </small>

        </div>

        {% else %}

        <div class="card">
        No notifications.
        </div>

        {% endfor %}
        """,
        items=items
    )


# ============================================================
# CHAT
# ============================================================

@app.route("/chat", methods=["GET", "POST"])
@login_required
def chat():

    user = current_user()
    db = get_db()

    if request.method == "POST":

        message = request.form.get(
            "message", ""
        ).strip()

        if message:
            db.execute("""
                INSERT INTO chats
                (user_id, sender, message, created_at)
                VALUES (?, 'user', ?, ?)
            """, (
                user["id"],
                message,
                now()
            ))

            db.commit()

        db.close()

        return redirect(url_for("chat"))

    messages = db.execute("""
        SELECT *
        FROM chats
        WHERE user_id = ?
        ORDER BY id ASC
    """, (user["id"],)).fetchall()

    db.close()

    return page(
        "Chat",
        """
        <div class="card">

        <h1>💬 Chat with Admin</h1>

        <div class="chat">

        {% for msg in messages %}

        <div class="chat-message
        {% if msg['sender'] == 'admin' %}
        chat-admin
        {% endif %}">

        <strong>
        {% if msg["sender"] == "admin" %}
        Admin
        {% else %}
        You
        {% endif %}
        </strong>

        <p>{{ msg["message"] }}</p>

        <small class="muted">
        {{ msg["created_at"] }}
        </small>

        </div>

        {% endfor %}

        </div>

        <form method="post">

        <textarea name="message"
                  placeholder="Write your message..."
                  required></textarea>

        <button class="btn">
        Send Message
        </button>

        </form>

        </div>
        """,
        messages=messages
    )


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@app.route("/admin")
@admin_required
def admin():

    db = get_db()

    users = db.execute(
        "SELECT COUNT(*) c FROM users WHERE is_admin = 0"
    ).fetchone()["c"]

    deposits = db.execute(
        "SELECT COUNT(*) c FROM deposits"
    ).fetchone()["c"]

    deposit_amount = db.execute(
        "SELECT COALESCE(SUM(amount),0) total "
        "FROM deposits WHERE status='approved'"
    ).fetchone()["total"]

    withdrawals = db.execute(
        "SELECT COUNT(*) c FROM withdrawals"
    ).fetchone()["c"]

    withdrawal_amount = db.execute(
        "SELECT COALESCE(SUM(amount),0) total "
        "FROM withdrawals WHERE status='approved'"
    ).fetchone()["total"]

    pending_deposits = db.execute("""
        SELECT d.*, u.name, u.phone
        FROM deposits d
        JOIN users u ON u.id = d.user_id
        WHERE d.status = 'pending'
        ORDER BY d.id ASC
    """).fetchall()

    pending_withdrawals = db.execute("""
        SELECT w.*, u.name, u.phone AS user_phone
        FROM withdrawals w
        JOIN users u ON u.id = w.user_id
        WHERE w.status = 'pending'
        ORDER BY w.id ASC
    """).fetchall()

    machines = db.execute("""
        SELECT *
        FROM machines
        ORDER BY id ASC
    """).fetchall()

    db.close()

    return page(
        "Admin",
        """
        <h1>Administrator Panel</h1>

        <div class="grid">

        <div class="card">
        <div class="muted">Registered Users</div>
        <div class="stats">{{ users }}</div>
        </div>

        <div class="card">
        <div class="muted">Approved Deposits</div>
        <div class="stats">
        {{ "{:,}".format(deposit_amount) }} UGX
        </div>
        </div>

        <div class="card">
        <div class="muted">Approved Withdrawals</div>
        <div class="stats">
        {{ "{:,}".format(withdrawal_amount) }} UGX
        </div>
        </div>

        </div>

        <div class="card">

        <h2>📊 Company Flow</h2>

        <canvas id="flowChart"></canvas>

        </div>

        <div class="card">

        <h2>Pending Deposits</h2>

        {% if pending_deposits %}

        <table>

        <tr>
        <th>User</th>
        <th>Amount</th>
        <th>Sender</th>
        <th>Reference</th>
        <th>Action</th>
        </tr>

        {% for d in pending_deposits %}

        <tr>

        <td>
        {{ d["name"] }}<br>
        {{ d["phone"] }}
        </td>

        <td>{{ "{:,}".format(d["amount"]) }} UGX</td>

        <td>{{ d["sender_name"] }}</td>

        <td>{{ d["reference"] }}</td>

        <td>

        <form method="post"
              action="{{ url_for(
                  'approve_deposit',
                  deposit_id=d['id']
              ) }}"
              style="display:inline">

        <button class="btn">
        Approve
        </button>

        </form>

        <form method="post"
              action="{{ url_for(
                  'reject_deposit',
                  deposit_id=d['id']
              ) }}"
              style="display:inline">

        <button class="btn btn-danger">
        Reject
        </button>

        </form>

        </td>

        </tr>

        {% endfor %}

        </table>

        {% else %}

        <p>No pending deposits.</p>

        {% endif %}

        </div>


        <div class="card">

        <h2>Pending Withdrawals</h2>

        {% if pending_withdrawals %}

        <table>

        <tr>
        <th>User</th>
        <th>Requested</th>
        <th>Tax</th>
        <th>Net</th>
        <th>Phone</th>
        <th>Action</th>
        </tr>

        {% for w in pending_withdrawals %}

        <tr>

        <td>
        {{ w["name"] }}<br>
        {{ w["user_phone"] }}
        </td>

        <td>
        {{ "{:,}".format(w["amount"]) }} UGX
        </td>

        <td>
        {{ "{:,}".format(w["tax"]) }} UGX
        </td>

        <td>
        {{ "{:,}".format(w["net_amount"]) }} UGX
        </td>

        <td>{{ w["phone"] }}</td>

        <td>

        <form method="post"
              action="{{ url_for(
                  'approve_withdrawal',
                  withdrawal_id=w['id']
              ) }}"
              style="display:inline">

        <button class="btn">
        Approve
        </button>

        </form>

        <form method="post"
              action="{{ url_for(
                  'reject_withdrawal',
                  withdrawal_id=w['id']
              ) }}"
              style="display:inline">

        <button class="btn btn-danger">
        Reject
        </button>

        </form>

        </td>

        </tr>

        {% endfor %}

        </table>

        {% else %}

        <p>No pending withdrawals.</p>

        {% endif %}

        </div>


        <div class="card">

        <h2>Machine Management</h2>

        <p>
        Machine purchases are automatically recorded.
        No separate admin approval is required.
        </p>

        <form method="post"
              action="{{ url_for('add_machine') }}">

        <label>Machine name</label>
        <input name="name"
               placeholder="DATA4MINES Example"
               required>

        <label>Series</label>
        <input name="series"
               placeholder="M7"
               required>

        <label>Image filename</label>
        <input name="image"
               placeholder="m7.jpg">

        <label>Purchase amount</label>
        <input type="number"
               name="purchase_amount"
               required>

        <label>Total withdrawal</label>
        <input type="number"
               name="withdrawal_amount"
               required>

        <label>Days</label>
        <input type="number"
               name="days"
               required>

        <label>Stock</label>
        <input type="number"
               name="stock"
               value="100"
               required>

        <button class="btn">
        Add Machine
        </button>

        </form>

        <hr>

        <table>

        <tr>
        <th>Machine</th>
        <th>Purchase</th>
        <th>Withdrawal</th>
        <th>Stock</th>
        <th>Status</th>
        <th>Action</th>
        </tr>

        {% for m in machines %}

        <tr>

        <td>
        {{ m["name"] }}<br>
        {{ m["series"] }}
        </td>

        <td>{{ "{:,}".format(m["purchase_amount"]) }}</td>

        <td>{{ "{:,}".format(m["withdrawal_amount"]) }}</td>

        <td>{{ m["stock"] }}</td>

        <td>
        {% if m["active"] %}
        <span class="success">Active</span>
        {% else %}
        <span class="danger">Hidden</span>
        {% endif %}
        </td>

        <td>

        <form method="post"
              action="{{ url_for(
                  'toggle_machine',
                  machine_id=m['id']
              ) }}">

        <button class="btn btn-secondary">
        Toggle
        </button>

        </form>

        </td>

        </tr>

        {% endfor %}

        </table>

        </div>


        <div class="card">

        <h2>💳 Deposit Numbers</h2>

        <form method="post"
              action="{{ url_for('add_payment_number') }}">

        <label>Phone number</label>
        <input name="number" required>

        <label>Account name</label>
        <input name="names" required>

        <button class="btn">
        Add Deposit Number
        </button>

        </form>

        </div>


        <div class="card">

        <h2>🔔 Send Notification</h2>

        <form method="post"
              action="{{ url_for('add_notification') }}">

        <label>Title</label>
        <input name="title" required>

        <label>Message</label>
        <textarea name="message" required></textarea>

        <button class="btn">
        Publish Notification
        </button>

        </form>

        </div>


        <div class="card">

        <h2>💬 User Messages</h2>

        <a class="btn"
           href="{{ url_for('admin_chat') }}">
           Open Admin Chat
        </a>

        </div>


        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

        <script>

        fetch("{{ url_for('admin_chart_data') }}")
        .then(response => response.json())
        .then(data => {

            new Chart(
                document.getElementById("flowChart"),
                {
                    type: "line",
                    data: {
                        labels: data.labels,
                        datasets: [
                            {
                                label: "Deposits",
                                data: data.deposits
                            },
                            {
                                label: "Withdrawals",
                                data: data.withdrawals
                            },
                            {
                                label: "Joined Users",
                                data: data.users
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: true
                    }
                }
            );

        });

        </script>
        """,
        users=users,
        deposits=deposits,
        deposit_amount=deposit_amount,
        withdrawals=withdrawals,
        withdrawal_amount=withdrawal_amount,
        pending_deposits=pending_deposits,
        pending_withdrawals=pending_withdrawals,
        machines=machines
    )


# ============================================================
# ADMIN CHART DATA
# ============================================================

@app.route("/admin/chart-data")
@admin_required
def admin_chart_data():

    db = get_db()

    labels = []
    deposits = []
    withdrawals = []
    users = []

    for days_ago in range(29, -1, -1):

        date = (
            datetime.now() -
            timedelta(days=days_ago)
        ).strftime("%Y-%m-%d")

        labels.append(date)

        d = db.execute("""
            SELECT COALESCE(SUM(amount),0) total
            FROM deposits
            WHERE status='approved'
            AND date(approved_at) = ?
        """, (date,)).fetchone()["total"]

        w = db.execute("""
            SELECT COALESCE(SUM(amount),0) total
            FROM withdrawals
            WHERE status='approved'
            AND date(approved_at) = ?
        """, (date,)).fetchone()["total"]

        u = db.execute("""
            SELECT COUNT(*) total
            FROM users
            WHERE date(created_at) = ?
        """, (date,)).fetchone()["total"]

        deposits.append(d)
        withdrawals.append(w)
        users.append(u)

    db.close()

    return jsonify({
        "labels": labels,
        "deposits": deposits,
        "withdrawals": withdrawals,
        "users": users
    })


# ============================================================
# APPROVE DEPOSIT
# ============================================================

@app.route(
    "/admin/deposit/<int:deposit_id>/approve",
    methods=["POST"]
)
@admin_required
def approve_deposit(deposit_id):

    db = get_db()

    deposit = db.execute("""
        SELECT *
        FROM deposits
        WHERE id = ? AND status = 'pending'
    """, (deposit_id,)).fetchone()

    if not deposit:
        db.close()
        flash("Deposit is no longer pending.", "error")
        return redirect(url_for("admin"))

    db.execute("""
        UPDATE deposits
        SET status = 'approved',
            approved_at = ?
        WHERE id = ?
    """, (
        now(),
        deposit_id
    ))

    db.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE id = ?
    """, (
        deposit["amount"],
        deposit["user_id"]
    ))

    db.execute("""
        INSERT INTO transactions
        (user_id, type, amount,
         description, status, created_at)
        VALUES (?, 'deposit', ?,
                'Deposit approved by administrator',
                'approved', ?)
    """, (
        deposit["user_id"],
        deposit["amount"],
        now()
    ))

    db.commit()
    db.close()

    flash("Deposit approved and balance updated.", "success")

    return redirect(url_for("admin"))


# ============================================================
# REJECT DEPOSIT
# ============================================================

@app.route(
    "/admin/deposit/<int:deposit_id>/reject",
    methods=["POST"]
)
@admin_required
def reject_deposit(deposit_id):

    db = get_db()

    db.execute("""
        UPDATE deposits
        SET status = 'rejected'
        WHERE id = ? AND status = 'pending'
    """, (deposit_id,))

    db.commit()
    db.close()

    flash("Deposit rejected.", "success")

    return redirect(url_for("admin"))


# ============================================================
# APPROVE WITHDRAWAL
# ============================================================

@app.route(
    "/admin/withdrawal/<int:withdrawal_id>/approve",
    methods=["POST"]
)
@admin_required
def approve_withdrawal(withdrawal_id):

    db = get_db()

    withdrawal = db.execute("""
        SELECT *
        FROM withdrawals
        WHERE id = ? AND status = 'pending'
    """, (withdrawal_id,)).fetchone()

    if not withdrawal:
        db.close()
        flash("Withdrawal is no longer pending.", "error")
        return redirect(url_for("admin"))

    db.execute("""
        UPDATE withdrawals
        SET status = 'approved',
            approved_at = ?
        WHERE id = ?
    """, (
        now(),
        withdrawal_id
    ))

    db.execute("""
        INSERT INTO transactions
        (user_id, type, amount,
         description, status, created_at)
        VALUES (?, 'withdrawal', ?,
                'Withdrawal approved by administrator',
                'approved', ?)
    """, (
        withdrawal["user_id"],
        withdrawal["amount"],
        now()
    ))

    db.commit()
    db.close()

    flash(
        "Withdrawal approved. The administrator can now process the manual payout.",
        "success"
    )

    return redirect(url_for("admin"))


# ============================================================
# REJECT WITHDRAWAL
# ============================================================

@app.route(
    "/admin/withdrawal/<int:withdrawal_id>/reject",
    methods=["POST"]
)
@admin_required
def reject_withdrawal(withdrawal_id):

    db = get_db()

    withdrawal = db.execute("""
        SELECT *
        FROM withdrawals
        WHERE id = ? AND status = 'pending'
    """, (withdrawal_id,)).fetchone()

    if not withdrawal:
        db.close()
        flash("Withdrawal is no longer pending.", "error")
        return redirect(url_for("admin"))

    # Return reserved funds
    db.execute("""
        UPDATE users
        SET balance = balance + ?
        WHERE id = ?
    """, (
        withdrawal["amount"],
        withdrawal["user_id"]
    ))

    db.execute("""
        UPDATE withdrawals
        SET status = 'rejected'
        WHERE id = ?
    """, (withdrawal_id,))

    db.commit()
    db.close()

    flash(
        "Withdrawal rejected and the reserved balance was returned.",
        "success"
    )

    return redirect(url_for("admin"))


# ============================================================
# ADD MACHINE
# ============================================================

@app.route("/admin/machine/add", methods=["POST"])
@admin_required
def add_machine():

    try:
        purchase = int(request.form.get(
            "purchase_amount", "0"
        ))

        withdrawal = int(request.form.get(
            "withdrawal_amount", "0"
        ))

        days = int(request.form.get(
            "days", "0"
        ))

        stock = int(request.form.get(
            "stock", "0"
        ))

    except ValueError:
        flash("Invalid machine numbers.", "error")
        return redirect(url_for("admin"))

    name = request.form.get("name", "").strip()
    series = request.form.get("series", "").strip()
    image = request.form.get("image", "").strip()

    if not name or not series:
        flash("Machine name and series are required.", "error")
        return redirect(url_for("admin"))

    db = get_db()

    db.execute("""
        INSERT INTO machines
        (name, series, image,
         purchase_amount, withdrawal_amount,
         days, stock, active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?)
    """, (
        name,
        series,
        image,
        purchase,
        withdrawal,
        days,
        stock,
        now()
    ))

    db.commit()
    db.close()

    flash("Machine added.", "success")

    return redirect(url_for("admin"))


# ============================================================
# TOGGLE MACHINE
# ============================================================

@app.route(
    "/admin/machine/<int:machine_id>/toggle",
    methods=["POST"]
)
@admin_required
def toggle_machine(machine_id):

    db = get_db()

    db.execute("""
        UPDATE machines
        SET active =
            CASE
                WHEN active = 1 THEN 0
                ELSE 1
            END
        WHERE id = ?
    """, (machine_id,))

    db.commit()
    db.close()

    flash("Machine availability updated.", "success")

    return redirect(url_for("admin"))


# ============================================================
# PAYMENT NUMBERS
# ============================================================

@app.route(
    "/admin/payment-number/add",
    methods=["POST"]
)
@admin_required
def add_payment_number():

    number = request.form.get(
        "number", ""
    ).strip()

    names = request.form.get(
        "names", ""
    ).strip()

    if not number or not names:
        flash("Number and account name are required.", "error")
        return redirect(url_for("admin"))

    db = get_db()

    try:
        db.execute("""
            INSERT INTO payment_numbers
            (number, names, active, created_at)
            VALUES (?, ?, 1, ?)
        """, (
            number,
            names,
            now()
        ))

        db.commit()

    except sqlite3.IntegrityError:
        flash("That payment number already exists.", "error")
        db.close()
        return redirect(url_for("admin"))

    db.close()

    flash("Deposit number added.", "success")

    return redirect(url_for("admin"))


# ============================================================
# NOTIFICATION ADMIN
# ============================================================

@app.route(
    "/admin/notification/add",
    methods=["POST"]
)
@admin_required
def add_notification():

    title = request.form.get(
        "title", ""
    ).strip()

    message = request.form.get(
        "message", ""
    ).strip()

    if not title or not message:
        flash("Title and message are required.", "error")
        return redirect(url_for("admin"))

    db = get_db()

    db.execute("""
        INSERT INTO notifications
        (title, message, created_at)
        VALUES (?, ?, ?)
    """, (
        title,
        message,
        now()
    ))

    db.commit()
    db.close()

    flash("Notification published.", "success")

    return redirect(url_for("admin"))


# ============================================================
# ADMIN CHAT
# ============================================================

@app.route("/admin/chat")
@admin_required
def admin_chat():

    db = get_db()

    messages = db.execute("""
        SELECT c.*, u.name, u.phone
        FROM chats c
        JOIN users u ON u.id = c.user_id
        ORDER BY c.id DESC
        LIMIT 200
    """).fetchall()

    db.close()

    return page(
        "Admin Chat",
        """
        <h1>💬 Admin Chat</h1>

        {% for message in messages %}

        <div class="card">

        <strong>
        {{ message["name"] }}
        -
        {{ message["phone"] }}
        </strong>

        <p>{{ message["message"] }}</p>

        <small class="muted">
        {{ message["created_at"] }}
        </small>

        <form method="post"
              action="{{ url_for(
                  'admin_reply',
                  user_id=message['user_id']
              ) }}">

        <input name="message"
               placeholder="Reply to user"
               required>

        <button class="btn">
        Reply
        </button>

        </form>

        </div>

        {% else %}

        <div class="card">
        No messages.
        </div>

        {% endfor %}
        """,
        messages=messages
    )


@app.route(
    "/admin/chat/<int:user_id>/reply",
    methods=["POST"]
)
@admin_required
def admin_reply(user_id):

    message = request.form.get(
        "message", ""
    ).strip()

    if not message:
        return redirect(url_for("admin_chat"))

    db = get_db()

    db.execute("""
        INSERT INTO chats
        (user_id, sender, message, created_at)
        VALUES (?, 'admin', ?, ?)
    """, (
        user_id,
        message,
        now()
    ))

    db.commit()
    db.close()

    return redirect(url_for("admin_chat"))


# ============================================================
# TRANSACTION HISTORY
# ============================================================

@app.route("/transactions")
@login_required
def transactions():

    user = current_user()

    db = get_db()

    items = db.execute("""
        SELECT *
        FROM transactions
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 100
    """, (user["id"],)).fetchall()

    db.close()

    return page(
        "Transactions",
        """
        <h1>Transaction History</h1>

        <div class="card">

        <table>

        <tr>
        <th>Type</th>
        <th>Amount</th>
        <th>Description</th>
        <th>Date</th>
        </tr>

        {% for item in items %}

        <tr>

        <td>{{ item["type"] }}</td>

        <td>
        {{ "{:,}".format(item["amount"]) }} UGX
        </td>

        <td>{{ item["description"] }}</td>

        <td>{{ item["created_at"] }}</td>

        </tr>

        {% else %}

        <tr>
        <td colspan="4">
        No transactions yet.
        </td>
        </tr>

        {% endfor %}

        </table>

        </div>
        """,
        items=items
    )


# ============================================================
# ERROR HANDLERS
# ============================================================

@app.errorhandler(404)
def not_found(error):
    return page(
        "Page Not Found",
        """
        <div class="card">

        <h1>404</h1>

        <p>
        The page you requested does not exist.
        </p>

        <a class="btn"
           href="{{ url_for('dashboard') }}">
           Return to Dashboard
        </a>

        </div>
        """
    ), 404


@app.errorhandler(500)
def server_error(error):
    return page(
        "Server Error",
        """
        <div class="card">

        <h1>Server Error</h1>

        <p>
        An internal error occurred.
        Check the terminal for the Python error.
        </p>

        <a class="btn"
           href="{{ url_for('dashboard') }}">
           Return to Dashboard
        </a>

        </div>
        """
    ), 500


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    init_db()

    print("=" * 60)
    print("DATA4MINES")
    print("=" * 60)
    print("Server: http://127.0.0.1:5000")
    print("Admin phone:", ADMIN_PHONE)
    print("Admin password:", ADMIN_PASSWORD)
    print("Database:", DB_PATH)
    print("=" * 60)

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False
    )