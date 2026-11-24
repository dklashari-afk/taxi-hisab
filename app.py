import os, datetime as dt
from functools import wraps
from flask import Flask, request, session, redirect, render_template, jsonify, send_from_directory, flash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.pool import NullPool
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, instance_path='/tmp/instance')
app.secret_key = os.environ.get("SECRET_KEY", "change-me")
app.permanent_session_lifetime = dt.timedelta(days=365)

# --- Database URL ---
url = os.environ.get("DATABASE_URL", "sqlite:///local.db")
url = url.replace("postgres://", "postgresql://", 1)
app.config.update(
    SQLALCHEMY_DATABASE_URI=url,
    SQLALCHEMY_ENGINE_OPTIONS={"poolclass": NullPool},
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=(os.environ.get("VERCEL") == "1"),
)
db = SQLAlchemy(app)
KIND = {"booking": "بکنگ", "fuel": "فیول", "kharcha": "خرچہ"}

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80)); phone = db.Column(db.String(20), unique=True)
    pw = db.Column(db.String(300)); role = db.Column(db.String(10))
    # driver ke liye: kis malik ka driver hai. owner ke liye None.
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

class Vehicle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id")); number = db.Column(db.String(30))
    driver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)

class Entry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    uid = db.Column(db.String(60), unique=True)
    vehicle_id = db.Column(db.Integer, db.ForeignKey("vehicle.id")); driver_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    day = db.Column(db.Date); kind = db.Column(db.String(10)); amount = db.Column(db.Integer); note = db.Column(db.String(200))

# --- DB init (Vercel serverless) ---
_db_ready = False
def _ensure_db():
    global _db_ready
    if _db_ready:
        return
    try:
        with app.app_context():
            db.create_all()
        _db_ready = True
    except Exception as ex:
        app.logger.warning("DB init failed: %s", ex)

@app.before_request
def _before():
    _ensure_db()

@app.route("/init-db")
def init_db():
    try:
        with app.app_context():
            db.create_all()
        return "OK: DB initialized"
    except Exception as ex:
        return f"ERROR: {ex}", 500

def me():
    return db.session.get(User, session["uid"]) if session.get("uid") else None

def need(role):
    def deco(f):
        @wraps(f)
        def w(*a, **k):
            u = me()
            if not u: return redirect("/login")
            if u.role != role: return redirect("/")
            return f(u, *a, **k)
        return w
    return deco

@app.route("/")
def index():
    u = me()
    return redirect("/login" if not u else "/owner" if u.role == "owner" else "/driver")

@app.route("/register", methods=["GET", "POST"])
def register():
    """Sirf malik (owner) register kar sakta hai. Driver malik banata hai."""
    if request.method == "POST":
        f = request.form; phone = f["phone"].strip()
        if User.query.filter_by(phone=phone).first():
            flash("یہ فون نمبر پہلے سے موجود ہے۔ لاگ ان کریں۔")
        else:
            u = User(name=f["name"].strip(), phone=phone,
                     pw=generate_password_hash(f["pw"]), role="owner")
            db.session.add(u); db.session.commit()
            session.permanent = True; session["uid"] = u.id
            return redirect("/owner")
    return render_template("auth.html", reg=True, u=None)

@app.route("/login", methods=["GET", "POST"])
def login():
    """Malik aur driver dono yahin se login karte hain."""
    if request.method == "POST":
        u = User.query.filter_by(phone=request.form["phone"].strip()).first()
        if u and check_password_hash(u.pw, request.form["pw"]):
            session.permanent = True; session["uid"] = u.id
            return redirect("/owner" if u.role == "owner" else "/driver")
        flash("فون نمبر یا پاسورڈ غلط ہے۔")
    return render_template("auth.html", reg=False, u=None)

@app.route("/logout")
def logout():
    session.clear(); return redirect("/login")

@app.route("/vehicle", methods=["POST"])
@need("owner")
def vehicle(u):
    """Malik gari add karta hai, saath mein driver bhi bana sakta hai."""
    number = request.form["number"].strip()
    d_name = request.form.get("driver_name", "").strip()
    d_phone = request.form.get("driver_phone", "").strip()
    d_pw = request.form.get("driver_pw", "").strip()

    driver_id = None
    if d_phone and d_pw:
        existing = User.query.filter_by(phone=d_phone).first()
        if existing:
            # agar yeh driver pehle se isi malik ka hai to wahi use karo
            if existing.role != "driver" or existing.owner_id != u.id:
                flash("یہ نمبر کسی اور اکاؤنٹ سے منسلک ہے۔")
                return redirect("/owner")
            driver_id = existing.id
        else:
            d = User(name=d_name or "ڈرائیور", phone=d_phone,
                     pw=generate_password_hash(d_pw), role="driver", owner_id=u.id)
            db.session.add(d); db.session.flush()
            driver_id = d.id

    db.session.add(Vehicle(owner_id=u.id, number=number, driver_id=driver_id))
    db.session.commit()
    flash("گاڑی شامل ہو گئی۔")
    return redirect("/owner")

@app.route("/owner")
@need("owner")
def owner(u):
    month = request.args.get("m") or dt.date.today().strftime("%Y-%m")
    vid = request.args.get("v", type=int)
    y, m = map(int, month.split("-"))
    start, end = dt.date(y, m, 1), dt.date(y + (m == 12), m % 12 + 1, 1)
    vehicles = Vehicle.query.filter_by(owner_id=u.id).all()
    ids = [v.id for v in vehicles if not vid or v.id == vid]
    es = Entry.query.filter(Entry.vehicle_id.in_(ids), Entry.day >= start, Entry.day < end).order_by(Entry.day.desc()).all() if ids else []
    tot = {}
    for e in es:
        tot.setdefault(e.vehicle_id, {"booking": 0, "fuel": 0, "kharcha": 0})[e.kind] += e.amount
    g = {"booking": 0, "fuel": 0, "kharcha": 0}
    for e in es: g[e.kind] += e.amount
    drivers = User.query.filter_by(owner_id=u.id, role="driver").all()
    return render_template("owner.html", g=g, u=u, month=month, vid=vid, vehicles=vehicles, es=es, tot=tot, drivers=drivers,
                           vn={v.id: v.number for v in vehicles}, dn={d.id: d.name for d in drivers}, K=KIND)

@app.route("/driver")
@need("driver")
def driver(u):
    return redirect("/static/driver.html")

@app.route("/api/sync", methods=["POST"])
def sync():
    u = me()
    if not u or u.role != "driver": return jsonify(error=1), 401
    mine = {v.id for v in Vehicle.query.filter_by(driver_id=u.id)}
    ok, bad = [], []
    for e in (request.get_json() or {}).get("entries", []):
        try:
            if e["vehicle_id"] in mine and e["kind"] in KIND and not Entry.query.filter_by(uid=e["uid"]).first():
                db.session.add(Entry(uid=e["uid"], vehicle_id=e["vehicle_id"], driver_id=u.id, day=dt.date.fromisoformat(e["day"]),
                                     kind=e["kind"], amount=int(round(float(e["amount"]))), note=(e.get("note") or "")[:200]))
                db.session.commit()
            ok.append(e["uid"])
        except Exception:
            db.session.rollback(); bad.append(e.get("uid"))
    return jsonify(ok=ok, bad=bad)

@app.route("/sw.js")
def sw():
    r = send_from_directory("static", "sw.js")
    r.headers["Cache-Control"] = "no-cache"
    r.headers["Service-Worker-Allowed"] = "/"
    return r

@app.route("/healthz")
def healthz():
    return "ok"

if __name__ == "__main__":
    app.run(debug=True)
