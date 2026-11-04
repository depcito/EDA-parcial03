import unittest

from tests.helpers import make_system

try:
    import tkinter as tk
    from donaciones.gui import App
    tk.Tk().destroy()
    HAS_DISPLAY = True
except Exception:  # noqa: BLE001
    HAS_DISPLAY = False


@unittest.skipUnless(HAS_DISPLAY, "sin entorno gráfico")
class GuiTests(unittest.TestCase):
    def setUp(self):
        self.app = App(make_system())
        self.app.update()

    def tearDown(self):
        self.app.destroy()

    def pump(self, until, tries=400):
        for _ in range(tries):
            self.app.update()
            if until():
                return True
            self.app.after(10)
        return False

    def test_dashboard_populated(self):
        self.assertNotEqual(self.app.kpis["injured"].get(), "-")
        self.assertGreater(len(self.app.alert_tv.get_children()), 0)

    def test_allocation_runs_async_and_updates_tables(self):
        self.app.run_allocation()
        self.assertTrue(self.pump(lambda: "asignaciones" in self.app.disp_msg.get()))
        self.assertGreater(len(self.app.disp_tv.get_children()), 0)
        self.assertGreater(len(self.app.unserved_tv.get_children()), 0)

    def test_invalid_form_shows_visual_errors(self):
        self.app.form_vars["quantity"].set("-5")
        self.app.submit_donation()
        self.assertIn("Cantidad", self.app.form_err["quantity"].cget("text"))
        self.assertIn("Corrija", self.app.form_msg.get())

    def test_valid_form_registers(self):
        v = self.app.form_vars
        v["donor_id"].set("D-001 · x")
        v["hub_id"].set("H-BOG")
        v["category"].set("REFUGIO")
        v["description"].set("Carpas")
        v["quantity"].set("20")
        n = len(self.app.system.lots)
        self.app.submit_donation()
        self.assertEqual(len(self.app.system.lots), n + 1)

    def test_bad_inventory_filter_is_flagged(self):
        self.app.inv_days.insert(0, "abc")
        self.app.search_inventory()
        self.assertIn("entero", self.app.status.get())

    def test_route_and_unreachable_message(self):
        self.app.route_hub.set("H-PEI")
        self.app.route_muni.set("Circasia")
        self.app.compute_route()
        self.assertIn("puente aéreo", self.app.route_msg.get())
        self.app.route_muni.set("Pereira")
        self.app.compute_route()
        self.assertIn("tramos", self.app.route_msg.get())

    def test_concurrent_events_do_not_block(self):
        self.app.run_allocation()
        self.app.run_analysis()
        self.app.search_inventory()
        self.assertTrue(self.pump(lambda: len(self.app.an_text.get("1.0", "end").strip()) > 20))


if __name__ == "__main__":
    unittest.main()
