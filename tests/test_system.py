import threading
import unittest
from datetime import timedelta

from donaciones.errors import DonationError, ValidationError
from donaciones.forms import validate_donation_form
from donaciones.models import Category, LotStatus, RoadStatus
from tests.helpers import EVENT, make_lot, make_system


def drain(system, cat):
    """Retira del inventario todo el stock disponible de una categoría (para escenarios de escasez)."""
    for lot_id in list(system._by_category[cat]):
        lot = system.lots[lot_id]
        if lot.status is LotStatus.AVAILABLE and lot.available > 0:
            system._unindex(lot)
            system.lots[lot_id] = lot.take(lot.available)


class RegistrationTests(unittest.TestCase):
    def setUp(self):
        self.s = make_system()

    def test_register_and_find_by_id(self):
        lot = self.s.register_donation(make_lot())
        self.assertEqual(self.s.get_lot("L-T001"), lot)
        self.assertIn(lot, self.s.search(category=Category.VIVERES, hub_id="H-PEI"))

    def test_rejections(self):
        self.s.register_donation(make_lot())
        for bad in (make_lot(), make_lot("X1", donor="D-999"), make_lot("X2", hub="H-NOPE"), make_lot("X3", qty=0)):
            with self.subTest(lot=bad.lot_id), self.assertRaises(DonationError):
                self.s.register_donation(bad)
        with self.assertRaises(ValidationError):  # recibido antes del evento
            self.s.register_donation(make_lot("X4", received=EVENT - timedelta(days=1)))
        with self.assertRaises(DonationError):  # ya vencido
            self.s.register_donation(make_lot("X5", received=EVENT, expiry_days=1))

    def test_search_levels(self):
        self.s.register_donation(make_lot("A1", expiry_days=2, hub="H-BOG"))
        near = self.s.search(expiring_within_days=3)
        self.assertIn("A1", [l.lot_id for l in near])
        self.assertTrue(all(l.expiry <= self.s.today + timedelta(days=3) for l in near))
        combo = self.s.search(donor_id="D-001", hub_id="H-BOG", category=Category.VIVERES, expiring_within_days=3)
        self.assertEqual([l.lot_id for l in combo], ["A1"])
        self.assertEqual(self.s.search(category=Category.VIVERES, hub_id="H-NOPE"), [])
        fefo = self.s.search(category=Category.MEDICO)
        self.assertEqual(fefo, sorted(fefo, key=lambda l: (l.shelf_key, l.lot_id)))

    def test_funds_range(self):
        funds = self.s.funds_between(10**9, 10**12)
        self.assertTrue(all(l.is_funds and 10**9 <= l.quantity <= 10**12 for l in funds))
        self.assertEqual(self.s.funds_between(5, 4), [])


class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.s = make_system()

    def test_assigned_lots_are_never_available(self):
        self.s.allocate()
        assigned = [l for l in self.s.lots.values() if l.status is LotStatus.ASSIGNED]
        self.assertTrue(assigned)
        found = {l.lot_id for l in self.s.search()}
        for l in assigned:
            self.assertEqual(l.available, 0)
            self.assertNotIn(l.lot_id, found)
        for l in self.s.lots.values():
            if l.status is LotStatus.AVAILABLE:
                self.assertGreater(l.available, 0)

    def test_inventory_conservation(self):
        self.s.allocate()
        by_cat = {}
        for a in self.s.allocations:
            by_cat[a.category.value] = by_cat.get(a.category.value, 0) + a.quantity
        for row in self.s.stock_balance():
            self.assertEqual(row["received"], row["available"] + row["dispatched"] + row["expired"], row["category"])
            self.assertEqual(by_cat.get(row["category"], 0), row["dispatched"])

    def test_never_over_deliver_and_second_run_keeps_invariants(self):
        self.s.allocate()
        self.s.allocate()
        for m in self.s.munis.values():
            for c in Category:
                self.assertLessEqual(self.s.received(m.muni_id, c), m.need(c))
        for row in self.s.stock_balance():
            self.assertEqual(row["received"], row["available"] + row["dispatched"] + row["expired"])

    def test_isolated_municipalities_get_nothing(self):
        iso = {m.muni_id for m in self.s.isolated_municipalities()}
        self.assertTrue(iso)
        rep = self.s.allocate()
        self.assertTrue(all(a.muni_id not in iso for a in rep.allocations))
        self.assertTrue(any("AISLADO" in why for _, why in rep.unserved))

    def test_priority_most_urgent_served_first_when_scarce(self):
        s = make_system()
        drain(s, Category.REFUGIO)
        s.register_donation(make_lot("SCARCE", cat=Category.REFUGIO, qty=500, hub="H-PEI", expiry_days=None))
        s.allocate()
        iso = {x.muni_id for x in s.isolated_municipalities()}
        got = {m: s.received(m, Category.REFUGIO) for m in s.munis}
        served = [s.munis[m] for m, q in got.items() if q > 0]
        unserved = [m for m in s.munis.values()
                    if m.need(Category.REFUGIO) > 0 and got[m.muni_id] == 0 and m.muni_id not in iso]
        self.assertTrue(served and unserved)
        self.assertGreaterEqual(min(m.urgency for m in served), max(m.urgency for m in unserved))

    def test_fefo_takes_earliest_expiry_first(self):
        s = make_system()
        drain(s, Category.VIVERES)
        s.register_donation(make_lot("LATE", qty=10**9, expiry_days=300, hub="H-PEI"))
        s.register_donation(make_lot("SOON", qty=10**9, expiry_days=10, hub="H-PEI"))
        s.allocate()
        self.assertGreater(s.lots["SOON"].quantity - s.lots["SOON"].available, 0)
        self.assertEqual(s.lots["LATE"].available, s.lots["LATE"].quantity)

    def test_cold_chain_not_sent_over_12_hours(self):
        s = make_system()
        drain(s, Category.MEDICO)
        s.register_donation(make_lot("COLD", cat=Category.MEDICO, qty=10**6, hub="H-BAQ", expiry_days=40, cold=True))
        rep = s.allocate()
        cold = [a for a in rep.allocations if a.lot_id == "COLD"]
        self.assertTrue(all(a.eta_hours <= 12.0 for a in cold))
        self.assertTrue(any("FRÍO" in why for _, why in rep.unserved))

    def test_expiry_removes_lot_from_circulation(self):
        s = make_system()
        s.register_donation(make_lot("EXP", expiry_days=5))
        s.set_today(s.today + timedelta(days=10))
        self.assertEqual(s.get_lot("EXP").status, LotStatus.EXPIRED)
        self.assertNotIn("EXP", [l.lot_id for l in s.search()])
        s.allocate()
        self.assertEqual(s.get_lot("EXP").available, 100)

    def test_closing_road_changes_route(self):
        s = make_system()
        hub, muni = "H-PEI", next(m.muni_id for m in s.munis.values() if m.name == "Pereira")
        cost, path = s.route(hub, muni)
        self.assertLess(cost, float("inf"))
        for a, b in zip(path, path[1:]):
            s.set_road_status(a, b, RoadStatus.CLOSED)
        cost2, _ = s.route(hub, muni)
        self.assertGreaterEqual(cost2, cost)
        with self.assertRaises(DonationError):
            s.set_road_status("H-PEI", "H-BAQ", RoadStatus.CLOSED)

    def test_astar_matches_dijkstra_on_real_network(self):
        s = make_system()
        for m in s.munis.values():
            for h in ("H-BOG", "H-CLO"):
                c1, _ = s.route(h, m.muni_id, "dijkstra")
                c2, _ = s.route(h, m.muni_id, "astar")
                if c1 == float("inf"):
                    self.assertEqual(c2, float("inf"))
                else:
                    self.assertAlmostEqual(c1, c2)


class ConcurrencyTests(unittest.TestCase):
    def test_parallel_registration_and_allocation_keep_inventory_consistent(self):
        s = make_system()
        errors = []

        def reg(t):
            try:
                for i in range(100):
                    s.register_donation(make_lot(f"C{t}-{i}", qty=50 + i, hub="H-PEI", expiry_days=60))
            except Exception as e:  # noqa: BLE001
                errors.append(e)

        threads = [threading.Thread(target=reg, args=(t,)) for t in range(6)]
        threads += [threading.Thread(target=s.allocate) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(sum(1 for k in s.lots if k.startswith("C")), 600)
        for row in s.stock_balance():
            self.assertEqual(row["received"], row["available"] + row["dispatched"] + row["expired"])
        for m in s.munis.values():
            for c in Category:
                self.assertLessEqual(s.received(m.muni_id, c), m.need(c))

    def test_massive_sequential_transactions(self):
        s = make_system()
        for i in range(2000):
            s.register_donation(make_lot(f"B{i}", qty=10, hub="H-BOG", expiry_days=90))
        s.allocate()
        for row in s.stock_balance():
            self.assertEqual(row["received"], row["available"] + row["dispatched"] + row["expired"])


class AlertTests(unittest.TestCase):
    def test_shortage_isolation_and_expiry_alerts(self):
        s = make_system()
        s.register_donation(make_lot("SOONX", expiry_days=3))
        self.assertIn("VENCIMIENTO", {a.kind for a in s.alerts()})
        s.allocate()
        self.assertTrue({"DESABASTECIMIENTO", "AISLAMIENTO"} <= {a.kind for a in s.alerts()})
        self.assertEqual(s.alerts()[0].level, "CRITICO")


class FormTests(unittest.TestCase):
    def setUp(self):
        self.s = make_system()
        self.ok = {"donor_id": "D-001", "hub_id": "H-BOG", "category": "MEDICO", "description": "Kits",
                   "quantity": "10", "weight_kg": "5", "volume_m3": "0.1", "expiry": "2027-01-01"}

    def test_valid(self):
        lot, errs = validate_donation_form(self.s, self.ok)
        self.assertEqual(errs, {})
        self.s.register_donation(lot)

    def test_collects_all_errors(self):
        _, errs = validate_donation_form(self.s, {"donor_id": "x", "hub_id": "", "category": "?", "description": " ",
                                                  "quantity": "-4", "weight_kg": "abc", "volume_m3": "-1",
                                                  "expiry": "ayer"})
        self.assertEqual(set(errs), {"donor_id", "hub_id", "category", "description", "quantity", "weight_kg",
                                     "volume_m3", "expiry"})

    def test_perishable_requires_expiry_and_past_expiry_rejected(self):
        _, e1 = validate_donation_form(self.s, {**self.ok, "expiry": ""})
        self.assertIn("expiry", e1)
        _, e2 = validate_donation_form(self.s, {**self.ok, "expiry": "2026-03-02"})
        self.assertIn("expiry", e2)
        _, e3 = validate_donation_form(self.s, {**self.ok, "quantity": "1.5"})
        self.assertIn("quantity", e3)


if __name__ == "__main__":
    unittest.main()
