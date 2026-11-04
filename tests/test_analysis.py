import unittest

from donaciones import analysis
from tests.helpers import make_system


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.s = make_system()
        self.munis = list(self.s.munis.values())

    def test_totals_match_sum_of_rows(self):
        t = analysis.impact_summary(self.munis)
        self.assertEqual(t["injured"], sum(m.injured for m in self.munis))
        zones = analysis.group_ranking(self.munis, "zone")
        self.assertEqual(sum(z["injured"] for z in zones), t["injured"])
        self.assertEqual(sum(z["municipalities"] for z in zones), len(self.munis))

    def test_zone_ranking_sorted_by_severity(self):
        sev = [z["severity"] for z in analysis.group_ranking(self.munis, "zone")]
        self.assertEqual(sev, sorted(sev, reverse=True))

    def test_top_municipalities(self):
        top = analysis.top_municipalities(self.munis, "injured", 3)
        self.assertEqual(len(top), 3)
        self.assertEqual(top[0].injured, max(m.injured for m in self.munis))

    def test_markdown_contains_answers(self):
        text = analysis.render_markdown(self.s, allocated=False)
        for needle in ("Heridos", "zonas", "incomunicados", "Alertas"):
            self.assertIn(needle, text)


if __name__ == "__main__":
    unittest.main()
