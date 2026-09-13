# Resonate

**Speeches that actually land with young voters.**

Full MVP web app for a Gen Z speech writing, coaching, and messaging service aimed at politicians, candidates, and campaign teams.

---

## Run it in 30 seconds

```bash
# 1. Unzip
unzip resonate-app.zip
cd resonate

# 2. Start (creates venv + installs Flask automatically)
chmod +x start.sh
./start.sh
```

Then open **http://127.0.0.1:5000**

### Manual alternative
```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install flask
python app.py
```

---

## Demo credentials

| Area              | Credential               |
|-------------------|--------------------------|
| Client portal     | Access code `DEMO2026`   |
| Admin dashboard   | Password `resonate2026`  |

The demo portal already has a sample campus-tour launch speech + strategy notes so you can see the full flow.

---

## What’s inside

- **Landing page** — clear positioning, differentiator, product stack, 3-step process
- **Discovery call booking** form
- **Client intake** form (generates unique portal access code)
- **Client portal** — view status + delivered speeches/notes
- **Admin dashboard** — manage bookings, update status, upload deliverables

Tech: Flask + SQLite + Tailwind (CDN). No external services required for the MVP.

---

## Project structure

```
resonate/
├── app.py              # Backend + routes
├── start.sh            # One-command launcher
├── requirements.txt
├── data/resonate.db    # Pre-seeded demo database
└── templates/          # All pages
```

---

## Next steps

1. Change the admin password and secret key in `app.py`
2. Add real email (Resend/Postmark) for access codes
3. Add Stripe for paid packages
4. Deploy to Railway / Render / Fly.io

Built to match the core idea: authentic, sharp, zero corporate-cringe.
