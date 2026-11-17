"""Серверная валидация данных формы бронирования."""
import re
from datetime import date, datetime

NAME_RE = re.compile(r"^(?=.*[А-Яа-яЁё])[А-Яа-яЁё\s.\-]+$")
PHONE_RE = re.compile(r"^\+7\(\d{3}\)\d{3}-\d{2}-\d{2}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DATE_RE = re.compile(r"^\d{2}\.\d{2}\.\d{4}$")


def parse_date(value):
    """ДД.ММ.ГГГГ -> date, иначе None."""
    if not DATE_RE.match(value):
        return None
    try:
        return datetime.strptime(value, "%d.%m.%Y").date()
    except ValueError:
        return None


def validate_booking(form, busy_periods, today=None):
    """Проверяет поля заявки.

    busy_periods — список (check_in, check_out) уже ОДОБРЕННЫХ броней этого номера (date, date).
    Возвращает (clean, errors): очищенные значения и словарь {поле: сообщение}.
    """
    today = today or date.today()
    errors, clean = {}, {}

    for field, label in (("first_name", "имя"), ("last_name", "фамилию")):
        v = (form.get(field) or "").strip()
        if not v:
            errors[field] = f"Пожалуйста, введите {label}"
        elif len(v) > 50:
            errors[field] = "Не более 50 символов"
        elif not NAME_RE.match(v):
            errors[field] = "Допустимы только кириллица, пробелы, точки и тире"
        clean[field] = v

    v = (form.get("phone") or "").strip()
    if not v:
        errors["phone"] = "Пожалуйста, введите номер телефона"
    elif not PHONE_RE.match(v):
        errors["phone"] = "Телефон должен быть в формате +7(XXX)XXX-XX-XX"
    clean["phone"] = v

    v = (form.get("email") or "").strip()
    if not v:
        errors["email"] = "Пожалуйста, введите email"
    elif len(v) > 254 or not EMAIL_RE.match(v):
        errors["email"] = "Введите корректный email, например name@example.com"
    clean["email"] = v

    ci_raw = (form.get("check_in") or "").strip()
    co_raw = (form.get("check_out") or "").strip()
    clean["check_in_raw"], clean["check_out_raw"] = ci_raw, co_raw
    ci = co = None
    if not ci_raw:
        errors["check_in"] = "Пожалуйста, введите дату заезда"
    else:
        ci = parse_date(ci_raw)
        if ci is None:
            errors["check_in"] = "Дата должна быть в формате ДД.ММ.ГГГГ и существовать в календаре"
        elif ci < today:
            errors["check_in"] = "Дата заезда не может быть раньше текущей даты"
    if not co_raw:
        errors["check_out"] = "Пожалуйста, введите дату выезда"
    else:
        co = parse_date(co_raw)
        if co is None:
            errors["check_out"] = "Дата должна быть в формате ДД.ММ.ГГГГ и существовать в календаре"
        elif ci is not None and co <= ci:
            errors["check_out"] = "Дата выезда должна быть позже даты заезда"

    if ci and co and "check_in" not in errors and "check_out" not in errors:
        for b_in, b_out in busy_periods:
            if ci < b_out and co > b_in:
                errors["check_out"] = (
                    "Номер уже забронирован на период "
                    f"{b_in:%d.%m.%Y} – {b_out:%d.%m.%Y}. Выберите другие даты")
                break
    clean["check_in"], clean["check_out"] = ci, co
    return clean, errors
