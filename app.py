from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
from datetime import datetime, timezone
import sqlite3
import os
import secrets
import socket
import csv
import io
from functools import wraps
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__)

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "resonate.db")
SECRET_KEY_PATH = os.path.join(os.path.dirname(__file__), "data", "secret_key.txt")


def get_or_create_secret_key():
    """Persist the Flask secret key to disk so admin/portal logins and
    flashed messages survive a dev-server restart instead of silently
    logging everyone out every time app.py restarts."""
    os.makedirs(os.path.dirname(SECRET_KEY_PATH), exist_ok=True)
    if os.path.exists(SECRET_KEY_PATH):
        with open(SECRET_KEY_PATH, "r") as f:
            key = f.read().strip()
            if key:
                return key
    key = secrets.token_hex(32)
    with open(SECRET_KEY_PATH, "w") as f:
        f.write(key)
    return key


app.secret_key = os.environ.get("SECRET_KEY") or get_or_create_secret_key()


def get_lan_ip():
    """Best-effort LAN IP for this machine, so a QR code/link generated
    while browsing on localhost still resolves from a phone on the same Wi-Fi."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return None


def phone_friendly_url(path):
    """Absolute URL to `path` that a phone can actually load. request.host
    is often 127.0.0.1 when the app is opened locally on the same computer,
    which a phone can't reach, so swap in the LAN IP in that case."""
    hostname = request.host.split(":")[0]
    absolute = request.host_url.rstrip("/") + path
    if hostname in ("127.0.0.1", "localhost", "0.0.0.0"):
        lan_ip = get_lan_ip()
        if lan_ip:
            absolute = absolute.replace(hostname, lan_ip, 1)
    return absolute

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            org TEXT,
            role TEXT,
            access_code TEXT UNIQUE,
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS intakes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            name TEXT,
            email TEXT,
            org TEXT,
            role TEXT,
            audience TEXT,
            goal TEXT,
            existing_draft TEXT,
            key_messages TEXT,
            constraints TEXT,
            tone_notes TEXT,
            status TEXT DEFAULT 'new',
            created_at TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS deliverables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intake_id INTEGER,
            title TEXT,
            content TEXT,
            notes TEXT,
            created_at TEXT,
            FOREIGN KEY (intake_id) REFERENCES intakes(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            intake_id INTEGER,
            client_id INTEGER,
            message TEXT,
            created_at TEXT,
            FOREIGN KEY (intake_id) REFERENCES intakes(id),
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS site_content (
            key TEXT PRIMARY KEY,
            label TEXT,
            page TEXT,
            value TEXT,
            updated_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            role TEXT,
            quote TEXT,
            rating INTEGER DEFAULT 5,
            visible INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            client_name TEXT,
            client_email TEXT,
            amount REAL NOT NULL,
            service TEXT,
            method TEXT,
            notes TEXT,
            paid_at TEXT,
            created_at TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            org TEXT,
            preferred_time TEXT,
            notes TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT
        )
    """)
    # Seed a demo admin client
    c.execute("SELECT id FROM clients WHERE email = ?", ("demo@resonate.coach",))
    if not c.fetchone():
        code = "DEMO2026"
        c.execute(
            "INSERT INTO clients (name, email, org, role, access_code, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("Demo Client", "demo@resonate.coach", "Youth Forward PAC", "Campaign Manager", code, datetime.now(timezone.utc).isoformat())
        )
    
    # Seed editable site content if empty
    defaults = [
        ("mission", "Mission statement", "home", "Speak so the next generation hears you."),
        ("what_we_do", "What we do (home overview)", "home", "Resonate helps public figures communicate with younger voters through clear writing, practical coaching, and messaging that feels natural when it is spoken out loud."),
        ("no_ai_note", "No AI note", "home", "No AI on client work. Every draft and coaching note is written by Shepherd."),
        ("about_intro", "About intro", "about", "Resonate exists because most political messaging aimed at younger voters is written by people a generation removed from that audience. The gap shows up in the language, the tone, and the assumptions."),
        ("about_background", "About background", "about", "I competed in speech and debate at a national level through Stoa and advanced to nationals four times. That training is about clarity, structure, and persuasion under pressure. I also bring political consulting experience through CSSA and service on Congressman Jeff Crank's staff."),
        ("about_body", "About additional text", "about", "The combination is practical. Competitive speech teaches how arguments actually land when spoken out loud. Time spent around campaigns and a congressional office teaches what constraints real political communication operates under. Resonate sits at that intersection.\n\nClient writing, coaching, and strategy are produced by hand. Resonate does not use AI to write speeches or coaching notes for clients.\n\nThe focus stays on the work: speeches and messages that feel natural to voters under thirty, without sounding forced or out of touch."),
        ("who_intro", "Who it is for intro", "who", "The work stays focused on purpose. Depth matters more than trying to serve everyone at once. Support is available to candidates and teams across the political spectrum."),
        ("who_candidates", "Candidates section", "who", "People running for office or already serving who need their words to land with voters under thirty. This includes town halls, campaign launches, short video messages, and debate preparation."),
        ("who_teams", "Campaign teams section", "who", "Managers and communications directors who know their principal needs a younger perspective in the room. Not another strategy document about youth engagement, but actual language that feels natural when spoken."),
        ("services_intro", "Services intro", "services", "Every service is delivered by Shepherd Brandt in person or by hand. Client writing, coaching, and strategy are never outsourced to AI. The goal is language that holds up when spoken out loud and feels natural to voters under thirty."),
        ("process_intro", "Process intro", "process", "Easy to explain and easy to begin."),
        ("pricing_intro", "Pricing intro", "pricing", "Straightforward pricing so you know what you are getting. Discovery calls are free. Custom scopes are available for larger campaigns."),
        ("capacity_note", "Booking page capacity note (keep honest — edit or clear as real availability changes)", "book", "Currently taking new clients. Most discovery calls are scheduled within 2 business days."),
        ("faq_intro", "FAQ intro", "faq", "Quick answers about how Resonate works."),
        ("contact_phone", "Contact phone", "about", "(719) 654-3960"),
        ("contact_email", "Contact email", "about", "shep.brandt@outlook.com"),
        ("contact_name", "Contact name", "about", "Shepherd Brandt"),
        ("reviews_enabled", "Show reviews on site (on/off)", "reviews", "on"),
        ("reviews_heading", "Reviews page heading", "reviews", "What clients say"),
        ("reviews_intro", "Reviews page intro", "reviews", "Feedback from people who have worked with Resonate on speeches, coaching, and messaging."),
        ("demo_enabled", "Show inaugural demo on home (on/off)", "demo", "on"),
        ("demo_heading", "Demo section heading", "demo", "Before and after: inaugural language"),
        ("demo_intro", "Demo section intro", "demo", "Two short passages from recent inaugural addresses, each with a Resonate-style rewrite aimed at clarity and younger listeners. Examples only. Not an endorsement of either speech."),
        ("demo_trump_1_orig", "Trump passage 1 (original)", "demo", "From this day forward, a new vision will govern our land. From this day forward, it is going to be only America first. America first."),
        ("demo_trump_1_rewrite", "Trump passage 1 (rewrite)", "demo", "Starting today, the standard is simple: every decision has to put American workers and families first. Not as a slogan. As the test for what we do next."),
        ("demo_trump_2_orig", "Trump passage 2 (original)", "demo", "We will bring back our jobs. We will bring back our borders. We will bring back our wealth. And we will bring back our dreams."),
        ("demo_trump_2_rewrite", "Trump passage 2 (rewrite)", "demo", "Jobs come home. Borders mean something again. Wealth is built here, not shipped out by default. And the people who do the work get a real shot at the future they were promised."),
        ("demo_biden_1_orig", "Biden passage 1 (original)", "demo", "We can do this if we open our souls instead of hardening our hearts. If we show a little tolerance and humility, and if we are willing to stand in the other person's shoes."),
        ("demo_biden_1_rewrite", "Biden passage 1 (rewrite)", "demo", "We get through this when we stop treating disagreement like an enemy attack. Listen longer than is comfortable. Assume the person across from you is still part of the same country."),
        ("demo_biden_2_orig", "Biden passage 2 (original)", "demo", "We must end this uncivil war that pits red against blue, rural versus urban, conservative versus liberal. We can do this if we open our souls instead of hardening our hearts."),
        ("demo_biden_2_rewrite", "Biden passage 2 (rewrite)", "demo", "The split between red and blue, city and town, left and right is eating the country from the inside. Ending it starts with words that do not treat half the map as disposable."),
    ]
    now = datetime.now(timezone.utc).isoformat()
    for key, label, page, value in defaults:
        exists = c.execute("SELECT 1 FROM site_content WHERE key = ?", (key,)).fetchone()
        if not exists:
            c.execute(
                "INSERT INTO site_content (key, label, page, value, updated_at) VALUES (?, ?, ?, ?, ?)",
                (key, label, page, value, now),
            )

    # Sample reviews if empty. Seeded HIDDEN (visible=0): these are placeholder
    # copy to preview the layout, not real client testimonials. Presenting
    # fabricated quotes as genuine reviews to real site visitors is both
    # dishonest and runs into FTC endorsement rules, so they must be swapped
    # for real testimonials (or left hidden) before this goes live for real.
    rev_count = c.execute("SELECT COUNT(*) as n FROM reviews").fetchone()
    n = rev_count["n"] if rev_count else 0
    if n == 0:
        samples = [
            ("Alex M. (SAMPLE — replace before launch)", "Campaign manager", "Shepherd tightened our town hall opening so it sounded like us, not a consultant. Younger volunteers actually used the lines.", 5),
            ("Jordan K. (SAMPLE — replace before launch)", "Candidate", "The coaching notes were specific and usable the same day. No fluff.", 5),
            ("Sam R. (SAMPLE — replace before launch)", "Comms director", "We needed short form scripts that did not feel cringe. The set we got is still in rotation.", 5),
        ]
        for name, role, quote, rating in samples:
            c.execute(
                "INSERT INTO reviews (name, role, quote, rating, visible, created_at) VALUES (?, ?, ?, ?, 0, ?)",
                (name, role, quote, rating, now),
            )

    conn.commit()
    conn.close()


def get_content(key, default=""):
    """Fetch editable site content by key."""
    try:
        conn = get_db()
        row = conn.execute("SELECT value FROM site_content WHERE key = ?", (key,)).fetchone()
        conn.close()
        if row and row["value"] is not None:
            return row["value"]
    except Exception:
        pass
    return default

def get_all_content():
    conn = get_db()
    rows = conn.execute("SELECT * FROM site_content ORDER BY page, label").fetchall()
    conn.close()
    return rows

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "client_id" not in session:
            flash("Please log in with your access code.", "error")
            return redirect(url_for("portal_login"))
        return f(*args, **kwargs)
    return decorated

@app.route("/")
def index():
    reviews_on = get_content("reviews_enabled", "on").strip().lower() in ("on", "true", "1", "yes")
    demo_on = get_content("demo_enabled", "on").strip().lower() in ("on", "true", "1", "yes")
    return render_template(
        "index.html",
        mission=get_content("mission", "Speak so the next generation hears you."),
        what_we_do=get_content("what_we_do", "Resonate helps public figures communicate with younger voters through clear writing, practical coaching, and messaging that feels natural when it is spoken out loud."),
        no_ai_note=get_content("no_ai_note", "No AI on client work. Every draft and coaching note is written by Shepherd."),
        reviews_enabled=reviews_on,
        demo_enabled=demo_on,
        demo_heading=get_content("demo_heading", "Before and after: inaugural language"),
        demo_intro=get_content("demo_intro", ""),
        trump_1_orig=get_content("demo_trump_1_orig", ""),
        trump_1_rewrite=get_content("demo_trump_1_rewrite", ""),
        trump_2_orig=get_content("demo_trump_2_orig", ""),
        trump_2_rewrite=get_content("demo_trump_2_rewrite", ""),
        biden_1_orig=get_content("demo_biden_1_orig", ""),
        biden_1_rewrite=get_content("demo_biden_1_rewrite", ""),
        biden_2_orig=get_content("demo_biden_2_orig", ""),
        biden_2_rewrite=get_content("demo_biden_2_rewrite", ""),
    )

@app.route("/book", methods=["GET", "POST"])
def book():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        org = request.form.get("org", "").strip()
        preferred_time = request.form.get("preferred_time", "").strip()
        notes = request.form.get("notes", "").strip()
        if not name or not email:
            flash("Name and email are required.", "error")
            return redirect(url_for("book"))
        conn = get_db()
        conn.execute(
            "INSERT INTO bookings (name, email, org, preferred_time, notes, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (name, email, org, preferred_time, notes, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()
        flash("Discovery call request received. We'll reply within 24 hours.", "success")
        return redirect(url_for("book"))
    return render_template("book.html", capacity_note=get_content("capacity_note", ""))

@app.route("/intake", methods=["GET", "POST"])
def intake():
    if request.method == "POST":
        data = {
            "name": request.form.get("name", "").strip(),
            "email": request.form.get("email", "").strip(),
            "org": request.form.get("org", "").strip(),
            "role": request.form.get("role", "").strip(),
            "audience": request.form.get("audience", "").strip(),
            "goal": request.form.get("goal", "").strip(),
            "existing_draft": request.form.get("existing_draft", "").strip(),
            "key_messages": request.form.get("key_messages", "").strip(),
            "constraints": request.form.get("constraints", "").strip(),
            "tone_notes": request.form.get("tone_notes", "").strip(),
        }
        if not data["name"] or not data["email"] or not data["goal"]:
            flash("Name, email, and primary goal are required.", "error")
            return redirect(url_for("intake"))
        conn = get_db()
        # Create or get client
        cur = conn.execute("SELECT id, access_code FROM clients WHERE email = ?", (data["email"],))
        row = cur.fetchone()
        if row:
            client_id = row["id"]
            access_code = row["access_code"]
        else:
            access_code = secrets.token_urlsafe(8).upper()[:8]
            cur = conn.execute(
                "INSERT INTO clients (name, email, org, role, access_code, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (data["name"], data["email"], data["org"], data["role"], access_code, datetime.now(timezone.utc).isoformat())
            )
            client_id = cur.lastrowid
        conn.execute(
            """INSERT INTO intakes 
               (client_id, name, email, org, role, audience, goal, existing_draft, key_messages, constraints, tone_notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (client_id, data["name"], data["email"], data["org"], data["role"],
             data["audience"], data["goal"], data["existing_draft"], data["key_messages"],
             data["constraints"], data["tone_notes"], datetime.now(timezone.utc).isoformat())
        )
        conn.commit()
        conn.close()
        flash(f"Intake submitted. Your portal access code is: {access_code}. Save it.", "success")
        return redirect(url_for("portal_login"))
    return render_template("intake.html")

@app.route("/portal/login", methods=["GET", "POST"])
def portal_login():
    if request.method == "POST":
        code = request.form.get("access_code", "").strip().upper()
        conn = get_db()
        cur = conn.execute("SELECT id, name, email FROM clients WHERE access_code = ?", (code,))
        client = cur.fetchone()
        conn.close()
        if client:
            session["client_id"] = client["id"]
            session["client_name"] = client["name"]
            session["client_email"] = client["email"]
            return redirect(url_for("portal"))
        flash("Invalid access code.", "error")
    return render_template("portal_login.html")

@app.route("/portal")
@login_required
def portal():
    client_id = session["client_id"]
    conn = get_db()
    intakes = conn.execute(
        "SELECT * FROM intakes WHERE client_id = ? ORDER BY created_at DESC", (client_id,)
    ).fetchall()
    deliverables = {}
    for i in intakes:
        dels = conn.execute(
            "SELECT * FROM deliverables WHERE intake_id = ? ORDER BY created_at DESC", (i["id"],)
        ).fetchall()
        deliverables[i["id"]] = dels
    conn.close()
    return render_template("portal.html", intakes=intakes, deliverables=deliverables)


@app.route("/portal/feedback/<int:intake_id>", methods=["POST"])
@login_required
def portal_feedback(intake_id):
    client_id = session["client_id"]
    message = request.form.get("message", "").strip()
    if not message:
        flash("Please enter feedback.", "error")
        return redirect(url_for("portal"))
    conn = get_db()
    # verify intake belongs to client
    row = conn.execute("SELECT id FROM intakes WHERE id = ? AND client_id = ?", (intake_id, client_id)).fetchone()
    if not row:
        conn.close()
        flash("Invalid request.", "error")
        return redirect(url_for("portal"))
    conn.execute(
        "INSERT INTO feedback (intake_id, client_id, message, created_at) VALUES (?, ?, ?, ?)",
        (intake_id, client_id, message, datetime.now(timezone.utc).isoformat())
    )
    conn.commit()
    conn.close()
    flash("Feedback submitted. Thank you.", "success")
    return redirect(url_for("portal"))

@app.route("/portal/logout")
def portal_logout():
    session.clear()
    return redirect(url_for("index"))



@app.route("/pricing")
def pricing():
    return render_template("pricing.html", pricing_intro=get_content("pricing_intro", "Straightforward pricing so you know what you are getting. Discovery calls are free."))

@app.route("/pay")
def pay():
    return render_template("pay.html")

@app.route("/faq")
def faq():
    return render_template("faq.html", faq_intro=get_content("faq_intro", "Quick answers about how Resonate works."))

@app.route("/contact")
def contact():
    return redirect(url_for("about"))

@app.route("/about")
def about():
    return render_template(
        "about.html",
        about_intro=get_content("about_intro", ""),
        about_background=get_content("about_background", ""),
        about_body=get_content("about_body", ""),
        contact_name=get_content("contact_name", "Shepherd Brandt"),
        contact_phone=get_content("contact_phone", "(719) 654-3960"),
        contact_email=get_content("contact_email", "shep.brandt@outlook.com"),
    )

@app.route("/who")
def who():
    return render_template(
        "who.html",
        who_intro=get_content("who_intro", ""),
        who_candidates=get_content("who_candidates", ""),
        who_teams=get_content("who_teams", ""),
    )

@app.route("/product")
def product():
    return render_template("product.html", services_intro=get_content("services_intro", ""))

@app.route("/process")
def process():
    return render_template("process.html", process_intro=get_content("process_intro", "Easy to explain and easy to begin."))

# Set ADMIN_PASSWORD in the environment to override the "resonate2026" default
# (important once this is deployed somewhere public — see README). Use `or`,
# not .get()'s default arg: Render stores an env var you left blank as an
# empty string rather than leaving it unset, and .get(key, default) only
# falls back when the key is entirely absent — an empty string would
# otherwise silently become the real password and lock everyone out.
ADMIN_PASSWORD_HASH = generate_password_hash(os.environ.get("ADMIN_PASSWORD") or "resonate2026")

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin"):
            flash("Please log in as admin.", "error")
            return redirect(url_for("admin_login"))
        return f(*args, **kwargs)
    return decorated

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if session.get("admin"):
        return redirect(url_for("admin"))
    if request.method == "POST":
        password = request.form.get("password", "")
        if check_password_hash(ADMIN_PASSWORD_HASH, password):
            session["admin"] = True
            session.permanent = True
            flash("Welcome back.", "success")
            return redirect(url_for("admin"))
        flash("Invalid password.", "error")
    return render_template("admin_login.html")

@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin():
    conn = get_db()
    intakes = conn.execute("SELECT * FROM intakes ORDER BY created_at DESC").fetchall()
    bookings = conn.execute("SELECT * FROM bookings ORDER BY created_at DESC").fetchall()
    clients = conn.execute("SELECT * FROM clients ORDER BY created_at DESC").fetchall()
    try:
        feedback = conn.execute(
            "SELECT f.*, i.goal, i.name as client_name FROM feedback f LEFT JOIN intakes i ON f.intake_id = i.id ORDER BY f.created_at DESC"
        ).fetchall()
    except Exception:
        feedback = []
    conn.close()
    return render_template(
        "admin.html",
        intakes=intakes,
        bookings=bookings,
        clients=clients,
        feedback=feedback,
        phone_target_url=phone_friendly_url(url_for("index")),
    )


@app.route("/admin/edit", methods=["GET", "POST"])
@admin_required
def admin_edit():
    if request.method == "POST":
        conn = get_db()
        for key in request.form:
            if key.startswith("content_"):
                content_key = key[len("content_"):]
                value = request.form.get(key, "")
                conn.execute(
                    "UPDATE site_content SET value = ?, updated_at = ? WHERE key = ?",
                    (value, datetime.now(timezone.utc).isoformat(), content_key),
                )
        conn.commit()
        conn.close()
        flash("Website content saved.", "success")
        return redirect(url_for("admin_edit"))
    rows = get_all_content()
    by_page = {}
    for r in rows:
        by_page.setdefault(r["page"], []).append(r)
    return render_template("admin_edit.html", by_page=by_page)

@app.route("/admin/edit/add", methods=["POST"])
@admin_required
def admin_edit_add():
    key = request.form.get("key", "").strip().replace(" ", "_").lower()
    label = request.form.get("label", "").strip()
    page = request.form.get("page", "general").strip()
    value = request.form.get("value", "")
    if not key or not label:
        flash("Key and label are required.", "error")
        return redirect(url_for("admin_edit"))
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO site_content (key, label, page, value, updated_at) VALUES (?, ?, ?, ?, ?)",
            (key, label, page, value, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
        flash("Field added.", "success")
    except Exception:
        flash("Could not add field (key may already exist).", "error")
    conn.close()
    return redirect(url_for("admin_edit"))



@app.route("/admin/finance", methods=["GET", "POST"])
@admin_required
def admin_finance():
    conn = get_db()
    if request.method == "POST":
        amount = request.form.get("amount", "0").replace(",", "").strip()
        try:
            amount_f = float(amount)
        except ValueError:
            amount_f = 0.0
        conn.execute(
            """INSERT INTO payments (client_id, client_name, client_email, amount, service, method, notes, paid_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                request.form.get("client_id") or None,
                request.form.get("client_name", "").strip(),
                request.form.get("client_email", "").strip(),
                amount_f,
                request.form.get("service", "").strip(),
                request.form.get("method", "").strip(),
                request.form.get("notes", "").strip(),
                request.form.get("paid_at") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        flash("Payment recorded.", "success")
        conn.close()
        return redirect(url_for("admin_finance"))

    payments = conn.execute("SELECT * FROM payments ORDER BY paid_at DESC, id DESC").fetchall()
    clients = conn.execute("SELECT * FROM clients ORDER BY name").fetchall()

    # Aggregate by client
    client_totals = conn.execute(
        """SELECT COALESCE(client_name, 'Unknown') as name,
                  COALESCE(client_email, '') as email,
                  COUNT(*) as payment_count,
                  SUM(amount) as total
           FROM payments
           GROUP BY lower(COALESCE(client_email, client_name))
           ORDER BY total DESC"""
    ).fetchall()

    # Aggregate by service
    service_totals = conn.execute(
        """SELECT COALESCE(service, 'Unspecified') as service,
                  COUNT(*) as count,
                  SUM(amount) as total
           FROM payments
           GROUP BY service
           ORDER BY total DESC"""
    ).fetchall()

    # Aggregate by method
    method_totals = conn.execute(
        """SELECT COALESCE(method, 'Unspecified') as method,
                  COUNT(*) as count,
                  SUM(amount) as total
           FROM payments
           GROUP BY method
           ORDER BY total DESC"""
    ).fetchall()

    total_revenue = conn.execute("SELECT COALESCE(SUM(amount), 0) as s FROM payments").fetchone()["s"]
    payment_count = conn.execute("SELECT COUNT(*) as c FROM payments").fetchone()["c"]
    avg_payment = (total_revenue / payment_count) if payment_count else 0

    # Monthly series for simple trend
    monthly = conn.execute(
        """SELECT substr(paid_at, 1, 7) as month, SUM(amount) as total, COUNT(*) as count
           FROM payments
           WHERE paid_at IS NOT NULL AND length(paid_at) >= 7
           GROUP BY month
           ORDER BY month"""
    ).fetchall()
    conn.close()

    return render_template(
        "admin_finance.html",
        payments=payments,
        clients=clients,
        client_totals=client_totals,
        service_totals=service_totals,
        method_totals=method_totals,
        total_revenue=total_revenue,
        payment_count=payment_count,
        avg_payment=avg_payment,
        monthly=monthly,
    )


@app.route("/admin/finance/delete/<int:payment_id>", methods=["POST"])
@admin_required
def admin_finance_delete(payment_id):
    conn = get_db()
    conn.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
    conn.commit()
    conn.close()
    flash("Payment removed.", "success")
    return redirect(url_for("admin_finance"))


@app.route("/admin/insights")
@admin_required
def admin_insights():
    """Backend analysis: trends, predictions, what is working, what to fix."""
    conn = get_db()
    payments = conn.execute("SELECT * FROM payments ORDER BY paid_at").fetchall()
    service_totals = conn.execute(
        """SELECT COALESCE(service, 'Unspecified') as service,
                  COUNT(*) as count, SUM(amount) as total, AVG(amount) as avg
           FROM payments GROUP BY service ORDER BY total DESC"""
    ).fetchall()
    client_totals = conn.execute(
        """SELECT COALESCE(client_name, 'Unknown') as name,
                  COUNT(*) as payment_count, SUM(amount) as total
           FROM payments GROUP BY lower(COALESCE(client_email, client_name))
           ORDER BY total DESC"""
    ).fetchall()
    monthly = conn.execute(
        """SELECT substr(paid_at, 1, 7) as month, SUM(amount) as total, COUNT(*) as count
           FROM payments WHERE paid_at IS NOT NULL AND length(paid_at) >= 7
           GROUP BY month ORDER BY month"""
    ).fetchall()
    intake_count = conn.execute("SELECT COUNT(*) as c FROM intakes").fetchone()["c"]
    booking_count = conn.execute("SELECT COUNT(*) as c FROM bookings").fetchone()["c"]
    client_count = conn.execute("SELECT COUNT(*) as c FROM clients").fetchone()["c"]
    total_revenue = conn.execute("SELECT COALESCE(SUM(amount), 0) as s FROM payments").fetchone()["s"]
    conn.close()

    insights = []
    working = []
    fixes = []
    predictions = []

    if not payments:
        insights.append("No payments recorded yet. Log your first payment on the Finance page so analysis has data to work with.")
        fixes.append("After each paid project, add amount, service type, and client name. Consistent logging is the foundation of useful forecasts.")
        predictions.append("Once you have 3 or more months of payments, month-over-month trend and next-month estimates will appear here.")
    else:
        # Top service
        if service_totals:
            top = service_totals[0]
            working.append(
                f"Most profitable service line: {top['service']} (${top['total']:.0f} total across {top['count']} payments, avg ${top['avg']:.0f}). Lean marketing and discovery-call pitches toward this offer."
            )
            if len(service_totals) > 1:
                weak = service_totals[-1]
                if weak["total"] < top["total"] * 0.35:
                    fixes.append(
                        f"{weak['service']} is lagging (${weak['total']:.0f} total). Either raise its visibility in discovery calls, bundle it with your top offer, or simplify the package so it is easier to buy."
                    )

        # Top clients
        if client_totals:
            top_c = client_totals[0]
            working.append(
                f"Highest contributing client: {top_c['name']} (${top_c['total']:.0f} across {top_c['payment_count']} payments). Protect that relationship and ask for referrals while results are fresh."
            )
            if len(client_totals) >= 3:
                working.append(
                    f"You have {len(client_totals)} paying client records. Repeat business and multi-payment clients are a signal to push monthly retainers."
                )

        # Conversion-ish signals
        if intake_count and total_revenue:
            insights.append(
                f"Pipeline snapshot: {client_count} clients, {intake_count} intakes, {booking_count} booking requests, ${total_revenue:.0f} recorded revenue."
            )
        if intake_count > (len(client_totals) or 1) * 2:
            fixes.append(
                "Intakes outpace paying clients. Follow up faster after intake, and make the path from portal delivery to payment explicit on the Pay page and in your closing email."
            )

        # Monthly trend + naive forecast
        months = [m["month"] for m in monthly]
        totals = [float(m["total"]) for m in monthly]
        if len(totals) >= 2:
            recent = totals[-1]
            prev = totals[-2]
            delta = recent - prev
            pct = (delta / prev * 100) if prev else 0
            if delta > 0:
                working.append(
                    f"Revenue is up month over month: {months[-2]} ${prev:.0f} → {months[-1]} ${recent:.0f} ({pct:+.0f}%). Keep doing whatever drove the last month’s wins."
                )
            elif delta < 0:
                fixes.append(
                    f"Revenue dipped: {months[-2]} ${prev:.0f} → {months[-1]} ${recent:.0f} ({pct:.0f}%). Check whether discovery calls, delivery speed, or follow-up slowed down."
                )
            # Simple moving average prediction
            window = totals[-3:] if len(totals) >= 3 else totals
            forecast = sum(window) / len(window)
            predictions.append(
                f"Next-month estimate (simple average of last {len(window)} months): about ${forecast:.0f}. Treat this as a planning floor, not a guarantee."
            )
            if len(totals) >= 3:
                # linear slope on last points
                n = len(window)
                xs = list(range(n))
                xbar = sum(xs) / n
                ybar = sum(window) / n
                num = sum((xs[i] - xbar) * (window[i] - ybar) for i in range(n))
                den = sum((xs[i] - xbar) ** 2 for i in range(n)) or 1
                slope = num / den
                linear_next = window[-1] + slope
                predictions.append(
                    f"Trend-adjusted outlook: about ${max(0, linear_next):.0f} if the recent slope continues."
                )
        elif len(totals) == 1:
            predictions.append(
                f"Only one month of data (${totals[0]:.0f}). Log two more months to unlock trend and forecast lines."
            )

        # Concentration risk
        if client_totals and total_revenue:
            top_share = float(client_totals[0]["total"]) / float(total_revenue) * 100
            if top_share > 50:
                fixes.append(
                    f"Your top client is about {top_share:.0f}% of revenue. That is strong loyalty and also concentration risk. Add one new paying relationship this month so income is not tied to a single account."
                )

        # Retainer suggestion
        svc_names = " ".join((s["service"] or "").lower() for s in service_totals)
        if "retainer" not in svc_names and "monthly" not in svc_names and total_revenue > 500:
            fixes.append(
                "No monthly or retainer packages show up in payment labels yet. If clients return for one-off speeches, offer the $900/month plan explicitly at delivery time."
            )
        elif "monthly" in svc_names or "retainer" in svc_names:
            working.append(
                "Recurring-style services appear in your payment log. That is the healthiest path to predictable income. Push annual prepay when a monthly client is happy."
            )

    if not working and payments:
        working.append("Keep logging every payment with a clear service label. Pattern detection improves as categories stay consistent.")
    if not fixes and payments:
        fixes.append("No major red flags from current totals. Focus on increasing discovery-call volume and converting intakes to paid packages.")
    if not predictions and payments:
        predictions.append("Add paid_at dates on every payment so monthly forecasting can run.")

    return render_template(
        "admin_insights.html",
        insights=insights,
        working=working,
        fixes=fixes,
        predictions=predictions,
        total_revenue=total_revenue,
        service_totals=service_totals,
        client_totals=client_totals,
        monthly=monthly,
    )




@app.route("/demo")
def demo_page():
    enabled = get_content("demo_enabled", "on").strip().lower() in ("on", "true", "1", "yes")
    if not enabled:
        flash("The demo is not available right now.", "error")
        return redirect(url_for("index"))
    return render_template(
        "demo.html",
        demo_heading=get_content("demo_heading", "Before and after"),
        demo_intro=get_content("demo_intro", ""),
        trump_1_orig=get_content("demo_trump_1_orig", ""),
        trump_1_rewrite=get_content("demo_trump_1_rewrite", ""),
        trump_2_orig=get_content("demo_trump_2_orig", ""),
        trump_2_rewrite=get_content("demo_trump_2_rewrite", ""),
        biden_1_orig=get_content("demo_biden_1_orig", ""),
        biden_1_rewrite=get_content("demo_biden_1_rewrite", ""),
        biden_2_orig=get_content("demo_biden_2_orig", ""),
        biden_2_rewrite=get_content("demo_biden_2_rewrite", ""),
        phone_target_url=phone_friendly_url(url_for("demo_page")),
    )

@app.route("/reviews")
def reviews():
    enabled = get_content("reviews_enabled", "on").strip().lower() in ("on", "true", "1", "yes")
    if not enabled:
        flash("Reviews are not available right now.", "error")
        return redirect(url_for("index"))
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM reviews WHERE visible = 1 ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return render_template(
        "reviews.html",
        reviews=rows,
        reviews_heading=get_content("reviews_heading", "What clients say"),
        reviews_intro=get_content("reviews_intro", ""),
    )

@app.route("/admin/reviews", methods=["GET", "POST"])
@admin_required
def admin_reviews():
    conn = get_db()
    if request.method == "POST":
        action = request.form.get("action", "add")
        if action == "toggle_site":
            val = request.form.get("reviews_enabled", "off")
            now = datetime.now(timezone.utc).isoformat()
            exists = conn.execute("SELECT 1 FROM site_content WHERE key = ?", ("reviews_enabled",)).fetchone()
            if exists:
                conn.execute("UPDATE site_content SET value = ?, updated_at = ? WHERE key = ?", (val, now, "reviews_enabled"))
            else:
                conn.execute(
                    "INSERT INTO site_content (key, label, page, value, updated_at) VALUES (?, ?, ?, ?, ?)",
                    ("reviews_enabled", "Show reviews on site (on/off)", "reviews", val, now),
                )
            conn.commit()
            flash("Reviews visibility updated.", "success")
        elif action == "add":
            try:
                rating = int(request.form.get("rating") or 5)
            except ValueError:
                rating = 5
            conn.execute(
                "INSERT INTO reviews (name, role, quote, rating, visible, created_at) VALUES (?, ?, ?, ?, 1, ?)",
                (
                    request.form.get("name", "").strip(),
                    request.form.get("role", "").strip(),
                    request.form.get("quote", "").strip(),
                    rating,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()
            flash("Review added.", "success")
        elif action == "toggle_review":
            rid = request.form.get("review_id")
            conn.execute("UPDATE reviews SET visible = 1 - visible WHERE id = ?", (rid,))
            conn.commit()
            flash("Review visibility toggled.", "success")
        elif action == "delete":
            conn.execute("DELETE FROM reviews WHERE id = ?", (request.form.get("review_id"),))
            conn.commit()
            flash("Review deleted.", "success")
        conn.close()
        return redirect(url_for("admin_reviews"))

    rows = conn.execute("SELECT * FROM reviews ORDER BY id DESC").fetchall()
    conn.close()
    enabled = get_content("reviews_enabled", "on").strip().lower() in ("on", "true", "1", "yes")
    return render_template("admin_reviews.html", reviews=rows, reviews_enabled=enabled)



@app.route("/admin/demo", methods=["GET", "POST"])
@admin_required
def admin_demo():
    keys = [
        "demo_enabled", "demo_heading", "demo_intro",
        "demo_trump_1_orig", "demo_trump_1_rewrite", "demo_trump_2_orig", "demo_trump_2_rewrite",
        "demo_biden_1_orig", "demo_biden_1_rewrite", "demo_biden_2_orig", "demo_biden_2_rewrite",
    ]
    if request.method == "POST":
        conn = get_db()
        now = datetime.now(timezone.utc).isoformat()
        for key in keys:
            if key in request.form:
                val = request.form.get(key, "")
                exists = conn.execute("SELECT 1 FROM site_content WHERE key = ?", (key,)).fetchone()
                if exists:
                    conn.execute("UPDATE site_content SET value = ?, updated_at = ? WHERE key = ?", (val, now, key))
                else:
                    conn.execute(
                        "INSERT INTO site_content (key, label, page, value, updated_at) VALUES (?, ?, ?, ?, ?)",
                        (key, key, "demo", val, now),
                    )
        conn.commit()
        conn.close()
        flash("Demo content saved.", "success")
        return redirect(url_for("admin_demo"))
    data = {k: get_content(k, "") for k in keys}
    if not data.get("demo_enabled"):
        data["demo_enabled"] = "on"
    return render_template("admin_demo.html", data=data)


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    flash("Logged out.", "success")
    return redirect(url_for("admin_login"))

@app.route("/admin/update_status/<int:intake_id>", methods=["POST"])
@admin_required
def update_status(intake_id):
    status = request.form.get("status")
    conn = get_db()
    conn.execute("UPDATE intakes SET status = ? WHERE id = ?", (status, intake_id))
    conn.commit()
    conn.close()
    flash("Status updated.", "success")
    return redirect(url_for("admin"))


@app.route("/admin/update_booking_status/<int:booking_id>", methods=["POST"])
@admin_required
def update_booking_status(booking_id):
    status = request.form.get("status")
    conn = get_db()
    conn.execute("UPDATE bookings SET status = ? WHERE id = ?", (status, booking_id))
    conn.commit()
    conn.close()
    flash("Booking status updated.", "success")
    return redirect(url_for("admin"))


EXPORTABLE_TABLES = ("bookings", "intakes", "clients", "payments", "reviews")


@app.route("/admin/export/<table>")
@admin_required
def admin_export(table):
    """Download a table as CSV. Exists mainly so leads/clients/payments can
    be backed up before a redeploy on ephemeral hosting (e.g. Render's free
    tier) wipes the SQLite file back to the seeded demo data."""
    if table not in EXPORTABLE_TABLES:
        flash("Unknown export.", "error")
        return redirect(url_for("admin"))
    conn = get_db()
    rows = conn.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()
    conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    if rows:
        writer.writerow(rows[0].keys())
        writer.writerows(rows)
    else:
        writer.writerow(["(no rows)"])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={table}.csv"},
    )

@app.route("/admin/add_deliverable/<int:intake_id>", methods=["POST"])
@admin_required
def add_deliverable(intake_id):
    title = request.form.get("title", "").strip()
    content = request.form.get("content", "").strip()
    notes = request.form.get("notes", "").strip()
    if title and content:
        conn = get_db()
        conn.execute(
            "INSERT INTO deliverables (intake_id, title, content, notes, created_at) VALUES (?, ?, ?, ?, ?)",
            (intake_id, title, content, notes, datetime.now(timezone.utc).isoformat())
        )
        conn.execute("UPDATE intakes SET status = ? WHERE id = ?", ("delivered", intake_id))
        conn.commit()
        conn.close()
        flash("Deliverable added.", "success")
    return redirect(url_for("admin"))

os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
