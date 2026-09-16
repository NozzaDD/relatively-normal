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
        # five example outfits, none with shoes or a bag
        self.assertEqual(gaps[("empty_slot", "shoes", None)]["unlocks"], 5)
        self.assertEqual(gaps[("empty_slot", "bag", None)]["unlocks"], 5)
        self.assertEqual(gaps[("hard_miss", "top", "pure white shirt")]["unlocks"], 1)
        self.assertEqual(gaps[("too_casual", "accessory", "rust scarf")]["unlocks"], 1)
        self.assertEqual(gaps[("not_enough_for_rain", "layer", None)]["unlocks"], 1)
        zone = gaps[("zone_gap", "accessory", None)]
        self.assertEqual(zone["flag"], "no accessory dressy enough for work into evening")
        self.assertEqual(zone["unlocks"], 1)
        # the two five-outfit gaps rank first
        self.assertEqual([g["unlocks"] for g in self.result["gaps_ranked"][:2]], [5, 5])
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
        # c) an unknown slot prefix (hat_ is a worksheet category now, so not that)
        im.save(folder / "cardigan_deep-teal.png")
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
        it = self.by_file["cardigan_deep-teal.png"]
        self.assertIsNone(it["slot"])
        self.assertTrue(any("cardigan_deep-teal.png" in w for w in self.out["warnings"]))

    def test_csv_and_contact_sheet_are_written(self):
        import csv as _csv
        with open(self.out["csv"], newline="") as fh:
            rows = list(_csv.DictReader(fh))
        self.assertEqual(rows[0].keys() if rows else None, rows[0].keys())
        self.assertEqual(list(rows[0].keys()), ["name", "slot", "hex", "dressiness", "weight", "near_face",
                                                "fibre", "surface", "notes"])
        by_name = {r["name"]: r for r in rows}
        self.assertEqual(by_name["deep teal knit"]["slot"], "top")
        self.assertEqual(by_name["deep teal knit"]["dressiness"], "")
        self.assertEqual(by_name["deep teal"]["slot"], "")   # the cardigan: slot left blank
        self.assertTrue(Path(self.out["sheet"]).read_text().count("<img") == 4)


class TestCorporateContext(unittest.TestCase):
    """The two corporate example outfits: not-corporate flags by setting, and
    the context gaps per corporate occasion."""

    @classmethod
    def setUpClass(cls):
        from engine import run
        cls.items = run.load_items(REPO_ROOT / "engine" / "examples" / "nora-items.csv")
        cls.outfits = run.load_outfits(REPO_ROOT / "engine" / "examples" / "nora-outfits.csv", cls.items)
        cls.result = horizons.result("soft_autumn", "teal_ochre", cls.items, outfits=cls.outfits)
        cls.by_name = {o["name"]: o for o in cls.result["outfits"]}

    def test_soft_autumn_corporate_list_is_the_owners(self):
        season = palette.get_season("soft_autumn")
        self.assertEqual(season.corporate, ["deep teal", "petrol", "chocolate", "dark olive",
                                            "warm mid grey", "cream", "soft plum", "black",
                                            "warm charcoal", "stone"])
        self.assertIsNotNone(season.find("warm charcoal"))
        self.assertIsNotNone(season.find("stone"))

    def test_loader_defaults_and_values(self):
        by = {o["name"]: o for o in self.outfits}
        self.assertEqual((by["client meeting"]["formality"], by["client meeting"]["setting"]), ("corporate", "office"))
        self.assertEqual((by["video call"]["formality"], by["video call"]["setting"]), ("corporate", "home"))
        self.assertEqual((by["work Tuesday"]["formality"], by["work Tuesday"]["setting"]), ("casual", "office"))
        blank = {"outfit": "x", "occasion": "", "dress_code": "", "weather": "", "formality": "", "setting": ""}
        from engine import run
        import csv, io
        text = "outfit,occasion,dress_code,weather,formality,setting,top,bottom,layer,shoes,bag,accessory\nblank,,,,,,deep teal knit,,,,,\n"
        import tempfile, os
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
            fh.write(text); path = fh.name
        try:
            o = run.load_outfits(path, self.items)[0]
        finally:
            os.unlink(path)
        self.assertEqual((o["formality"], o["setting"]), ("casual", "office"))

    def test_casual_outfits_are_not_context_checked(self):
        self.assertFalse(self.by_name["work Tuesday"]["checks"]["context"]["checked"])
        self.assertEqual(self.by_name["work Tuesday"]["checks"]["context"]["flags"], [])

    def test_corporate_in_the_office_checks_every_slot(self):
        o = self.by_name["client meeting"]
        ctx = o["checks"]["context"]
        self.assertEqual(ctx["face_visible"], list(matcher.SLOTS))
        flags = {(f["item_id"], f["flag"]) for f in ctx["flags"]}
        # rust is accent-only in that context; black is on every corporate list
        self.assertEqual(flags, {("rust scarf", "not corporate")})
        self.assertFalse(o["passes"])

    def test_corporate_at_home_checks_only_what_the_camera_sees(self):
        o = self.by_name["video call"]
        ctx = o["checks"]["context"]
        self.assertEqual(ctx["face_visible"], ["top", "dress", "layer", "accessory"])
        flags = {(f["item_id"], f["flag"]) for f in ctx["flags"]}
        self.assertEqual(flags, {("rust scarf", "not corporate")})   # the trousers are below the camera
        self.assertFalse(o["passes"])

    def test_context_gaps_per_corporate_occasion(self):
        gaps = {(g["type"], g.get("slot"), g.get("occasion")): g for g in self.result["gaps_ranked"]}
        self.assertEqual(gaps[("context_gap", "accessory", "client meeting")]["flag"], "no corporate accessory for client meeting")
        self.assertNotIn(("context_gap", "bottom", "client meeting"), gaps)  # black trousers are corporate
        self.assertEqual(gaps[("context_gap", "accessory", "video call")]["unlocks"], 1)
        self.assertNotIn(("context_gap", "bottom", "video call"), gaps)   # bottom is not face-visible at home
        self.assertNotIn(("context_gap", "top", "client meeting"), gaps)  # the teal knit is corporate

    def test_context_gap_ranks_above_zone_gap_at_equal_unlocks(self):
        types = [g["type"] for g in self.result["gaps_ranked"] if g["unlocks"] == 1]
        self.assertLess(types.index("context_gap"), types.index("zone_gap"))
        self.assertLess(matcher.GAP_SEVERITY["context_gap"], matcher.GAP_SEVERITY["zone_gap"])


class TestDressSlot(unittest.TestCase):
    """The dress slot: coverage, the separates warning, and the face rules."""

    def setUp(self):
        self.season = palette.get_season("soft_autumn")
        self.dress = {"id": "black dress", "hex": "000000", "slot": "dress"}
        self.teal = {"id": "deep teal knit", "hex": "1F5F63", "slot": "top"}
        self.scarf = {"id": "rust scarf", "hex": "A6502F", "slot": "accessory", "near_face": True}

    def _outfit(self, items, name="o"):
        return matcher.score_outfits([{"name": name, "items": items}], self.season, items)["outfits"][0]

    def test_a_dress_alone_completes_top_and_bottom(self):
        o = self._outfit([self.dress])
        self.assertEqual(o["checks"]["coverage"]["missing"], ["shoes", "bag", "accessory"])
        self.assertEqual(o["checks"]["warnings"], [])
        self.assertIn("dress", matcher.SLOTS)
        self.assertEqual(matcher.BODY_WEIGHT["dress"], 4)

    def test_a_dress_with_a_top_is_warned_not_failed(self):
        teal_dress = {"id": "teal dress", "hex": "1F5F63", "slot": "dress"}
        stone_top = {"id": "stone tee", "hex": "D6CEC2", "slot": "top"}   # a neutral, so the pair is valid
        o = self._outfit([teal_dress, stone_top])
        self.assertEqual(o["checks"]["warnings"], ["dress plus separates"])
        self.assertNotIn("top", o["checks"]["coverage"]["missing"])
        self.assertTrue(o["pairing"]["valid"])
        self.assertTrue(o["passes"])
        self.assertFalse(any(g["type"] == "dress_plus_separates" for g in o["gaps"]))

    def test_black_dress_alone_is_out(self):
        r = matcher.score_item(self.dress, self.season)
        self.assertEqual((r["verdict"], r["where"]), ("out", "at the face"))
        o = self._outfit([self.dress])
        self.assertEqual(o["slots"]["dress"]["verdict"], "out")

    def test_black_dress_with_the_rust_scarf_is_in(self):
        o = self._outfit([self.dress, self.scarf])
        d = o["slots"]["dress"]
        self.assertEqual((d["verdict"], d["nearest"], d["where"]), ("in", "black (away from face)", "away from the face"))
        self.assertEqual(o["face_colour"], "rust scarf")
        self.assertEqual(o["checks"]["coverage"]["missing"], ["shoes", "bag"])


class TestWorksheetPrefixes(unittest.TestCase):
    """jewellery_ -> accessory with near_face false; scarf_ and hat_ -> true;
    dress_ -> the dress slot."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        from PIL import Image
        from engine import intake
        cls.tmp = tempfile.TemporaryDirectory()
        folder = Path(cls.tmp.name)
        for name in ("jewellery_gold-hoops.png", "scarf_rust-scarf.png", "hat_camel-beret.png", "dress_teal-dress.png"):
            im = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
            for y in range(20, 100):
                for x in range(20, 100):
                    im.putpixel((x, y), (0xA6, 0x50, 0x2F, 255))
            im.save(folder / name)
        cls.out = intake.run_folder(folder)
        cls.by_file = {it["file"]: it for it in cls.out["items"]}
        import csv
        with open(cls.out["csv"], newline="") as fh:
            cls.rows = {r["name"]: r for r in csv.DictReader(fh)}

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_jewellery_is_hardware(self):
        it = self.by_file["jewellery_gold-hoops.png"]
        self.assertEqual((it["slot"], it["near_face"]), ("accessory", False))
        self.assertEqual(self.rows["gold hoops"]["near_face"], "false")

    def test_scarf_and_hat_are_near_face(self):
        for f in ("scarf_rust-scarf.png", "hat_camel-beret.png"):
            with self.subTest(file=f):
                self.assertEqual((self.by_file[f]["slot"], self.by_file[f]["near_face"]), ("accessory", True))
        self.assertEqual(self.rows["rust scarf"]["near_face"], "true")

    def test_dress_prefix(self):
        self.assertEqual((self.by_file["dress_teal-dress.png"]["slot"], self.by_file["dress_teal-dress.png"]["near_face"]), ("dress", None))
        self.assertEqual(self.out["warnings"], [])

    def test_loader_reads_the_written_flags(self):
        from engine import run
        items = {i["id"]: i for i in run.load_items(self.out["csv"])}
        self.assertIs(items["gold hoops"]["near_face"], False)
        self.assertIs(items["rust scarf"]["near_face"], True)
        self.assertNotIn("near_face", items["teal dress"])


class TestMonochromePairing(unittest.TestCase):
    """combinations.md §5 — two chromatic items within ΔE 12 of each other are
    valid as monochrome, regardless of the generators, when both are in
    palette."""

    def setUp(self):
        self.season = palette.get_season("soft_autumn")
        self.dress = {"id": "teal dress", "hex": "1F5F63", "slot": "dress"}
        self.top = {"id": "teal top", "hex": "1F5F63", "slot": "top"}

    def _outfit(self, items):
        return matcher.score_outfits([{"name": "o", "items": items}], self.season, items)["outfits"][0]

    def test_teal_dress_plus_teal_top_is_monochrome_and_still_warned(self):
        o = self._outfit([self.dress, self.top])
        self.assertTrue(o["pairing"]["valid"])
        self.assertTrue(o["passes"])
        self.assertEqual(o["checks"]["warnings"], ["dress plus separates"])
        a, b = matcher.score_item(self.dress, self.season), matcher.score_item(self.top, self.season)
        v = matcher.pair_valid(a, b, [])          # no generated pairs at all: monochrome still holds
        self.assertEqual((v["kind"], v["valid"], v["generator"]), ("monochrome", True, "monochrome"))
        self.assertEqual(v["delta_e"], 0.0)

    def test_a_near_neighbour_inside_delta_e_12_is_monochrome(self):
        petrol = {"id": "petrol top", "hex": "2C5A66", "slot": "top"}   # ΔE ~7 from deep teal
        v = matcher.pair_valid(matcher.score_item(self.dress, self.season),
                               matcher.score_item(petrol, self.season), [])
        self.assertEqual(v["kind"], "monochrome")
        self.assertLessEqual(v["delta_e"], matcher.MONOCHROME_DE)

    def test_out_of_palette_twins_are_not_monochrome(self):
        cobalt_a = {"id": "cobalt top", "hex": "0047FF", "slot": "top"}
        cobalt_b = {"id": "cobalt dress", "hex": "0047FF", "slot": "dress"}
        v = matcher.pair_valid(matcher.score_item(cobalt_a, self.season),
                               matcher.score_item(cobalt_b, self.season), [])
        self.assertEqual(v["kind"], "chromatic+chromatic")   # both are out; the rule needs in-palette
        self.assertFalse(v["valid"])

    def test_a_far_pair_still_needs_a_generator(self):
        ochre = {"id": "ochre top", "hex": "C7912B", "slot": "top"}
        v = matcher.pair_valid(matcher.score_item(self.dress, self.season),
                               matcher.score_item(ochre, self.season), [])
        self.assertEqual(v["kind"], "chromatic+chromatic")
        self.assertFalse(v["valid"])


class TestWorksNowRanking(unittest.TestCase):
    """horizons.md §3c — works-now is ranked by pairing kind first. The closet
    below is tops and bottoms only, so every outfit uses exactly two items and
    the kind ordering is the only thing separating them."""

    CLOSET = [
        # tops
        {"id": "teal knit", "hex": "1F5F63", "slot": "top"},        # chromatic
        {"id": "rose blouse", "hex": "C09A93", "slot": "top"},      # chromatic
        {"id": "sage shirt", "hex": "9AA88B", "slot": "top"},       # chromatic
        {"id": "stone tee", "hex": "D6CEC2", "slot": "top"},        # neutral
        # bottoms
        {"id": "ochre skirt", "hex": "C7912B", "slot": "bottom"},   # opposition with teal
        {"id": "olive trouser", "hex": "4E5A3A", "slot": "bottom"}, # muted with rose, tonal with sage
        {"id": "petrol jean", "hex": "2C5A66", "slot": "bottom"},   # monochrome with teal
        {"id": "grey trouser", "hex": "8B8378", "slot": "bottom"},  # neutral
        {"id": "charcoal trouser", "hex": "3A3632", "slot": "bottom"},  # neutral
    ]

    @classmethod
    def setUpClass(cls):
        cls.season = palette.get_season("soft_autumn")
        cls.scored = matcher.score_items(cls.CLOSET, cls.season)
        cls.gen_lists = generators.run(cls.season.anchors)

    def _kinds(self, mood=None):
        out = horizons.works_now_generated(self.scored, self.gen_lists, mood=mood)
        seen = []
        for o in out:
            if o["kind"] not in seen:
                seen.append(o["kind"])
        return out, seen

    def test_the_closet_produces_every_kind(self):
        _, seen = self._kinds()
        self.assertEqual(set(seen), set(horizons.WORKS_NOW_ORDER),
                         "the fixture must produce one outfit of each kind")

    def test_default_order_is_opposition_first_monochrome_fourth(self):
        out, seen = self._kinds()
        self.assertEqual(seen, list(horizons.WORKS_NOW_ORDER))
        self.assertEqual(out[0]["kind"], "opposition")
        self.assertEqual({"teal knit", "ochre skirt"}, set(out[0]["items"]))
        # every outfit uses two items, so kind alone decides the order
        self.assertEqual({len(o["items"]) for o in out}, {2})

    def test_calm_promotes_tonal_and_monochrome_above_opposition(self):
        out, seen = self._kinds(mood="calm, put together, not trying")
        self.assertEqual(seen, list(horizons.WORKS_NOW_ORDER_CALM))
        self.assertEqual(out[0]["kind"], "tonal")
        self.assertLess(seen.index("tonal"), seen.index("opposition"))
        self.assertLess(seen.index("monochrome"), seen.index("opposition"))
        self.assertLess(seen.index("muted"), seen.index("opposition"))

    def test_items_used_breaks_ties_within_a_kind(self):
        closet = self.CLOSET + [{"id": "rust scarf", "hex": "A6502F", "slot": "accessory", "near_face": True}]
        scored = matcher.score_items(closet, self.season)
        out = horizons.works_now_generated(scored, self.gen_lists)
        opposition = [o for o in out if o["kind"] == "opposition"]
        self.assertEqual([len(o["items"]) for o in opposition],
                         sorted((len(o["items"]) for o in opposition), reverse=True))

    def test_a_dress_alone_has_no_kind_and_sorts_last(self):
        closet = self.CLOSET + [{"id": "teal dress", "hex": "1F5F63", "slot": "dress"}]
        scored = matcher.score_items(closet, self.season)
        out = horizons.works_now_generated(scored, self.gen_lists)
        dress_only = [o for o in out if o["items"] == ["teal dress"]]
        self.assertEqual(len(dress_only), 1)
        self.assertIsNone(dress_only[0]["kind"])
        self.assertIs(out[-1], dress_only[0])


SA = lambda: palette.get_season("soft_autumn")


def _outfit(items, season=None, **spec):
    season = season or SA()
    spec = {"name": spec.pop("name", "o"), "items": items, **spec}
    return matcher.score_outfits([spec], season, items)["outfits"][0]


class TestDenimByFibre(unittest.TestCase):
    """Decision 1 — denim is identified by the declared fibre, never by colour."""

    def setUp(self):
        self.season = SA()

    def test_every_season_admits_denim_below_the_waist(self):
        for key, s in palette.load_seasons().items():
            with self.subTest(season=key):
                self.assertEqual(s.denim, "admitted_below_waist")
                self.assertEqual(s.rules()["denim"], "admitted_below_waist")

    def test_below_the_waist_any_wash_is_in(self):
        for name, hexv in (("raw indigo", "1F2E4A"), ("mid wash", "5C7A9E"), ("light wash", "8FA9C4")):
            r = matcher.score_item({"id": name, "hex": hexv, "slot": "bottom", "fibre": "denim"}, self.season)
            with self.subTest(wash=name):
                self.assertEqual((r["verdict"], r["nearest"], r["stage"]), ("in", "denim (below waist)", 1))

    def test_at_the_face_the_wash_decides(self):
        dark = matcher.score_item({"id": "dark", "hex": "2A3C5B", "slot": "top", "fibre": "denim"}, self.season)
        light = matcher.score_item({"id": "light", "hex": "8FA9C4", "slot": "top", "fibre": "denim"}, self.season)
        self.assertEqual((dark["verdict"], dark["nearest"]), ("in", "denim (dark wash)"))
        self.assertEqual(light["verdict"], "out")
        # the boundary is L* 45
        self.assertLess(colour.lab_to_lch(colour.hex_to_lab("2A3C5B"))[0], matcher.DENIM_FACE_L)
        self.assertGreater(colour.lab_to_lch(colour.hex_to_lab("8FA9C4"))[0], matcher.DENIM_FACE_L)

    def test_colour_alone_never_applies_the_rule(self):
        """The slate blue case: a True Summer foundation that looks like denim."""
        slate = {"id": "slate blue top", "hex": "5E6F8C", "slot": "top"}
        self.assertTrue(matcher.looks_like_denim(slate["hex"]), "the hint should fire on this colour")
        ts = palette.get_season("true_summer")
        r = matcher.score_item(slate, ts)
        self.assertEqual(r["stage"], 3)                      # scored against the palette, not the denim rule
        self.assertEqual((r["verdict"], r["nearest"]), ("in", "slate blue"))

    def test_the_intake_hint_proposes_but_leaves_fibre_blank(self):
        import csv as _csv
        import tempfile
        from PIL import Image
        from engine import intake
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            im = Image.new("RGBA", (120, 120), (0, 0, 0, 0))
            for y in range(20, 100):
                for x in range(20, 100):
                    im.putpixel((x, y), (0x5C, 0x7A, 0x9E, 255))      # mid-wash blue
            im.save(folder / "bottom_blue-jeans.png")
            out = intake.run_folder(folder)
            item = out["items"][0]
            self.assertTrue(item["denim_hint"])
            self.assertTrue(any("set fibre: denim" in w for w in out["warnings"]))
            with open(out["csv"], newline="") as fh:
                row = list(_csv.DictReader(fh))[0]
            self.assertEqual(row["fibre"], "")                        # never written, so never applied
            self.assertIn("looks like denim", row["notes"])


class TestBaseSlot(unittest.TestCase):
    """Decision 2 — a base is judged only when nothing covers it."""

    def setUp(self):
        self.season = SA()
        self.base = {"id": "magenta slip", "hex": "FF00FF", "slot": "base"}
        self.top = {"id": "teal knit", "hex": "1F5F63", "slot": "top"}
        self.bottom = {"id": "grey trouser", "hex": "8B8378", "slot": "bottom"}

    def test_base_is_a_slot_but_never_a_coverage_gap(self):
        self.assertIn("base", matcher.SLOTS)
        self.assertNotIn("base", matcher.COVERAGE_SLOTS)
        self.assertEqual(matcher.BODY_WEIGHT["base"], 0)
        self.assertEqual(matcher.AREA_WEIGHT["base"], 0.5)

    def test_covered_by_a_top_it_is_in_by_default(self):
        o = _outfit([self.top, self.bottom, self.base])
        b = o["slots"]["base"]
        self.assertEqual((b["verdict"], b["stage"], b["where"]), ("in", 0, "covered"))
        self.assertNotIn("base", [f["item_id"] for f in o["checks"]["zone"]["flags"]])

    def test_uncovered_it_is_judged(self):
        o = _outfit([self.bottom, self.base])
        self.assertEqual(o["slots"]["base"]["verdict"], "hard_miss")

    def test_excluded_from_tier_balance_and_the_face_rules(self):
        black_base = {"id": "black slip", "hex": "000000", "slot": "base"}
        r = matcher.score_item(black_base, self.season)
        self.assertEqual(r["where"], "away from the face")   # never a face position
        self.assertEqual(r["verdict"], "in")
        covered = _outfit([self.top, self.bottom, black_base])
        bare = _outfit([self.top, self.bottom])
        self.assertEqual(covered["checks"]["tier_mix"], bare["checks"]["tier_mix"])

    def test_base_prefix_at_intake(self):
        from engine import intake
        self.assertEqual(intake.parse_filename("base_silk-slip.jpg"), ("base", "silk slip", None))


class TestFibreSurfaceAndTexture(unittest.TestCase):
    """Decision 3 — fabric and texture as item fields, and the flat check."""

    def setUp(self):
        self.season = SA()

    def test_the_vocabularies(self):
        self.assertEqual(matcher.FIBRES, ("wool", "cotton", "silk", "linen", "denim",
                                          "leather", "suede", "cashmere", "synthetic", "other"))
        self.assertEqual(matcher.SURFACES, ("smooth", "matte", "textured", "pile", "shiny"))

    def test_fields_load_from_the_csv_and_reach_the_item(self):
        from engine import run
        items = {i["id"]: i for i in run.load_items(REPO_ROOT / "engine" / "examples" / "nora-items.csv")}
        self.assertEqual((items["deep teal knit"]["fibre"], items["deep teal knit"]["surface"]),
                         ("wool", "textured"))
        r = matcher.score_item(items["deep teal knit"], self.season)
        self.assertEqual((r["fibre"], r["surface"]), ("wool", "textured"))

    def test_an_unknown_fibre_is_refused(self):
        from engine import run
        import tempfile, os
        text = ("name,slot,hex,dressiness,weight,near_face,fibre,surface,notes\n"
                "x,top,1F5F63,2,2,,tweed,smooth,\n")
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False) as fh:
            fh.write(text); path = fh.name
        try:
            with self.assertRaises(SystemExit):
                run.load_items(path)
        finally:
            os.unlink(path)

    def test_all_smooth_in_a_low_contrast_season_is_flat(self):
        o = _outfit([{"id": "teal knit", "hex": "1F5F63", "slot": "top", "surface": "smooth"},
                     {"id": "petrol trouser", "hex": "2C5A66", "slot": "bottom", "surface": "smooth"}])
        self.assertEqual(o["checks"]["texture"]["flag"], "flat — needs texture")
        self.assertTrue(any(g["type"] == "flat_texture" for g in o["gaps"]))

    def test_one_textured_item_clears_it(self):
        o = _outfit([{"id": "teal knit", "hex": "1F5F63", "slot": "top", "surface": "textured"},
                     {"id": "petrol trouser", "hex": "2C5A66", "slot": "bottom", "surface": "smooth"}])
        self.assertIsNone(o["checks"]["texture"]["flag"])

    def test_an_unset_surface_is_unknown_not_smooth(self):
        o = _outfit([{"id": "teal knit", "hex": "1F5F63", "slot": "top", "surface": "smooth"},
                     {"id": "petrol trouser", "hex": "2C5A66", "slot": "bottom"}])
        self.assertIsNone(o["checks"]["texture"]["flag"])
        self.assertIsNone(o["checks"]["texture"]["all_smooth"])


class TestMaterialPreferences(unittest.TestCase):
    """Decision 4 — the intake file's material preferences, reported not scored."""

    def setUp(self):
        self.season = SA()
        self.pairs = [p for lst in generators.run(self.season.anchors).values() for p in lst]

    def test_the_example_intake_file_loads(self):
        from engine import run
        data = run.load_intake(REPO_ROOT / "engine" / "examples" / "nora-intake.yaml")
        self.assertEqual(data["confidence"], {"temperature": "medium", "value": "high", "chroma": "high"})
        self.assertEqual(data["questions"]["wears_most"], "knitwear")
        self.assertEqual(data["materials"]["loves"], ["wool", "cashmere"])

    def test_an_unknown_fibre_in_the_intake_is_refused(self):
        from engine import run
        import tempfile, os
        with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as fh:
            fh.write("materials:\n  loves: [tweed]\n"); path = fh.name
        try:
            with self.assertRaises(SystemExit):
                run.load_intake(path)
        finally:
            os.unlink(path)

    def test_a_loved_fibre_that_could_dress_you_and_never_does(self):
        items = [{"id": "linen shirt", "hex": "EFE6D3", "slot": "top", "fibre": "linen"},
                 {"id": "linen trouser", "hex": "8B8378", "slot": "bottom", "fibre": "linen"},
                 {"id": "wool knit", "hex": "1F5F63", "slot": "top", "fibre": "wool"}]
        scored = matcher.score_items(items, self.season)
        worn = matcher.score_outfits([{"name": "a", "items": [items[2], items[1]]}],
                                     self.season, items)["outfits"]
        out = horizons.material_notes({"loves": ["linen"]}, scored, worn, self.pairs)
        note = next(n for n in out["notes"] if n["kind"] == "suggestion")
        self.assertIn("you said you love linen", note["text"])
        self.assertEqual(set(note["items"]), {"linen shirt", "linen trouser"})

    def test_no_suggestion_when_an_outfit_already_is_that_fibre(self):
        items = [{"id": "wool knit", "hex": "1F5F63", "slot": "top", "fibre": "wool"},
                 {"id": "wool trouser", "hex": "8B8378", "slot": "bottom", "fibre": "wool"}]
        scored = matcher.score_items(items, self.season)
        worn = matcher.score_outfits([{"name": "a", "items": items}], self.season, items)["outfits"]
        out = horizons.material_notes({"loves": ["wool"]}, scored, worn, self.pairs)
        self.assertEqual([n for n in out["notes"] if n["kind"] == "suggestion"], [])

    def test_easy_against_a_high_maintenance_wardrobe(self):
        items = [{"id": "silk top", "hex": "1F5F63", "slot": "top", "fibre": "silk"},
                 {"id": "suede skirt", "hex": "A6502F", "slot": "bottom", "fibre": "suede"},
                 {"id": "wool knit", "hex": "4E5A3A", "slot": "top", "fibre": "wool"},
                 {"id": "cotton tee", "hex": "EFE6D3", "slot": "top", "fibre": "cotton"}]
        scored = matcher.score_items(items, self.season)
        out = horizons.material_notes({"note": "I want something easy"}, scored, [], self.pairs)
        challenge = next(n for n in out["notes"] if n["kind"] == "challenge")
        self.assertIn("you said easy", challenge["text"])
        self.assertEqual(challenge["share"], 0.5)

    def test_preferences_change_no_verdict(self):
        from engine import run
        items = run.load_items(REPO_ROOT / "engine" / "examples" / "nora-items.csv")
        outfits = run.load_outfits(REPO_ROOT / "engine" / "examples" / "nora-outfits.csv", items)
        plain = horizons.result("soft_autumn", "teal_ochre", items, outfits=outfits)
        withm = horizons.result("soft_autumn", "teal_ochre", items, outfits=outfits,
                                materials={"loves": ["wool"], "avoids": ["synthetic"], "note": "easy"})
        verdicts = lambda r: [(o["name"], s, (v or {}).get("verdict"))
                              for o in r["outfits"] for s, v in o["slots"].items()]
        self.assertEqual(verdicts(plain), verdicts(withm))
        self.assertEqual(plain["short_term"]["distance"], withm["short_term"]["distance"])


class TestLifeWeight(unittest.TestCase):
    """Decision 5 — gaps rank by unlocks × the mean life weight of the outfits."""

    def setUp(self):
        from engine import run
        self.items = run.load_items(REPO_ROOT / "engine" / "examples" / "nora-items.csv")
        self.outfits = run.load_outfits(REPO_ROOT / "engine" / "examples" / "nora-outfits.csv", self.items)
        self.result = horizons.result("soft_autumn", "teal_ochre", self.items, outfits=self.outfits)

    def test_life_weight_loads_from_the_csv(self):
        by = {o["name"]: o["life_weight"] for o in self.outfits}
        self.assertEqual(by["work Tuesday"], 8)
        self.assertEqual(by["work into evening"], 3)

    def test_a_blank_life_weight_defaults_to_five(self):
        season = SA()
        out = matcher.score_outfits([{"name": "x", "items": [{"id": "t", "hex": "1F5F63", "slot": "top"}]}],
                                    season, [{"id": "t", "hex": "1F5F63", "slot": "top"}])
        self.assertEqual(out["outfits"][0]["life_weight"], matcher.DEFAULT_LIFE_WEIGHT)
        self.assertEqual(matcher.DEFAULT_LIFE_WEIGHT, 5)

    def test_score_is_unlocks_times_mean_life_weight(self):
        for g in self.result["gaps_ranked"]:
            with self.subTest(gap=g["type"]):
                self.assertAlmostEqual(g["score"], round(g["unlocks"] * g["mean_life_weight"], 1), places=1)

    def test_ranking_follows_the_score_not_the_count(self):
        scores = [g["score"] for g in self.result["gaps_ranked"]]
        self.assertEqual(scores, sorted(scores, reverse=True))
        # the video-call gap (life weight 7) outranks the work-into-evening one (3)
        by = {(g["type"], g.get("occasion")): g for g in self.result["gaps_ranked"]}
        video = by[("context_gap", "video call")]
        evening = next(g for g in self.result["gaps_ranked"] if g["type"] == "zone_gap")
        self.assertEqual(video["unlocks"], evening["unlocks"])
        self.assertGreater(video["score"], evening["score"])


class TestDirectionsBlock(unittest.TestCase):
    """Decision 6 — the three directions, side by side."""

    @classmethod
    def setUpClass(cls):
        from engine import run
        cls.items = run.load_items(REPO_ROOT / "engine" / "examples" / "nora-items.csv")
        cls.result = horizons.result("soft_autumn", "teal_ochre", cls.items)
        cls.dirs = cls.result["long_term"]["directions"]

    def test_one_block_per_direction_in_the_season(self):
        season = SA()
        self.assertEqual([d["direction"] for d in self.dirs], list(season.directions))

    def test_each_carries_a_palette_combinations_and_strategic_pieces(self):
        for d in self.dirs:
            with self.subTest(direction=d["direction"]):
                self.assertEqual(set(d["palette"]), set(palette.TIERS))
                self.assertLessEqual(len(d["combinations"]), horizons.DIRECTION_COMBINATIONS)
                self.assertLessEqual(len(d["strategic_pieces"]), horizons.STRATEGIC_PIECES)
                self.assertTrue(d["note"])

    def test_the_palette_is_re_weighted_toward_the_direction(self):
        for d in self.dirs:
            with self.subTest(direction=d["direction"]):
                first = d["palette"]["foundations"][0] if d["palette"]["foundations"] else None
                heaviest = max(a["weight"] for t in palette.TIERS for a in d["palette"][t])
                self.assertEqual(heaviest, 2.0)
                self.assertIsNotNone(first)

    def test_strategic_pieces_are_things_the_closet_lacks(self):
        owned = {r["nearest"] for r in matcher.score_items(self.items, SA()) if r["verdict"] == "in"}
        for d in self.dirs:
            for p in d["strategic_pieces"]:
                with self.subTest(direction=d["direction"], piece=p["anchor"]):
                    self.assertNotIn(p["anchor"], owned)


class TestResultPage(unittest.TestCase):
    """The colour-share bars, the best improvement and the summary."""

    @classmethod
    def setUpClass(cls):
        from engine import render, run
        cls.items = run.load_items(REPO_ROOT / "engine" / "examples" / "nora-items.csv")
        cls.outfits = run.load_outfits(REPO_ROOT / "engine" / "examples" / "nora-outfits.csv", cls.items)
        cls.result = horizons.result("soft_autumn", "teal_ochre", cls.items, outfits=cls.outfits,
                                     materials={"loves": ["wool"], "note": "easy"})
        cls.html = render.render(cls.result)

    def test_shares_are_area_weighted_and_sum_to_one(self):
        o = next(o for o in self.result["outfits"] if o["name"] == "work Tuesday")
        self.assertAlmostEqual(sum(s["share"] for s in o["shares"]), 1.0, places=2)
        by = {s["item_id"]: s for s in o["shares"]}
        # top 2 + bottom 2 + accessory 1 = 5
        self.assertEqual(by["deep teal knit"]["area"], 2)
        self.assertEqual(by["rust scarf"]["area"], 1)
        self.assertAlmostEqual(by["rust scarf"]["share"], 0.2, places=2)

    def test_every_share_carries_its_verdict(self):
        for o in self.result["outfits"]:
            for s in o["shares"]:
                with self.subTest(outfit=o["name"], item=s["item_id"]):
                    self.assertIn(s["verdict"], ("in", "near", "out", "hard_miss"))

    def test_each_outfit_has_a_best_improvement(self):
        for o in self.result["outfits"]:
            with self.subTest(outfit=o["name"]):
                imp = o["improvement"]
                self.assertIn("before", imp)
                self.assertGreaterEqual(imp["before"], imp["after"])
                if imp["item_id"]:
                    self.assertAlmostEqual(sum(s["share"] for s in imp["shares"]), 1.0, places=2)

    def test_the_summary_weights_compositions_by_life_weight(self):
        comps = self.result["short_term"]["compositions"]
        self.assertEqual(comps[0]["composition"], "top + bottom + accessory")
        self.assertEqual(comps[0]["life_weight"], 8 + 3 + 6 + 7)
        self.assertEqual([c["life_weight"] for c in comps], sorted((c["life_weight"] for c in comps), reverse=True))
        self.assertTrue(all("heads_toward" in c for c in comps))

    def test_the_page_renders_every_new_block(self):
        for fragment in ("Three directions", "What you actually wear", "Best improvement",
                         'class="shares"', "life weight", "wool", "textured"):
            with self.subTest(fragment=fragment):
                self.assertIn(fragment, self.html)
        self.assertNotIn("http://", self.html)


class TestTrialSlice(unittest.TestCase):
    """The narrow first slice (frameworks/scope.md): same engine, three
    differences, nothing removed."""

    TRIAL = REPO_ROOT / "engine" / "examples" / "trial-nora"

    @classmethod
    def setUpClass(cls):
        from engine import render, run
        cls.items = run.load_items(cls.TRIAL / "items.csv")
        cls.outfits = run.load_outfits(cls.TRIAL / "outfits.csv", cls.items)
        cls.trial = horizons.result("soft_autumn", "teal_ochre", cls.items, outfits=cls.outfits,
                                    trial={"occasion": "work", "month": "October"})
        cls.full = horizons.result("soft_autumn", "teal_ochre", cls.items, outfits=cls.outfits)
        cls.html = render.render(cls.trial)

    # -- the shape of the ask
    def test_the_example_has_the_slots_the_trial_asks_for(self):
        by_slot = {}
        for i in self.items:
            by_slot[i["slot"]] = by_slot.get(i["slot"], 0) + 1
        self.assertEqual(by_slot, {"top": 4, "bottom": 4, "layer": 2, "shoes": 2, "bag": 2, "accessory": 4})
        near = [i for i in self.items if i["slot"] == "accessory" and i.get("near_face")]
        hardware = [i for i in self.items if i["slot"] == "accessory" and not i.get("near_face")]
        self.assertEqual((len(near), len(hardware)), (2, 2))    # two scarves, two jewellery
        # sixteen items plus the two optional layers
        self.assertEqual(len(self.items) - by_slot["layer"], 16)

    def test_four_outfits_covering_the_four_combinations(self):
        self.assertEqual(len(self.outfits), 4)
        self.assertEqual(sorted((o["formality"], o["setting"]) for o in self.outfits),
                         [("casual", "home"), ("casual", "office"),
                          ("corporate", "home"), ("corporate", "office")])
        self.assertEqual(sorted(o["weather"] for o in self.outfits), ["clear", "clear", "clear", "rain"])
        self.assertIn("work into evening", [o["occasion"] for o in self.outfits])

    def test_all_four_outfits_are_checked(self):
        self.assertEqual(len(self.trial["outfits"]), 4)
        for o in self.trial["outfits"]:
            with self.subTest(outfit=o["name"]):
                for key in ("coverage", "palette", "tier_mix", "contrast", "zone", "weather",
                            "context", "texture"):
                    self.assertIn(key, o["checks"])
                self.assertTrue(o["checks"]["context"]["checked"] or o["formality"] == "casual")
                self.assertIsNotNone(o["shares"])
                self.assertIn("before", o["improvement"])

    # -- difference 1: the missing list
    def test_trial_suppresses_the_missing_list(self):
        miss = self.trial["short_term"]["missing"]
        self.assertIsNone(miss["anchors"])
        self.assertTrue(miss["suppressed"])
        self.assertEqual(miss["note"], horizons.TRIAL_NO_MISSING)
        self.assertNotIn("missing from the closet", self.html)

    def test_a_full_run_on_the_same_wardrobe_still_lists_it(self):
        miss = self.full["short_term"]["missing"]
        self.assertFalse(miss.get("suppressed", False))
        self.assertIsNotNone(miss["anchors"])          # eighteen items clears the ten-item floor

    # -- difference 2: the title
    def test_the_page_is_titled_for_the_occasion_and_month(self):
        self.assertIn("<title>Work · October · Soft Autumn</title>", self.html)
        self.assertIn('class="scope"', self.html)

    # -- difference 3: the long-term block
    def test_the_long_term_horizon_is_replaced(self):
        self.assertIn("What this tells us about the rest of your wardrobe", self.html)
        self.assertIn("What it did not", self.html)
        self.assertNotIn("<h2>Long-term</h2>", self.html)
        f = self.trial["trial"]["findings"]
        self.assertEqual(f["outfits_checked"], 4)
        self.assertTrue(f["shows"])
        self.assertTrue(any("other occasions" in s for s in f["does_not_show"]))

    # -- and nothing else moved
    def test_every_verdict_gap_and_bar_is_identical_to_a_full_run(self):
        shape = lambda r: ([(o["name"], s, (v or {}).get("verdict"), (v or {}).get("nearest"))
                            for o in r["outfits"] for s, v in o["slots"].items()],
                           [(g["type"], g.get("slot"), g["score"]) for g in r["gaps_ranked"]],
                           [(o["name"], [(s["item_id"], s["share"]) for s in o["shares"]])
                            for o in r["outfits"]],
                           r["short_term"]["distance"],
                           [m["item_id"] for m in r["short_term"]["next_moves"]])
        self.assertEqual(shape(self.trial), shape(self.full))

    def test_the_denim_bottom_is_admitted_below_the_waist(self):
        o = next(o for o in self.trial["outfits"] if o["slots"]["bottom"]
                 and o["slots"]["bottom"]["fibre"] == "denim")
        self.assertEqual(o["slots"]["bottom"]["nearest"], "denim (below waist)")

    def test_the_committed_result_page_is_current(self):
        from engine import render
        self.assertEqual((self.TRIAL / "result.html").read_text(),
                         render.render(horizons.result(
                             "soft_autumn", "teal_ochre", self.items, outfits=self.outfits,
                             materials={"loves": ["wool", "cashmere"], "avoids": ["synthetic"],
                                        "note": "something easy — I want to get dressed without thinking about it"},
                             mood="calm, put together, not trying",
                             confidence={"temperature": "medium", "value": "high", "chroma": "high"},
                             trial={"occasion": "work", "month": "October"})))
