from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


AS_OF = date(2026, 10, 1)
FIELDS = [
    "Last_name_ru", "First_name_ru", "Middle_name_ru", "Sex_ru", "Birth_date",
    "Birth_place_ru", "Issue_date", "Issue_organisation_code", "Licence_number",
    "Issue_organization_ru",
]

MIN_FIELD_CONF = {
    "Last_name_ru": 0.997,
    "First_name_ru": 0.997,
    "Middle_name_ru": 0.997,
    "Sex_ru": 0.997,
    "Birth_date": 0.997,
    "Birth_place_ru": 0.999,
    "Issue_date": 0.997,
    "Issue_organisation_code": 0.997,
    "Licence_number": 0.997,
    "Issue_organization_ru": 0.999,
}
MIN_CHAR_CONF = 0.99

# приводит текст к верхнему регистру, убирает повторные пробелы
def norm(value: Any) -> str:
    return " ".join(str(value or "").split()).upper()


def field_text(field: dict[str, Any] | None) -> str:
    if not field:
        return ""
    return " ".join(str(line.get("text", "")).strip()
                    for line in field.get("lines", []) if line.get("text"))

# уверенность всего поля и минимальную уверенность среди его символов
def field_confidence(field: dict[str, Any] | None) -> tuple[float, float]:
    if not field:
        return 0.0, 0.0
    confidence = float(field.get("conf", 0.0) or 0.0)
    chars = [float(c) for line in field.get("lines", [])
             for c in line.get("char_conf", [])]
    return confidence, min(chars, default=0.0)

# дата формата в обьект даты
def parse_date(value: str) -> date | None:
    try:
        return datetime.strptime(norm(value), "%d.%m.%Y").date()
    except (ValueError, TypeError):
        return None

# день рождения в заданном году (в невисокосный год 29 февраля день рождения будет 28)
def birthday_in_year(born: date, year: int) -> date:
    try:
        return born.replace(year=year)
    except ValueError:
        return date(year, 2, 28)

# возраст человека на указанную дату
def age_on(born: date, on: date) -> int:
    return on.year - born.year - ((on.month, on.day) < (born.month, born.day))

# проверка выдачи паспорта
def passport_valid(born: date, issued: date, as_of: date = AS_OF) -> bool:
    if issued > as_of or age_on(born, issued) < 14 or age_on(born, as_of) < 14:
        return False
    issued_age = age_on(born, issued)
    if issued_age >= 45:
        return True
    boundary_age = 20 if issued_age < 20 else 45
    boundary = birthday_in_year(born, born.year + boundary_age)
    return as_of <= boundary + timedelta(days=90)

# проверки MRZ 

# контрольная цифра MRZ по весам 7,3,1
def check_digit(value: str) -> str | None:
    table = {str(i): i for i in range(10)}
    table.update({chr(ord("A") + i): 10 + i for i in range(26)})
    table["<"] = 0
    if any(c not in table for c in value):
        return None
    return str(sum(table[c] * (7, 3, 1)[i % 3]
                   for i, c in enumerate(value)) % 10)

# извлечение строк MRZ из записи
def mrz_lines(record: dict[str, Any]) -> list[str]:
    mrz = record.get("mrz") or {}
    return [norm(line.get("text", "")).replace(" ", "")
            for line in mrz.get("lines", [])]

# проверка
def mrz_ok(lines: list[str]) -> bool:
    if len(lines) < 2 or len(lines[0]) != 44 or len(lines[1]) != 44:
        return False
    a, b = lines[:2]
    return (
        a.startswith("PNRUS")
        and b[10:13] == "RUS"
        and check_digit(b[0:9]) == b[9]
        and check_digit(b[13:19]) == b[19]
        and b[20] in "MF"
        and re.fullmatch(r"\d{6}", b[13:19]) is not None
    )

# перевод русских букв в латиницу
def transliterate(value: str) -> str:
    mapping = {
        "А":"A", "Б":"B", "В":"V", "Г":"G", "Д":"D", "Е":"E", "Ё":"E",
        "Ж":"ZH", "З":"Z", "И":"I", "Й":"I", "К":"K", "Л":"L", "М":"M",
        "Н":"N", "О":"O", "П":"P", "Р":"R", "С":"S", "Т":"T", "У":"U",
        "Ф":"F", "Х":"KH", "Ц":"TS", "Ч":"CH", "Ш":"SH", "Щ":"SHCH",
        "Ъ":"IE", "Ы":"Y", "Ь":"", "Э":"E", "Ю":"IU", "Я":"IA",
    }
    return "".join(mapping.get(c, c) for c in norm(value) if c.isalpha())

# счетчик замен, удалений, вставок
def edit_distance(a: str, b: str) -> int:
    if len(a) < len(b):
        a, b = b, a
    previous = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        current = [i]
        for j, cb in enumerate(b, 1):
            current.append(min(current[-1] + 1, previous[j] + 1,
                               previous[j - 1] + (ca != cb)))
        previous = current
    return previous[-1]

# раздел ФИО
def mrz_name_parts(first_line: str) -> list[str]:
    if len(first_line) != 44 or "<<" not in first_line:
        return []
    surname, rest = first_line[5:].split("<<", 1)
    parts = [surname]
    parts.extend(x for x in rest.split("<") if x)
    return parts[:3]

# сверка
def consistent_with_mrz(fields: dict[str, str], lines: list[str]) -> bool:
    if not mrz_ok(lines):
        return False
    first, second = lines[:2]
    mrz_names = mrz_name_parts(first)
    if len(mrz_names) < 2:
        return False

    for field_name, mrz_name in zip(FIELDS[:3], mrz_names):
        candidate = transliterate(fields[field_name]).replace(" ", "")
        if not candidate or edit_distance(candidate, mrz_name) > 1:
            return False

    birth = parse_date(fields["Birth_date"])
    if not birth or birth.strftime("%y%m%d") != second[13:19]:
        return False
    expected_sex = "M" if norm(fields["Sex_ru"]).startswith("МУЖ") else "F"
    if second[20] != expected_sex:
        return False

    licence_digits = "".join(re.findall(r"\d", fields["Licence_number"]))
    if (len(licence_digits) != 10 or licence_digits[:3] != second[:3]
            or licence_digits[-6:] != second[3:9]):
        return False
    code_digits = "".join(re.findall(r"\d", fields["Issue_organisation_code"]))
    tail = re.search(r"(\d{3})<\d{2}$", second)
    if len(code_digits) != 6 or not tail or code_digits[-3:] != tail.group(1):
        return False
    return True

# проверка одного документа
def candidate_fields(record: dict[str, Any]) -> dict[str, str] | None:
    viz = record.get("viz") or {}
    fields: dict[str, str] = {}
    for name in FIELDS:
        value = field_text(viz.get(name))
        confidence, min_char = field_confidence(viz.get(name))
        if not value or confidence < MIN_FIELD_CONF[name] or min_char < MIN_CHAR_CONF:
            return None
        fields[name] = norm(value)

    if fields["Sex_ru"] not in {"МУЖ.", "ЖЕН."}:
        return None
    birth = parse_date(fields["Birth_date"])
    issued = parse_date(fields["Issue_date"])
    if not birth or not issued or issued < birth:
        return None
    if not re.fullmatch(r"\d{3}-\d{3}", fields["Issue_organisation_code"]):
        return None
    if not re.fullmatch(r"\d{2} \d{2} \d{6}", fields["Licence_number"]):
        return None
    if not passport_valid(birth, issued):
        return None

    lines = mrz_lines(record)
    if not consistent_with_mrz(fields, lines):
        return None
    return fields

# читает jsonl построчно, запись ответа для каждого документа+кол-во документов и принятых
def process(input_path: Path, output_path: Path) -> tuple[int, int]:
    total = accepted = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with input_path.open(encoding="utf-8") as src, output_path.open("w", encoding="utf-8") as dst:
        for line_number, line in enumerate(src, 1):
            try:
                record = json.loads(line)
                doc_id = record["doc_id"]
            except (json.JSONDecodeError, KeyError) as exc:
                raise ValueError(f"Invalid input on line {line_number}: {exc}") from exc
            fields = candidate_fields(record)
            answer = {"doc_id": doc_id,
                      "decision": "accept" if fields is not None else "reject"}
            if fields is not None:
                answer["fields"] = fields
                accepted += 1
            dst.write(json.dumps(answer, ensure_ascii=False) + "\n")
            total += 1
    return total, accepted

# путь к входу и выходу - запуск process и итоговая печать статистики
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="*_predictions.jsonl")
    parser.add_argument("output", type=Path, help="answers.jsonl")
    args = parser.parse_args()
    try:
        total, accepted = process(args.input, args.output)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"documents: {total}; accepted: {accepted}; rejected: {total - accepted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
