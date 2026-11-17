"""Сервис бронирования номеров гостиницы «Сладкие сны» (Flask + SQLite)."""
import os
import secrets
from datetime import date
from functools import wraps
from pathlib import Path

from flask import (Flask, abort, flash, redirect, render_template, request,
                   session, url_for)
from werkzeug.security import check_password_hash, generate_password_hash

from . import db as database
from .validation import validate_booking

HOTEL_NAME = "Сладкие сны"
ADMIN_LOGIN = "hotel123"
# Пароль из задания (adminHotel) хранится только в виде хеша
ADMIN_PASSWORD_HASH = generate_password_hash("adminHotel")
CATALOG_SIZE = 6  # сколько случайных номеров выводить в каталоге


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(exist_ok=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=os.path.join(app.instance_path, "hotel.db"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)
    database.init_db(app.config["DATABASE"])
    app.teardown_appcontext(database.close_db)

    # ---------- общие вещи ----------
    @app.context_processor
    def inject_globals():
        return {"hotel_name": HOTEL_NAME, "csrf_token": csrf_token,
                "is_admin": bool(session.get("admin"))}

    def csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_hex(16)
        return session["csrf"]

    @app.before_request
    def check_csrf():
        if request.method == "POST":
            sent = request.form.get("csrf_token", "")
            if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
                abort(400, "Недействительный CSRF-токен. Обновите страницу и повторите.")

    @app.after_request
    def security_headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'")
        return resp

    def admin_required(view):
        @wraps(view)
        def wrapped(*a, **kw):
            if not session.get("admin"):
                return redirect(url_for("login"))
            return view(*a, **kw)
        return wrapped

    @app.errorhandler(400)
    @app.errorhandler(404)
    def error_page(e):
        return render_template("error.html", error=e), e.code

    # ---------- каталог ----------
    def room_rows(where="", params=(), tail=""):
        d = database.get_db()
        rooms = d.execute(
            "SELECT r.*, c.name AS category FROM rooms r"
            " JOIN categories c ON c.id = r.category_id " + where + tail, params).fetchall()
        out = []
        for r in rooms:
            am = [a["name"] for a in d.execute(
                "SELECT a.name FROM amenities a JOIN room_amenities ra ON ra.amenity_id=a.id"
                " WHERE ra.room_id=? ORDER BY a.id", (r["id"],))]
            out.append({**dict(r), "amenities": am})
        return out

    @app.get("/")
    def catalog():
        d = database.get_db()
        categories = d.execute("SELECT * FROM categories ORDER BY id").fetchall()
        valid_ids = {c["id"] for c in categories}
        selected = {int(x) for x in request.args.getlist("category")
                    if x.isdigit() and int(x) in valid_ids}
        if selected:
            marks = ",".join("?" * len(selected))
            rooms = room_rows(f"WHERE r.category_id IN ({marks})", tuple(selected),
                              f" ORDER BY RANDOM() LIMIT {CATALOG_SIZE}")
        else:
            rooms = room_rows("", (), f" ORDER BY RANDOM() LIMIT {CATALOG_SIZE}")
        return render_template("catalog.html", rooms=rooms, categories=categories,
                               selected=selected)

    # ---------- бронирование ----------
    def busy_periods(room_id):
        rows = database.get_db().execute(
            "SELECT check_in, check_out FROM bookings WHERE room_id=? AND status='Одобрена'"
            " AND check_out > ? ORDER BY check_in",
            (room_id, date.today().isoformat())).fetchall()
        return [(date.fromisoformat(r["check_in"]), date.fromisoformat(r["check_out"]))
                for r in rows]

    @app.route("/order/<int:room_id>", methods=["GET", "POST"])
    def order(room_id):
        rooms = room_rows("WHERE r.id = ?", (room_id,))
        if not rooms:
            abort(404)
        room, busy = rooms[0], busy_periods(room_id)
        form, errors = {}, {}
        if request.method == "POST":
            clean, errors = validate_booking(request.form, busy)
            form = {"first_name": clean["first_name"], "last_name": clean["last_name"],
                    "phone": clean["phone"], "email": clean["email"],
                    "check_in": clean["check_in_raw"], "check_out": clean["check_out_raw"]}
            if not errors:
                d = database.get_db()
                d.execute(
                    "INSERT INTO bookings(room_id, first_name, last_name, phone, email,"
                    " check_in, check_out) VALUES (?,?,?,?,?,?,?)",
                    (room_id, clean["first_name"], clean["last_name"], clean["phone"],
                     clean["email"], clean["check_in"].isoformat(),
                     clean["check_out"].isoformat()))
                d.commit()
                flash("Заявка успешно отправлена!", "success")
                return redirect(url_for("order", room_id=room_id))
        return render_template(
            "order.html", room=room, form=form, errors=errors,
            busy=[[a.isoformat(), b.isoformat()] for a, b in busy],
            busy_text=[f"{a:%d.%m.%Y} – {b:%d.%m.%Y}" for a, b in busy],
            today=date.today().isoformat())

    # ---------- вход администратора ----------
    @app.route("/login", methods=["GET", "POST"])
    def login():
        error = None
        if request.method == "POST":
            user = request.form.get("username", "")
            pwd = request.form.get("password", "")
            ok_user = secrets.compare_digest(user.encode(), ADMIN_LOGIN.encode())
            ok_pwd = check_password_hash(ADMIN_PASSWORD_HASH, pwd)
            if ok_user and ok_pwd:
                session.clear()
                session["admin"] = True
                return redirect(url_for("admin"))
            error = "Неверный логин или пароль"
        return render_template("login.html", error=error)

    @app.post("/logout")
    def logout():
        session.clear()
        return redirect(url_for("catalog"))

    # ---------- панель управления ----------
    @app.get("/admin")
    @admin_required
    def admin():
        rows = database.get_db().execute(
            "SELECT b.*, r.number, c.name AS category FROM bookings b"
            " JOIN rooms r ON r.id=b.room_id JOIN categories c ON c.id=r.category_id"
            " ORDER BY CASE b.status WHEN 'Новая' THEN 0 WHEN 'Одобрена' THEN 1 ELSE 2 END,"
            " b.created_at DESC, b.id DESC").fetchall()
        bookings = []
        for r in rows:
            b = dict(r)
            b["check_in_fmt"] = date.fromisoformat(b["check_in"]).strftime("%d.%m.%Y")
            b["check_out_fmt"] = date.fromisoformat(b["check_out"]).strftime("%d.%m.%Y")
            bookings.append(b)
        return render_template("admin.html", bookings=bookings)

    @app.post("/admin/booking/<int:booking_id>/<action>")
    @admin_required
    def booking_action(booking_id, action):
        d = database.get_db()
        b = d.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
        if b is None:
            abort(404)
        if action == "delete":
            d.execute("DELETE FROM bookings WHERE id=?", (booking_id,))
            flash("Заявка удалена", "success")
        elif action == "approve":
            clash = d.execute(
                "SELECT 1 FROM bookings WHERE room_id=? AND status='Одобрена' AND id<>?"
                " AND check_in < ? AND check_out > ?",
                (b["room_id"], booking_id, b["check_out"], b["check_in"])).fetchone()
            if clash:
                flash("Нельзя одобрить: номер уже забронирован на пересекающийся период", "danger")
            else:
                d.execute("UPDATE bookings SET status='Одобрена' WHERE id=?", (booking_id,))
                flash("Заявка одобрена", "success")
        elif action == "reject":
            d.execute("UPDATE bookings SET status='Отклонена' WHERE id=?", (booking_id,))
            flash("Заявка отклонена", "success")
        else:
            abort(404)
        d.commit()
        return redirect(url_for("admin"))

    return app
