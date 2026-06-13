"""Theme index loader and keyword search for planned reels.

Loads and validates themes.json, the hand-maintained topic index over verified
passages, and provides case-insensitive whole-word keyword search. Pure standard
library: this module fetches nothing and holds no religious text. The verified
flag is surfaced, never filtered, so callers can flag or refuse unverified
passages themselves.
"""

import json
import os
import re

# ── Constants ────────────────────────────────────────────────────────────────

DEFAULT_THEMES_PATH = "themes.json"

_PASSAGE_REQUIRED_KEYS = (
    "surah",
    "ayah",
    "ayah_end",
    "name",
    "verified",
    "verified_on",
    "note",
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")


# ── Validation ───────────────────────────────────────────────────────────────

def _is_int(value):
    # bool subclasses int, so isinstance(True, int) is True; exclude it here.
    return isinstance(value, int) and not isinstance(value, bool)


def _validate_passage(theme_slug, index, passage):
    """Validate one passage; raise ValueError naming the theme, index, and field."""
    where = f"theme '{theme_slug}' passage {index}"
    if not isinstance(passage, dict):
        raise ValueError(f"{where}: expected an object, got {type(passage).__name__}")
    for key in _PASSAGE_REQUIRED_KEYS:
        if key not in passage:
            raise ValueError(f"{where}: missing required key '{key}'")
    if not _is_int(passage["surah"]):
        raise ValueError(f"{where}: 'surah' must be an int")
    if not _is_int(passage["ayah"]):
        raise ValueError(f"{where}: 'ayah' must be an int")
    if not _is_int(passage["ayah_end"]):
        raise ValueError(f"{where}: 'ayah_end' must be an int")
    if passage["ayah_end"] < passage["ayah"]:
        raise ValueError(
            f"{where}: 'ayah_end' ({passage['ayah_end']}) is before "
            f"'ayah' ({passage['ayah']})"
        )
    if not isinstance(passage["name"], str):
        raise ValueError(f"{where}: 'name' must be a string")
    if not isinstance(passage["verified"], bool):
        raise ValueError(f"{where}: 'verified' must be a boolean")
    if passage["verified_on"] is not None and not isinstance(passage["verified_on"], str):
        raise ValueError(f"{where}: 'verified_on' must be a string or null")
    if not isinstance(passage["note"], str):
        raise ValueError(f"{where}: 'note' must be a string")


def _validate_theme(theme):
    """Validate one theme and its passages; raise ValueError on any problem."""
    if not isinstance(theme, dict):
        raise ValueError(f"theme entry must be an object, got {type(theme).__name__}")
    slug = theme.get("slug")
    if not isinstance(slug, str) or not slug:
        raise ValueError(f"theme is missing a non-empty string 'slug': {theme!r}")
    if not isinstance(theme.get("title"), str):
        raise ValueError(f"theme '{slug}' is missing a string 'title'")
    keywords = theme.get("keywords")
    if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
        raise ValueError(f"theme '{slug}' 'keywords' must be a list of strings")
    passages = theme.get("passages")
    if not isinstance(passages, list):
        raise ValueError(f"theme '{slug}' 'passages' must be a list")

    seen_refs = set()
    for index, passage in enumerate(passages):
        _validate_passage(slug, index, passage)
        ref = (passage["surah"], passage["ayah"], passage["ayah_end"])
        if ref in seen_refs:
            raise ValueError(
                f"theme '{slug}' has duplicate passage reference "
                f"{ref[0]}:{ref[1]}-{ref[2]}"
            )
        seen_refs.add(ref)


# ── Loading ──────────────────────────────────────────────────────────────────

def load_themes(path=DEFAULT_THEMES_PATH):
    """Load and validate the theme index, returning a list of theme dicts.

    A relative path is resolved against this module's directory so the default
    works from any working directory. Unknown top-level keys (such as _about and
    _rules) are ignored. Raises ValueError with a specific message on any schema
    violation or duplicate passage reference.
    """
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict) or not isinstance(data.get("themes"), list):
        raise ValueError("themes file must be an object with a 'themes' list")
    themes = data["themes"]
    for theme in themes:
        _validate_theme(theme)
    return themes


# ── Search ───────────────────────────────────────────────────────────────────

def _word_tokens(text):
    """Lowercase a string and return its alphanumeric word tokens."""
    return _TOKEN_RE.findall(text.lower())


def _query_tokens(words):
    """Normalize a query (a string or an iterable of strings) to word tokens."""
    parts = [words] if isinstance(words, str) else list(words)
    tokens = []
    for part in parts:
        tokens.extend(_word_tokens(part))
    return tokens


def search(themes, words):
    """Return (theme, passage) pairs whose keywords or name match the query.

    Each distinct query token is matched case-insensitively against whole words
    drawn from the theme's keywords and the passage's name (no substring hits).
    The score is the number of distinct query tokens that match; pairs with at
    least one match are returned sorted by descending score, ties keeping input
    order. Unverified passages are included; callers decide how to flag them.
    """
    query = set(_query_tokens(words))
    if not query:
        return []
    scored = []
    for theme in themes:
        keyword_words = set()
        for keyword in theme.get("keywords", []):
            keyword_words.update(_word_tokens(keyword))
        for passage in theme.get("passages", []):
            candidate_words = keyword_words | set(_word_tokens(passage.get("name", "")))
            score = len(query & candidate_words)
            if score:
                scored.append((score, theme, passage))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [(theme, passage) for _score, theme, passage in scored]
