"""The first test case — frameworks/examples/nora-soft-autumn.yaml.

When the engine is applied to these inputs, the output must match this. If it
doesn't, the method is wrong, not the case (and the thresholds are not to be
tuned here to make it pass).
"""
import unittest
from pathlib import Path

import yaml

from engine import colour, generators, horizons, matcher, palette

REPO_ROOT = Path(__file__).resolve().parents[2]
CASE_PATH = REPO_ROOT / "frameworks" / "examples" / "nora-soft-autumn.yaml"

# The slot each known item sits in, and the accessory's near_face flag. The
# test case names the garments; the engine needs the slots.
ITEM_SLOTS = {
    "deep teal knit": ("top", None),
    "black trousers": ("bottom", None),
    "rust scarf": ("accessory", True),
    "pure white shirt": ("top", None),
    "cobalt top": ("top", None),
}

# The three ranked lists over Soft Autumn as reported on 2026-09-14, after the
# Muted generator was added, less the one pair that involved a neutral (warm mid
# grey, relative chroma 0.115, no longer enters the generators — combinations.md
# §5): (dominant, counter, hue gap, ΔL*, Δ relative chroma).
EXPECTED_OPPOSITION = [
    ("petrol", "salmon", 178.1, 31.0, 0.19),
    ("petrol", "cinnamon", 169.3, 16.5, 0.10),
    ("rust", "muted teal", 153.6, 15.3, 0.02),
    ("soft plum", "sage", 145.6, 38.0, 0.13),
    ("petrol", "ochre", 145.4, 28.2, 0.13),
    ("petrol", "mustard", 138.0, 35.3, 0.17),
    ("petrol", "old gold", 137.8, 28.0, 0.02),
    ("deep teal", "ochre", 125.0, 27.1, 0.00),
    ("deep teal", "mustard", 117.7, 34.2, 0.04),
    ("deep teal", "old gold", 117.4, 26.9, 0.11),
    ("soft plum", "cream", 108.5, 62.5, 0.05),
    ("petrol", "moss", 108.4, 19.4, 0.17),
]
EXPECTED_TONAL = [
    ("dark olive", "sage", 4.8, 30.6, 0.20),
    ("camel", "cream", 9.7, 26.3, 0.13),
    ("warm taupe", "cream", 11.5, 28.8, 0.05),
    ("chocolate", "warm taupe", 14.9, 38.0, 0.13),
    ("chocolate", "camel", 16.7, 40.5, 0.05),
    ("chocolate", "salmon", 21.7, 41.8, 0.16),
    ("chocolate", "cream", 26.4, 66.8, 0.08),
    ("chocolate", "dusty rose", 29.5, 42.1, 0.10),
    ("dark olive", "cream", 32.3, 55.1, 0.12),
]
EXPECTED_MUTED = [
    ("soft plum", "dusty rose", 52.6, 37.8, 0.06),
    ("soft plum", "camel", 98.7, 36.2, 0.08),
    ("soft plum", "warm taupe", 97.0, 33.7, 0.10),
    ("dark olive", "dusty rose", 88.2, 30.4, 0.13),
    ("dark olive", "camel", 42.0, 28.8, 0.02),
]


def load_case():
    with open(CASE_PATH) as fh:
        return yaml.safe_load(fh)


class TestColourMaths(unittest.TestCase):
    def test_relative_chroma_worked_note(self):
        # combinations.md §2: deep teal 0.846, ochre 0.850
        for hex_, expected in (("1F5F63", 0.846), ("C7912B", 0.850)):
            L, C, h = colour.lab_to_lch(colour.hex_to_lab(hex_))
            self.assertAlmostEqual(colour.relative_chroma(L, C, h), expected, places=3)

    def test_delta_e_identity(self):
        self.assertAlmostEqual(colour.delta_e_2000(colour.hex_to_lab("1F5F63"), colour.hex_to_lab("1F5F63")), 0.0)


class TestNoraSeason(unittest.TestCase):
    def setUp(self):
        self.case = load_case()
        self.expected = self.case["expected_result"]

    def test_primary_season_exists_with_direction(self):
        season = palette.get_season(self.expected["primary_season"])
        self.assertIn(self.expected["direction"], season.directions)
        self.assertEqual(season.primary, "soft")
        self.assertEqual(season.secondary, "warm")

    def test_runner_up_season(self):
        confidence = {ax: v["confidence"] for ax, v in self.case["expected_axes"].items()}
        runner = palette.runner_up(self.expected["primary_season"], confidence)
        self.assertEqual(runner["season"], self.expected["secondary_season"])
        self.assertEqual(runner["axis"], "temperature")

    def test_tier_proportions(self):
        self.assertEqual(palette.TIER_SHARE, self.expected["tier_proportions"])


class TestNoraVerdicts(unittest.TestCase):
    def setUp(self):
        self.case = load_case()
        self.season = palette.get_season(self.case["expected_result"]["primary_season"])

    def test_every_expected_verdict(self):
        for row in self.case["known_items_and_expected_verdicts"]:
            slot, near_face = ITEM_SLOTS[row["item"]]
            item = {"id": row["item"], "hex": row["hex"], "slot": slot}
            if near_face is not None:
                item["near_face"] = near_face
            with self.subTest(item=row["item"]):
                r = matcher.score_item(item, self.season)
                self.assertEqual(r["verdict"], row["expected"], r)
                self.assertEqual(r["nearest"], row["nearest"], r)


class TestNoraCombinations(unittest.TestCase):
    def setUp(self):
        self.season = palette.get_season("soft_autumn")
        self.lists = generators.run(self.season.anchors)

    def test_named_pairs_land_in_their_generators(self):
        for a, b, gen in (("deep teal", "ochre", "opposition"),
                          ("petrol", "cinnamon", "opposition"),
                          ("dark olive", "dusty rose", "muted")):
            with self.subTest(pair=(a, b)):
                found = generators.find_pair(self.lists, a, b)
                self.assertIsNotNone(found, f"{a} / {b} not produced by any generator")
                self.assertEqual(found[0], gen)

    def test_plum_and_old_gold_is_produced_by_none(self):
        self.assertIsNone(generators.find_pair(self.lists, "soft plum", "old gold"))

    def _check_list(self, name, expected):
        got = [(p.dominant.name, p.counter.name, round(p.hue_gap, 1), round(p.delta_L, 1), round(p.delta_rel, 2))
               for p in self.lists[name]]
        self.assertEqual(got, expected)

    def test_opposition_ranked_list(self):
        self._check_list("opposition", EXPECTED_OPPOSITION)

    def test_tonal_ranked_list(self):
        self._check_list("tonal", EXPECTED_TONAL)

    def test_muted_ranked_list(self):
        self._check_list("muted", EXPECTED_MUTED)

    def test_direction_reweighting_puts_teal_first(self):
        out = generators.generate(self.season.anchors, direction_anchor="deep teal")
        self.assertIn("deep teal", out["lists"]["opposition"][0].names)
        self.assertEqual(out["order"], ["opposition", "tonal", "muted"])

    def test_calm_mood_promotes_tonal_and_muted(self):
        out = generators.generate(self.season.anchors, mood=self.setUp_mood())
        self.assertEqual(out["order"], ["tonal", "muted", "opposition"])

    def setUp_mood(self):
        return load_case()["inputs"]["questions"]["wants_to_feel"]


class TestNoraHorizons(unittest.TestCase):
    def test_full_result_runs_on_the_known_items(self):
        case = load_case()
        items = []
        for row in case["known_items_and_expected_verdicts"]:
            slot, near_face = ITEM_SLOTS[row["item"]]
            item = {"id": row["item"], "hex": row["hex"], "slot": slot}
            if near_face is not None:
                item["near_face"] = near_face
            items.append(item)
        confidence = {ax: v["confidence"] for ax, v in case["expected_axes"].items()}
        r = horizons.result("soft_autumn", "teal_ochre", items,
                            mood=case["inputs"]["questions"]["wants_to_feel"], confidence=confidence)
        self.assertEqual(r["long_term"]["runner_up"]["season"], "soft_summer")
        self.assertEqual(r["long_term"]["generator_order"], ["tonal", "muted", "opposition"])
        self.assertEqual(set(r["slots"]), set(matcher.SLOTS))
        self.assertIn("palette_distance", r["short_term"]["distance"])
        # deep teal knit + black trousers make a works-now core pair
        self.assertTrue(any(o["core_pair"] == ["deep teal knit", "black trousers"]
                            for o in r["short_term"]["works_now"]))


if __name__ == "__main__":
    unittest.main()
