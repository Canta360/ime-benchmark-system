"""Typing slips (a neighboring key, a key left out, a key typed twice, two
keys swapped), vendored from the repo's eval/typo-study.py so the slips in a
set do not change when the repo does."""
from __future__ import annotations

import random
import re

NEIGHBORS = {
    "q": "wa", "w": "qes", "e": "wrd", "r": "etf", "t": "ryg", "y": "tuh", "u": "yij", "i": "uok", "o": "ipl",
    "p": "ol", "a": "qsz", "s": "awdz", "d": "sefx", "f": "drgc", "g": "fthv", "h": "gyjb", "j": "hukn",
    "k": "jilm", "l": "kop", "z": "asx", "x": "zdc", "c": "xfv", "v": "cgb", "b": "vhn", "n": "bjm", "m": "nk",
}
KINDS = ("neighbor", "missing", "repeated", "swapped")


def slip(word: str, at: int, kind: str, rng: random.Random) -> str | None:
    c = word[at]
    if kind == "neighbor":
        if c.lower() not in NEIGHBORS:
            return None
        other = rng.choice(NEIGHBORS[c.lower()])
        return word[:at] + (other.upper() if c.isupper() else other) + word[at + 1:]
    if kind == "missing":
        return word[:at] + word[at + 1:] if len(word) > 2 else None
    if kind == "repeated":
        return word[:at] + c + word[at:]
    if at + 1 < len(word) and word[at + 1].isalpha() and word[at + 1].lower() != c.lower():
        return word[:at] + word[at + 1] + c + word[at + 2:]
    return None


def add_slips(words: list[str], count: int, rng: random.Random) -> list[str] | None:
    """`count` slips in different words when there are that many (letters
    only, not a sentence's first capital); None when they cannot be made."""
    places = [(w, i) for w, word in enumerate(words) for i, c in enumerate(word)
              if c.isalpha() and not (i == 0 and c.isupper())]
    if not places:
        return None
    taken: set[int] = set()
    made = 0
    words = list(words)
    for _ in range(200):
        if made == count:
            break
        w, at = rng.choice(places)
        if (w in taken and len({p[0] for p in places}) >= count) or at >= len(words[w]):
            continue
        changed = slip(words[w], at, rng.choice(KINDS), rng)
        if changed is None or changed == words[w] or not re.sub(r"[^A-Za-z]", "", changed):
            continue
        words[w] = changed
        taken.add(w)
        made += 1
    return words if made == count else None


def japanese_slips(keys: str, count: int, rng: random.Random) -> str | None:
    """`count` slips in run-together romaji keys (one 'word'), one at a time."""
    for _ in range(count):
        result = add_slips([keys], 1, rng)
        if not result:
            return None
        keys = result[0]
    return keys
