

import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

import postprocess as pp


class TextAndDateTests(unittest.TestCase):
    def test_norm_collapses_whitespace_and_case(self):
        self.assertEqual(pp.norm("  Иванов\n Иван "), "ИВАНОВ ИВАН")

    def test_field_text_joins_ocr_lines(self):
        field = {"lines": [{"text": "С. ПРИМЕР"}, {"text": "РАЙОН"}]}
        self.assertEqual(pp.field_text(field), "С. ПРИМЕР РАЙОН")

    def test_field_confidence_returns_field_and_worst_character(self):
        field = {"conf": 0.998, "lines": [{"char_conf": [0.999, 0.991]}]}
        self.assertEqual(pp.field_confidence(field), (0.998, 0.991))

    def test_parse_date_accepts_valid_date_and_rejects_invalid_date(self):
        self.assertEqual(pp.parse_date("01.10.2000"), date(2000, 10, 1))
        self.assertIsNone(pp.parse_date("31.02.2000"))

    def test_leap_day_birthday(self):
        self.assertEqual(pp.birthday_in_year(date(2000, 2, 29), 2021), date(2021, 2, 28))

    def test_age_on_accounts_for_whether_birthday_has_passed(self):
        born = date(2000, 10, 2)
        self.assertEqual(pp.age_on(born, date(2026, 10, 1)), 25)
        self.assertEqual(pp.age_on(born, date(2026, 10, 2)), 26)

    def test_passport_validity_20_year_window(self):
        born = date(2006, 10, 1)
        issued = date(2020, 10, 1)
        self.assertTrue(pp.passport_valid(born, issued, date(2020, 10, 1)))
        self.assertFalse(pp.passport_valid(born, issued, date(2027, 1, 1)))

    def test_passport_issued_after_45_is_indefinite(self):
        self.assertTrue(pp.passport_valid(date(1970, 6, 1), date(2017, 6, 1), date(2026, 10, 1)))


class MrzTests(unittest.TestCase):
    line1 = "PNRUSZAINTINOV<<ZAKERIQ<NAZIFULOVI3<<<<<<<<<"
    line2 = "6122839687RUS1006102M<<<<<<<4250911620004<28"

    def test_check_digit_known_sample(self):
        self.assertEqual(pp.check_digit("612283968"), "7")

    def test_mrz_validation_known_sample(self):
        self.assertEqual(len(self.line1), 44)
        self.assertEqual(len(self.line2), 44)
        self.assertTrue(pp.mrz_ok([self.line1, self.line2]))

    def test_mrz_rejects_bad_check_digit(self):
        broken = self.line2[:9] + "0" + self.line2[10:]
        self.assertFalse(pp.mrz_ok([self.line1, broken]))

    def test_transliteration(self):
        self.assertEqual(pp.transliterate("ЗАИНТИНОВ"), "ZAINTINOV")

    def test_edit_distance(self):
        self.assertEqual(pp.edit_distance("KITURKO", "KITURKS"), 1)
        self.assertEqual(pp.edit_distance("ABC", "XYZ"), 3)

    def test_mrz_name_split(self):
        self.assertEqual(pp.mrz_name_parts(self.line1), ["ZAINTINOV", "ZAKERIQ", "NAZIFULOVI3"])


class OutputTests(unittest.TestCase):
    def test_process_writes_a_reject_answer_for_missing_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.jsonl"
            output = root / "nested" / "answers.jsonl"
            source.write_text(json.dumps({"doc_id": "synthetic_1", "viz": {}}) + "\n", encoding="utf-8")

            self.assertEqual(pp.process(source, output), (1, 0))
            answer = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(answer, {"doc_id": "synthetic_1", "decision": "reject"})


if __name__ == "__main__":
    unittest.main()
