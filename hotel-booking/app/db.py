"""Работа с базой данных SQLite: подключение, создание схемы, начальные данные."""
import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA = Path(__file__).with_name("schema.sql")

# Категории и характеристики взяты из файла «Характеристики номеров.txt»
CATEGORIES = {
    "Стандартный": {
        "image": "img/standart.png", "places": 2, "area": 22,
        "amenities": ["Полный санузел", "Двуспальная кровать", "Телевизор"],
        "rooms": [("101", 3000), ("102", 3400), ("103", 3800)],
    },
    "Студия": {
        "image": "img/studio.jpg", "places": 2, "area": 32,
        "amenities": ["Кухонный уголок", "Полный санузел", "Двуспальная кровать",
                      "Телевизор", "Холодильник"],
        "rooms": [("201", 4600), ("202", 5400), ("203", 6200)],
    },
    "Люкс": {
        "image": "img/lux.png", "places": 4, "area": 55,
        "amenities": ["Двухкомнатный", "Полный санузел", "Двуспальная кровать",
                      "Телевизор", "Холодильник", "Кондиционер"],
        "rooms": [("301", 8500), ("302", 11500), ("303", 15000)],
    },
}


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db(path):
    """Создаёт таблицы и заполняет каталог номеров (если база пустая)."""
    con = sqlite3.connect(path)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    if con.execute("SELECT COUNT(*) FROM rooms").fetchone()[0] == 0:
        for cat, data in CATEGORIES.items():
            cur = con.execute("INSERT INTO categories(name) VALUES (?)", (cat,))
            cat_id = cur.lastrowid
            amenity_ids = []
            for a in data["amenities"]:
                con.execute("INSERT OR IGNORE INTO amenities(name) VALUES (?)", (a,))
                amenity_ids.append(
                    con.execute("SELECT id FROM amenities WHERE name=?", (a,)).fetchone()[0])
            for number, price in data["rooms"]:
                cur = con.execute(
                    "INSERT INTO rooms(category_id, number, price, places, area, image)"
                    " VALUES (?,?,?,?,?,?)",
                    (cat_id, number, price, data["places"], data["area"], data["image"]))
                for aid in amenity_ids:
                    con.execute("INSERT INTO room_amenities VALUES (?,?)", (cur.lastrowid, aid))
    con.commit()
    con.close()
