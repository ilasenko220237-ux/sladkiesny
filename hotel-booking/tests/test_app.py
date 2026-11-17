import os
import re
import sqlite3
import tempfile
import unittest
from datetime import date, timedelta

from app.main import create_app


def d(offset):
    return (date.today() + timedelta(days=offset)).strftime("%d.%m.%Y")


class AppTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "t.db")
        self.app = create_app({"TESTING": True, "DATABASE": self.db})
        self.c = self.app.test_client()

    def tearDown(self):
        self.tmp.cleanup()

    def token(self, client=None):
        client = client or self.c
        client.get("/")
        with client.session_transaction() as s:
            s["csrf"] = s.get("csrf", "tok")
            return s["csrf"]

    def book(self, room=1, **over):
        data = {"first_name": "Иван", "last_name": "Петров-Иванов", "phone": "+7(800)555-35-35",
                "email": "ivan@example.com", "check_in": d(5), "check_out": d(7)}
        data.update(over)
        data["csrf_token"] = self.token()
        return self.c.post(f"/order/{room}", data=data)

    def login(self, client=None):
        client = client or self.c
        t = self.token(client)
        return client.post("/login", data={"username": "hotel123", "password": "adminHotel",
                                           "csrf_token": t})

    def rows(self, sql):
        con = sqlite3.connect(self.db)
        try:
            return con.execute(sql).fetchall()
        finally:
            con.close()

    # ---- каталог ----
    def test_catalog_six_random_rooms(self):
        html = self.c.get("/").get_data(as_text=True)
        self.assertEqual(html.count('class="card"'), 6)
        self.assertIn("Забронировать", html)

    def test_catalog_filter(self):
        for cat_id, name in ((1, "Стандартный"), (2, "Студия"), (3, "Люкс")):
            html = self.c.get(f"/?category={cat_id}").get_data(as_text=True)
            self.assertEqual(html.count("Категория: "), 3)
            self.assertEqual(html.count(f"Категория: {name}"), 3)
        html = self.c.get("/?category=1&category=3").get_data(as_text=True)
        self.assertNotIn("Категория: Студия", html)
        html = self.c.get("/?category=abc&category=999").get_data(as_text=True)  # мусор игнорируется
        self.assertEqual(html.count('class="card"'), 6)

    # ---- валидация ----
    def test_valid_booking_saved_as_new(self):
        r = self.book()
        self.assertEqual(r.status_code, 302)
        self.assertEqual(self.rows("SELECT status, check_in FROM bookings")[0][0], "Новая")
        self.assertIn("Заявка успешно отправлена!", self.c.get("/order/1").get_data(as_text=True))

    def test_field_errors(self):
        cases = [
            ({"first_name": ""}, "Пожалуйста, введите имя"),
            ({"first_name": "John"}, "кириллица"),
            ({"first_name": "Иван1"}, "кириллица"),
            ({"last_name": ""}, "введите фамилию"),
            ({"last_name": "<script>"}, "кириллица"),
            ({"phone": ""}, "введите номер телефона"),
            ({"phone": "89005553535"}, "+7(XXX)XXX-XX-XX"),
            ({"email": ""}, "введите email"),
            ({"email": "not-an-email"}, "корректный email"),
            ({"check_in": ""}, "введите дату заезда"),
            ({"check_in": "2030-01-01"}, "ДД.ММ.ГГГГ"),
            ({"check_in": "31.02.2030"}, "ДД.ММ.ГГГГ"),
            ({"check_out": ""}, "введите дату выезда"),
            ({"check_in": d(-1), "check_out": d(3)}, "раньше текущей даты"),
            ({"check_in": d(5), "check_out": d(5)}, "позже даты заезда"),
            ({"check_in": d(5), "check_out": d(4)}, "позже даты заезда"),
        ]
        for over, text in cases:
            r = self.book(**over)
            self.assertEqual(r.status_code, 200, over)
            self.assertIn(text, r.get_data(as_text=True), over)
        self.assertEqual(self.rows("SELECT COUNT(*) FROM bookings")[0][0], 0)

    def test_today_checkin_allowed(self):
        self.assertEqual(self.book(check_in=d(0), check_out=d(1)).status_code, 302)

    def test_unknown_room_404(self):
        self.assertEqual(self.c.get("/order/9999").status_code, 404)

    # ---- пересечения с одобренными бронями ----
    def test_overlap_only_with_approved(self):
        self.book(check_in=d(10), check_out=d(15))
        # пока заявка «Новая» — период свободен
        self.assertEqual(self.book(check_in=d(12), check_out=d(14)).status_code, 302)
        self.login()
        bid = self.rows("SELECT id FROM bookings ORDER BY id")[0][0]
        self.c.post(f"/admin/booking/{bid}/approve", data={"csrf_token": self.token()})
        self.assertEqual(self.rows("SELECT status FROM bookings WHERE id=%d" % bid)[0][0], "Одобрена")
        r = self.book(check_in=d(12), check_out=d(14))
        self.assertEqual(r.status_code, 200)
        self.assertIn("уже забронирован", r.get_data(as_text=True))
        self.assertEqual(self.book(check_in=d(8), check_out=d(11)).status_code, 200)   # заходит внутрь
        self.assertEqual(self.book(check_in=d(9), check_out=d(16)).status_code, 200)   # накрывает
        self.assertEqual(self.book(check_in=d(15), check_out=d(17)).status_code, 302)  # день выезда свободен
        self.assertEqual(self.book(check_in=d(8), check_out=d(10)).status_code, 302)   # выезд в день заезда
        self.assertEqual(self.book(room=2, check_in=d(12), check_out=d(14)).status_code, 302)  # другой номер

    def test_order_page_exposes_busy_periods(self):
        self.book(check_in=d(10), check_out=d(15))
        self.login()
        self.c.post("/admin/booking/1/approve", data={"csrf_token": self.token()})
        html = self.c.get("/order/1").get_data(as_text=True)
        self.assertIn("data-busy=", html)
        self.assertIn("Номер занят", html)

    def test_admin_cannot_approve_overlapping(self):
        self.book(check_in=d(10), check_out=d(15))
        self.book(check_in=d(12), check_out=d(14))
        self.login()
        for bid in (1, 2):
            self.c.post(f"/admin/booking/{bid}/approve", data={"csrf_token": self.token()})
        self.assertEqual([r[0] for r in self.rows("SELECT status FROM bookings ORDER BY id")],
                         ["Одобрена", "Новая"])

    # ---- панель администратора ----
    def test_admin_requires_login(self):
        self.assertEqual(self.c.get("/admin").status_code, 302)
        self.assertTrue(self.c.get("/admin").headers["Location"].endswith("/login"))
        r = self.c.post("/admin/booking/1/delete", data={"csrf_token": self.token()})
        self.assertEqual(r.status_code, 302)

    def test_login_wrong_and_right(self):
        t = self.token()
        for u, p in (("hotel123", "wrong"), ("admin", "adminHotel"), ("", "")):
            r = self.c.post("/login", data={"username": u, "password": p, "csrf_token": t})
            self.assertEqual(r.status_code, 200)
            self.assertIn("Неверный логин или пароль", r.get_data(as_text=True))
        self.assertEqual(self.login().status_code, 302)
        self.assertEqual(self.c.get("/admin").status_code, 200)

    def test_approve_reject_delete(self):
        self.book()
        self.book(check_in=d(20), check_out=d(22))
        self.login()
        t = self.token()
        self.c.post("/admin/booking/1/approve", data={"csrf_token": t})
        self.c.post("/admin/booking/2/reject", data={"csrf_token": t})
        self.assertEqual([r[0] for r in self.rows("SELECT status FROM bookings ORDER BY id")],
                         ["Одобрена", "Отклонена"])
        html = self.c.get("/admin").get_data(as_text=True)
        self.assertIn("Петров-Иванов", html)
        self.c.post("/admin/booking/1/delete", data={"csrf_token": t})
        self.assertEqual(self.rows("SELECT COUNT(*) FROM bookings")[0][0], 1)
        self.assertEqual(self.c.post("/admin/booking/999/delete", data={"csrf_token": t}).status_code, 404)

    def test_logout(self):
        self.login()
        self.c.post("/logout", data={"csrf_token": self.token()})
        self.assertEqual(self.c.get("/admin").status_code, 302)

    # ---- безопасность ----
    def test_csrf_required(self):
        self.c.get("/")
        r = self.c.post("/order/1", data={"first_name": "Иван"})
        self.assertEqual(r.status_code, 400)
        r = self.c.post("/login", data={"username": "hotel123", "password": "adminHotel"})
        self.assertEqual(r.status_code, 400)

    def test_sql_injection_and_xss_are_inert(self):
        r = self.c.get("/?category=1%20OR%201=1")
        self.assertEqual(r.status_code, 200)
        r = self.book(first_name="'; DROP TABLE bookings;--")
        self.assertIn("кириллица", r.get_data(as_text=True))
        self.assertEqual(self.rows("SELECT COUNT(*) FROM bookings")[0][0], 0)
        r = self.book(email='"><script>alert(1)</script>@a.ru')
        self.assertNotIn("<script>alert(1)", r.get_data(as_text=True))

    def test_security_headers(self):
        h = self.c.get("/").headers
        self.assertEqual(h["X-Content-Type-Options"], "nosniff")
        self.assertIn("default-src 'self'", h["Content-Security-Policy"])


if __name__ == "__main__":
    unittest.main()
