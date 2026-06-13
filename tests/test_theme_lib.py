"""Unit tests for theme_lib.

Fixtures use placeholder passage names and numeric references only. No religious
text appears anywhere in this file, per the project's content rules.
"""

import json
import os
import tempfile
import unittest

import theme_lib


def _passage(surah, ayah, ayah_end=None, name="Sample Passage",
             verified=False, verified_on=None, note=""):
    return {
        "surah": surah,
        "ayah": ayah,
        "ayah_end": ayah if ayah_end is None else ayah_end,
        "name": name,
        "verified": verified,
        "verified_on": verified_on,
        "note": note,
    }


def _theme(slug, title, keywords, passages):
    return {"slug": slug, "title": title, "keywords": keywords, "passages": passages}


def _valid_fixture():
    return {
        "_about": "placeholder metadata; ignored by the loader",
        "_rules": "placeholder rules; ignored by the loader",
        "themes": [
            _theme(
                "sample-relief", "Sample relief",
                ["hardship", "relief", "second chance"],
                [
                    _passage(1, 1, 2, name="Sample Passage A"),
                    _passage(2, 5, 5, name="Sample Passage B",
                             verified=True, verified_on="2026-01-01"),
                    _passage(1, 3, 3, name="Sample Mercy Note"),
                ],
            ),
            _theme(
                "sample-mercy", "Sample mercy",
                ["mercy", "hope"],
                [
                    _passage(3, 10, 10, name="Sample Passage Ease"),
                    _passage(4, 20, 20, name="Sample Please Wait"),
                ],
            ),
        ],
    }


class _FixtureCase(unittest.TestCase):
    def fixture(self, data):
        """Write a themes-shaped dict to a temp file and return its absolute path."""
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        self.addCleanup(os.remove, path)
        return path


class LoadThemesTest(_FixtureCase):
    def test_valid_fixture_loads(self):
        themes = theme_lib.load_themes(self.fixture(_valid_fixture()))
        self.assertEqual(len(themes), 2)
        self.assertEqual(themes[0]["slug"], "sample-relief")
        self.assertEqual(len(themes[0]["passages"]), 3)
        self.assertEqual(themes[0]["passages"][0]["ayah_end"], 2)

    def test_unknown_top_level_keys_ignored(self):
        themes = theme_lib.load_themes(self.fixture(_valid_fixture()))
        self.assertEqual(len(themes), 2)

    def test_missing_required_key_rejected(self):
        data = _valid_fixture()
        del data["themes"][0]["passages"][0]["verified_on"]
        with self.assertRaises(ValueError):
            theme_lib.load_themes(self.fixture(data))

    def test_wrong_type_rejected(self):
        data = _valid_fixture()
        data["themes"][0]["passages"][0]["ayah"] = "1"
        with self.assertRaises(ValueError):
            theme_lib.load_themes(self.fixture(data))

    def test_bool_is_not_accepted_as_int(self):
        data = _valid_fixture()
        data["themes"][0]["passages"][0]["surah"] = True
        with self.assertRaises(ValueError):
            theme_lib.load_themes(self.fixture(data))

    def test_ayah_end_before_ayah_rejected(self):
        data = _valid_fixture()
        data["themes"][0]["passages"][0]["ayah"] = 5
        data["themes"][0]["passages"][0]["ayah_end"] = 2
        with self.assertRaises(ValueError):
            theme_lib.load_themes(self.fixture(data))

    def test_duplicate_reference_rejected(self):
        dup = _theme("dup", "Dup", ["sample"],
                     [_passage(7, 1, 1), _passage(7, 1, 1)])
        with self.assertRaises(ValueError):
            theme_lib.load_themes(self.fixture({"themes": [dup]}))

    def test_same_surah_different_range_is_allowed(self):
        # (1,1,2) and (1,3,3) share a surah but are distinct references.
        themes = theme_lib.load_themes(self.fixture(_valid_fixture()))
        refs = {(p["surah"], p["ayah"], p["ayah_end"]) for p in themes[0]["passages"]}
        self.assertIn((1, 1, 2), refs)
        self.assertIn((1, 3, 3), refs)


class SearchTest(_FixtureCase):
    def setUp(self):
        self.themes = theme_lib.load_themes(self.fixture(_valid_fixture()))

    def test_keyword_match_returns_all_theme_passages(self):
        # "hardship" is a sample-relief keyword, so all three of its passages match.
        results = theme_lib.search(self.themes, "hardship")
        self.assertEqual(len(results), 3)
        self.assertTrue(all(theme["slug"] == "sample-relief" for theme, _p in results))

    def test_case_insensitive(self):
        self.assertEqual(
            len(theme_lib.search(self.themes, "HARDSHIP")),
            len(theme_lib.search(self.themes, "hardship")),
        )

    def test_unverified_passages_are_returned(self):
        results = theme_lib.search(self.themes, "hardship")
        self.assertTrue(any(not passage["verified"] for _t, passage in results))

    def test_whole_word_not_substring(self):
        # "ease" matches the name "Sample Passage Ease" but not "Sample Please Wait".
        results = theme_lib.search(self.themes, "ease")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][1]["name"], "Sample Passage Ease")

    def test_scored_by_match_count(self):
        # "Sample Mercy Note" matches keyword "relief" AND name word "mercy" (2);
        # the other relief passages and the mercy-theme passages match only one.
        results = theme_lib.search(self.themes, "relief mercy")
        self.assertEqual(results[0][1]["name"], "Sample Mercy Note")

    def test_no_match_returns_empty(self):
        self.assertEqual(theme_lib.search(self.themes, "zzznomatch"), [])

    def test_empty_query_returns_empty(self):
        self.assertEqual(theme_lib.search(self.themes, ""), [])

    def test_accepts_token_iterable(self):
        as_string = theme_lib.search(self.themes, "mercy hope")
        as_list = theme_lib.search(self.themes, ["mercy", "hope"])
        self.assertEqual(len(as_string), len(as_list))


if __name__ == "__main__":
    unittest.main()
