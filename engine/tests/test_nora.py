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


class TestNoraOutfits(unittest.TestCase):
    """The three example outfits in engine/examples/nora-outfits.csv: the zone
    and weather flags they must raise, and the unlock counts on ranked gaps."""

    @classmethod
    def setUpClass(cls):
        from engine import run
        cls.items = run.load_items(REPO_ROOT / "engine" / "examples" / "nora-items.csv")
        cls.outfits = run.load_outfits(REPO_ROOT / "engine" / "examples" / "nora-outfits.csv", cls.items)
        cls.result = horizons.result("soft_autumn", "teal_ochre", cls.items, outfits=cls.outfits)
        cls.by_name = {o["name"]: o for o in cls.result["outfits"]}

    def test_items_carry_the_two_attributes_and_the_layer_slot_exists(self):
        self.assertEqual(len(self.items), 5)  # the template's blank hint rows are skipped
        self.assertEqual({i["dressiness"] for i in self.items}, {2, 3})
        self.assertIn("layer", matcher.SLOTS)
        self.assertNotIn("layer", matcher.COVERAGE_SLOTS)

    def test_work_tuesday_raises_no_zone_or_weather_flag(self):
        o = self.by_name["work Tuesday"]
        self.assertEqual(o["checks"]["zone"]["flags"], [])
        self.assertIsNone(o["checks"]["weather"]["flag"])

    def test_dinner_in_rain_without_a_layer_is_not_enough_for_rain(self):
        o = self.by_name["dinner with friends"]
        self.assertEqual(o["checks"]["weather"]["flag"], "not enough for rain")
        self.assertFalse(o["checks"]["weather"]["layer_present"])
        self.assertEqual(o["checks"]["zone"]["flags"], [])
        self.assertFalse(o["passes"])

    def test_work_into_evening_is_flagged_twice(self):
        o = self.by_name["work into evening"]
        # once as a hard miss at the face (the white shirt) ...
        top = o["slots"]["top"]
        self.assertEqual(top["item_id"], "pure white shirt")
        self.assertEqual(top["verdict"], "hard_miss")
        self.assertEqual(top["where"], "at the face")
        # ... and once as too casual for the occasion (the rust scarf, dressiness 2 against dress code 4)
        flags = {(z["item_id"], z["flag"]) for z in o["checks"]["zone"]["flags"]}
        self.assertEqual(flags, {("rust scarf", "too casual")})
        self.assertFalse(o["passes"])

    def test_ranked_gaps_carry_unlock_counts(self):
        gaps = {(g["type"], g.get("slot"), g.get("item_id")): g for g in self.result["gaps_ranked"]}
        self.assertEqual(gaps[("empty_slot", "shoes", None)]["unlocks"], 3)
        self.assertEqual(gaps[("empty_slot", "bag", None)]["unlocks"], 3)
        self.assertEqual(gaps[("hard_miss", "top", "pure white shirt")]["unlocks"], 1)
        self.assertEqual(gaps[("too_casual", "accessory", "rust scarf")]["unlocks"], 1)
        self.assertEqual(gaps[("not_enough_for_rain", "layer", None)]["unlocks"], 1)
        zone = gaps[("zone_gap", "accessory", None)]
        self.assertEqual(zone["flag"], "no accessory dressy enough for work into evening")
        self.assertEqual(zone["unlocks"], 1)
        # the two three-outfit gaps rank first
        self.assertEqual([g["unlocks"] for g in self.result["gaps_ranked"][:2]], [3, 3])
        # the layer is never a coverage gap
        self.assertNotIn(("empty_slot", "layer", None), gaps)

    def test_missing_list_needs_ten_items(self):
        miss = self.result["short_term"]["missing"]
        self.assertIsNone(miss["anchors"])
        self.assertEqual(miss["note"], horizons.NOT_ENOUGH_ITEMS)


class TestLayerYieldsTheFace(unittest.TestCase):
    """matching.md §2: a layer is a face position unless the outfit has an
    in-palette near-face accessory — then the accessory is the face colour."""

    def setUp(self):
        self.season = palette.get_season("soft_autumn")
        self.coat = {"id": "black coat", "hex": "000000", "slot": "layer"}
        self.scarf = {"id": "rust scarf", "hex": "A6502F", "slot": "accessory", "near_face": True}

    def test_black_coat_alone_is_out(self):
        r = matcher.score_item(self.coat, self.season)
        self.assertEqual((r["verdict"], r["where"]), ("out", "at the face"))
        o = matcher.score_outfits([{"name": "coat only", "items": [self.coat]}], self.season, [self.coat])["outfits"][0]
        self.assertEqual(o["slots"]["layer"]["verdict"], "out")
        self.assertIsNone(o["face_colour"])

    def test_black_coat_with_the_rust_scarf_is_in(self):
        items = [self.coat, self.scarf]
        o = matcher.score_outfits([{"name": "coat and scarf", "items": items}], self.season, items)["outfits"][0]
        layer = o["slots"]["layer"]
        self.assertEqual(layer["verdict"], "in")
        self.assertEqual(layer["nearest"], "black (away from face)")
        self.assertEqual(layer["where"], "away from the face")
        self.assertEqual(o["face_colour"], "rust scarf")
        self.assertEqual(o["slots"]["accessory"]["verdict"], "in")

    def test_an_out_of_palette_scarf_does_not_take_the_face(self):
        cobalt_scarf = {"id": "cobalt scarf", "hex": "0047FF", "slot": "accessory", "near_face": True}
        items = [self.coat, cobalt_scarf]
        o = matcher.score_outfits([{"name": "coat and cobalt", "items": items}], self.season, items)["outfits"][0]
        self.assertEqual(o["slots"]["layer"]["verdict"], "out")
        self.assertIsNone(o["face_colour"])


class TestPhotoIntake(unittest.TestCase):
    """engine/intake.py on two generated images: a solid deep-teal rectangle on
    a white background, and the same rectangle as a transparent PNG. Both must
    come back within ΔE 3 of deep teal's hex."""

    TEAL = (0x1F, 0x5F, 0x63)

    @classmethod
    def setUpClass(cls):
        import tempfile
        from PIL import Image
        cls.tmp = tempfile.TemporaryDirectory()
        folder = Path(cls.tmp.name)
        # a) opaque: white 300x300 with a 160x160 teal rectangle in the middle
        im = Image.new("RGB", (300, 300), (255, 255, 255))
        for y in range(70, 230):
            for x in range(70, 230):
                im.putpixel((x, y), cls.TEAL)
        im.save(folder / "top_deep-teal-knit.png")
        im.save(folder / "top_deep-teal-knit-jpeg.jpg", quality=95)
        # b) transparent cutout: the same rectangle, everything else alpha 0
        cut = Image.new("RGBA", (300, 300), (0, 0, 0, 0))
        for y in range(70, 230):
            for x in range(70, 230):
                cut.putpixel((x, y), cls.TEAL + (255,))
        cut.save(folder / "accessory_deep-teal-cutout.png")
        # c) an unknown slot prefix
        im.save(folder / "hat_deep-teal.png")
        from engine import intake
        cls.out = intake.run_folder(folder)
        cls.by_file = {it["file"]: it for it in cls.out["items"]}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _assert_teal(self, item):
        de = colour.delta_e_2000(colour.hex_to_lab(item["hex"]), colour.srgb_to_lab(self.TEAL))
        self.assertLessEqual(de, 3.0, f'{item["file"]}: {item["hex"]} is ΔE {de:.1f} from deep teal')

    def test_opaque_rectangle_on_white(self):
        it = self.by_file["top_deep-teal-knit.png"]
        self.assertEqual(it["mode"], "background")
        self.assertEqual(it["background"], "FFFFFF")
        self._assert_teal(it)

    def test_opaque_rectangle_as_jpeg(self):
        self._assert_teal(self.by_file["top_deep-teal-knit-jpeg.jpg"])

    def test_transparent_cutout(self):
        it = self.by_file["accessory_deep-teal-cutout.png"]
        self.assertEqual(it["mode"], "alpha")
        self._assert_teal(it)

    def test_filename_gives_slot_and_name(self):
        it = self.by_file["top_deep-teal-knit.png"]
        self.assertEqual((it["slot"], it["name"]), ("top", "deep teal knit"))

    def test_unknown_slot_is_a_warning_not_a_guess(self):
        it = self.by_file["hat_deep-teal.png"]
        self.assertIsNone(it["slot"])
        self.assertTrue(any("hat_deep-teal.png" in w for w in self.out["warnings"]))

    def test_csv_and_contact_sheet_are_written(self):
        import csv as _csv
        with open(self.out["csv"], newline="") as fh:
            rows = list(_csv.DictReader(fh))
        self.assertEqual(rows[0].keys() if rows else None, rows[0].keys())
        self.assertEqual(list(rows[0].keys()), ["name", "slot", "hex", "dressiness", "weight", "near_face", "notes"])
        by_name = {r["name"]: r for r in rows}
        self.assertEqual(by_name["deep teal knit"]["slot"], "top")
        self.assertEqual(by_name["deep teal knit"]["dressiness"], "")
        self.assertEqual(by_name["deep teal"]["slot"], "")   # the hat: slot left blank
        self.assertTrue(Path(self.out["sheet"]).read_text().count("<img") == 4)
