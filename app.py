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
# SQLAlchemy 2.x: postgres:// ko postgresql:// mein badalna zaroori hai
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
class Link(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("user.id")); driver_id = db.Column(db.Integer, db.ForeignKey("user.id"))
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
# Har cold start par create_all chalana risky hai. Ek flag use karte hain.
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

# --- Manual init route (first deploy ke baad ek dafa call karein) ---
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
    if request.method == "POST":
        f = request.form; phone = f["phone"].strip()
        if User.query.filter_by(phone=phone).first():
            flash("یہ فون نمبر پہلے سے موجود ہے۔ لاگ ان کریں۔")
        else:
            u = User(name=f["name"].strip(), phone=phone, pw=generate_password_hash(f["pw"]), role="owner" if f["role"] == "owner" else "driver")
            db.session.add(u); db.session.commit()
            session.permanent = True; session["uid"] = u.id
            return redirect("/")
    return render_template("auth.html", reg=True, u=None)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = User.query.filter_by(phone=request.form["phone"].strip()).first()
        if u and check_password_hash(u.pw, request.form["pw"]):
            session.permanent = True; session["uid"] = u.id
            return redirect("/")
        flash("فون نمبر یا پاسورڈ غلط ہے۔")
    return render_template("auth.html", reg=False, u=None)

@app.route("/logout")
def logout():
    session.clear(); return redirect("/login")

@app.route("/link", methods=["POST"])
def link():
    u = me()
    if not u: return redirect("/login")
    o = User.query.filter_by(phone=request.form["phone"].strip()).first()
    want = "driver" if u.role == "owner" else "owner"
    if not o or o.role != want:
        flash("اس نمبر کا %s اکاؤنٹ نہیں ملا۔" % ("ڈرائیور" if want == "driver" else "مالک"))
    else:
        ow, dr = (u, o) if u.role == "owner" else (o, u)
        if not Link.query.filter_by(owner_id=ow.id, driver_id=dr.id).first():
            db.session.add(Link(owner_id=ow.id, driver_id=dr.id)); db.session.commit()
        flash("جڑ گئے: " + o.name)
    return redirect("/")

@app.route("/vehicle", methods=["POST"])
@need("owner")
def vehicle(u):
    d = request.form.get("driver_id", type=int)
    if d and not Link.query.filter_by(owner_id=u.id, driver_id=d).first(): d = None
    db.session.add(Vehicle(owner_id=u.id, number=request.form["number"].strip(), driver_id=d)); db.session.commit()
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
    drivers = [db.session.get(User, l.driver_id) for l in Link.query.filter_by(owner_id=u.id)]
    return render_template("owner.html", g=g, u=u, month=month, vid=vid, vehicles=vehicles, es=es, tot=tot, drivers=drivers,
                           vn={v.id: v.number for v in vehicles}, dn={d.id: d.name for d in drivers}, K=KIND)

@app.route("/driver")
@need("driver")
def driver(u):
    vs = [{"id": v.id, "n": v.number} for v in Vehicle.query.filter_by(driver_id=u.id)]
    owners = [db.session.get(User, l.owner_id) for l in Link.query.filter_by(driver_id=u.id)]
    return render_template("driver.html", u=u, vs=vs, owners=owners)

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

# health check (optional, Vercel ke liye acha rahega)
@app.route("/healthz")
def healthz():
    return "ok"

if __name__ == "__main__":
    app.run(debug=True)
