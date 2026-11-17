-- Схема БД сервиса бронирования номеров «Сладкие сны»
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS categories (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE            -- Стандартный / Студия / Люкс
);

CREATE TABLE IF NOT EXISTS rooms (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    number      TEXT    NOT NULL UNIQUE,
    price       INTEGER NOT NULL CHECK (price > 0),
    places      INTEGER NOT NULL CHECK (places > 0),
    area        INTEGER NOT NULL CHECK (area > 0),
    image       TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS amenities (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS room_amenities (
    room_id    INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    amenity_id INTEGER NOT NULL REFERENCES amenities(id),
    PRIMARY KEY (room_id, amenity_id)
);

CREATE TABLE IF NOT EXISTS bookings (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id    INTEGER NOT NULL REFERENCES rooms(id) ON DELETE CASCADE,
    first_name TEXT NOT NULL,
    last_name  TEXT NOT NULL,
    phone      TEXT NOT NULL,
    email      TEXT NOT NULL,
    check_in   TEXT NOT NULL,
    check_out  TEXT NOT NULL,
    status     TEXT NOT NULL DEFAULT 'Новая'
               CHECK (status IN ('Новая', 'Одобрена', 'Отклонена')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    CHECK (check_out > check_in)
);

CREATE INDEX IF NOT EXISTS idx_bookings_room_status ON bookings(room_id, status);
