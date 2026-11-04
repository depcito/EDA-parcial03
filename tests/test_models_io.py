import json
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path

from donaciones.errors import DataSourceError, ValidationError
from donaciones.io_data import (load_dataset, load_lots, load_table, parse_lot, read_rows, save_lots_csv,
                                save_lots_json)
from donaciones.models import Category, Lot, Municipality, Road, RoadStatus
from tests.helpers import DATA, make_lot

GOOD = {"lot_id": "L-1", "donor_id": "D-001", "category": "agua", "description": "agua", "quantity": "10",
        "unit": "litro", "weight_kg": "10", "volume_m3": "0.01", "hub_id": "H-BOG", "received": "2026-03-02",
        "expiry": "2026-06-01", "cold_chain": "false"}
HEADER = ",".join(GOOD)


def write(dirpath, name, text):
    p = Path(dirpath) / name
    p.write_text(text, encoding="utf-8")
    return p


class ModelTests(unittest.TestCase):
    def test_lot_is_immutable(self):
        lot = make_lot()
        with self.assertRaises(Exception):
            lot.quantity = 5

    def test_negative_quantity_rejected(self):
        with self.assertRaises(ValidationError):
            make_lot(qty=-1)

    def test_available_cannot_exceed_quantity(self):
        with self.assertRaises(ValidationError):
            Lot(**{**make_lot().__dict__, "available": 101})

    def test_expiry_must_follow_reception(self):
        with self.assertRaises(ValidationError):
            make_lot(expiry_days=0)

    def test_take_marks_assigned_at_zero(self):
        lot = make_lot(qty=10)
        part = lot.take(4)
        self.assertEqual((part.available, part.status.value), (6, "DISPONIBLE"))
        self.assertEqual(part.take(6).status.value, "ASIGNADO")
        with self.assertRaises(ValidationError):
            part.take(7)

    def test_road_hours_and_closed(self):
        self.assertEqual(Road("a", "b", 100, 50, RoadStatus.OPEN).hours, 2.0)
        self.assertEqual(Road("a", "b", 100, 50, RoadStatus.RESTRICTED).hours, 4.0)
        self.assertEqual(Road("a", "b", 100, 50, RoadStatus.CLOSED).hours, float("inf"))
        with self.assertRaises(ValidationError):
            Road("a", "a", 1, 50, RoadStatus.OPEN)

    def test_municipality_victims_cannot_exceed_population(self):
        ds = load_dataset(DATA)
        m = next(iter(ds.municipalities.values()))
        with self.assertRaises(ValidationError):
            Municipality(**{**m.__dict__, "injured": m.population + 1})


class ParsingTests(unittest.TestCase):
    def test_parse_valid_row_case_insensitive_enum(self):
        lot = parse_lot(GOOD)
        self.assertEqual((lot.category, lot.quantity, lot.expiry), (Category.AGUA, 10, date(2026, 6, 1)))

    def test_bad_values(self):
        cases = [("quantity", "abc"), ("quantity", "-3"), ("quantity", "1.5"), ("received", "01/03/2026"),
                 ("category", "ARMAS"), ("weight_kg", "nan"), ("weight_kg", "-1"), ("lot_id", "  "),
                 ("cold_chain", "quizas"), ("description", None)]
        for key, val in cases:
            with self.subTest(key=key, val=val), self.assertRaises(ValidationError):
                parse_lot({**GOOD, key: val})

    def test_json_native_types(self):
        row = {**GOOD, "quantity": 10, "weight_kg": 10.0, "cold_chain": False}
        self.assertEqual(parse_lot(row).quantity, 10)
        with self.assertRaises(ValidationError):
            parse_lot({**row, "quantity": True})


class LoaderTests(unittest.TestCase):
    def test_real_dataset_is_clean(self):
        ds = load_dataset(DATA, strict=True)
        self.assertEqual(ds.errors, [])
        self.assertGreater(len(ds.lots), 200)
        self.assertTrue(all(l.expiry is None or l.expiry > ds.event.event_date for l in ds.lots.values()))

    def test_malformed_rows_are_reported_not_fatal(self):
        def row(**kw):
            return ",".join({**GOOD, **kw}.values())

        with tempfile.TemporaryDirectory() as d:
            text = "\n".join([
                HEADER,
                row(),                                  # válida
                row(lot_id="L-2", quantity="-5"),       # negativa
                row(lot_id="L-3", expiry="2026-02-01"),  # caduca antes del evento
                row(lot_id="L-4", donor_id="D-999"),    # donante huérfano
                row(lot_id="L-5", hub_id=""),           # nulo
                row(),                                  # duplicada
                "L-6,solo,tres",                        # faltan campos
                row() + ",extra",                       # sobran campos
            ])
            for f in DATA.iterdir():
                shutil.copy(f, d)
            write(d, "lots.csv", text)
            ds = load_dataset(d)
            self.assertEqual(list(ds.lots), ["L-1"])
            self.assertEqual(len(ds.errors), 7)
            with self.assertRaises(DataSourceError):
                load_dataset(d, strict=True)

    def test_missing_file_and_bad_json(self):
        with self.assertRaises(DataSourceError):
            read_rows("no_existe.csv")
        with tempfile.TemporaryDirectory() as d:
            write(d, "x.json", "{no es json")
            with self.assertRaises(DataSourceError):
                read_rows(Path(d) / "x.json")
            write(d, "y.json", '{"a": 1}')
            with self.assertRaises(DataSourceError):
                read_rows(Path(d) / "y.json")
            write(d, "vacio.csv", "")
            with self.assertRaises(DataSourceError):
                read_rows(Path(d) / "vacio.csv")
            write(d, "event.json", '{"name": "x"}')
            with self.assertRaises(DataSourceError):
                load_dataset(d)

    def test_json_list_with_non_object_item(self):
        with tempfile.TemporaryDirectory() as d:
            write(d, "l.json", json.dumps([GOOD, 42]))
            items, errors = load_table(Path(d) / "l.json", parse_lot, "lot_id")
            self.assertEqual((len(items), len(errors)), (1, 1))

    def test_roundtrip_csv_and_json(self):
        ds = load_dataset(DATA)
        lots = list(ds.lots.values())[:50]
        with tempfile.TemporaryDirectory() as d:
            save_lots_csv(Path(d) / "a.csv", lots)
            save_lots_json(Path(d) / "a.json", lots)
            for name in ("a.csv", "a.json"):
                back, errs = load_lots(Path(d) / name)
                self.assertEqual(errs, [])
                self.assertEqual(back, lots)

    def test_write_failure_is_wrapped(self):
        with self.assertRaises(DataSourceError):
            save_lots_csv(Path("carpeta/inexistente/x.csv"), [])


if __name__ == "__main__":
    unittest.main()
