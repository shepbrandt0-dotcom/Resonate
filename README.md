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

## Deploy to Render (shareable domain)

The repo includes `render.yaml`, so Render can set the whole thing up from a
Blueprint:

1. Push this repo to GitHub (already done if you're reading this from there).
2. Go to [render.com](https://render.com) → New → **Blueprint** → connect the
   `Resonate` repo and branch.
3. Render reads `render.yaml` and provisions a free web service automatically.
   It will prompt you to set `ADMIN_PASSWORD` (kept private, not stored in
   the repo) — pick something other than the default before it's public.
4. Deploy. You'll get a URL like `https://resonate.onrender.com` — share that,
   or open it on your phone directly, or open `/demo` or `/admin` there and
   use the in-page QR code to hand it to someone else's phone.

**Know before you rely on it:** Render's free tier uses ephemeral disk, so
the SQLite database (`data/resonate.db`) resets to the seeded demo data
whenever the service redeploys or spins down from inactivity and back up.
Fine for showing off the site; don't collect real client intakes on the free
tier without adding a persistent disk (paid plan) or an external database.

## Other next steps

1. Add real email (Resend/Postmark) for access codes — include an unsubscribe
   link on any marketing email (not required for one-off transactional
   emails like access codes), per the commitment in the Privacy Policy.
2. Add Stripe for paid packages
3. Move to a persistent database (Postgres) once this isn't just a demo
4. Fill in `legal_business_name` and `legal_business_address` in Edit Website
   (under the "legal" section) — they show up on /privacy and /terms
5. Have a lawyer review /privacy, /terms, and /cookies before relying on
   them — they're a solid starting point, not legal advice, especially the
   refund and governing-law sections in Terms

Built to match the core idea: authentic, sharp, zero corporate-cringe.
