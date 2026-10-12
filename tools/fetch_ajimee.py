"""Builds sets/ajimee.tsv from AJIMEE-Bench exactly as published.

  python tools/fetch_ajimee.py [--file evaluation_items.json]

The file is fetched at a pinned commit (or read from --file) and must have
the SHA-256 below. Every item is used, with its expected outputs unchanged;
the only thing added is the romaji typed for its katakana reading (kana as
romaji, punctuation as the keys that type it). The left context is kept in
sets/ajimee.context.tsv.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "lib"))
from kana import hiragana, to_keys  # noqa: E402

COMMIT = "401666cd56d1a570c2021798b64b6da4396bfd45"
URL = f"https://raw.githubusercontent.com/azooKey/AJIMEE-Bench/{COMMIT}/JWTD_v2/v1/evaluation_items.json"
SHA256 = "e9eb668fd6aa14b1e26436f429b5550108af0a1dfd443b8cea0bcb3ab3028fca"
# Punctuation in the readings, as the keys that type it with a romaji IME.
KEYS = {"、": ",", "。": ".", "（": "(", "）": ")", "「": "[", "」": "]", "『": "[", "』": "]", "・": "/", "…": "...",
        "！": "!", "？": "?"}
ROOT = Path(__file__).resolve().parents[1]


def keys_for(reading: str) -> str:
    out, piece = [], ""
    for c in hiragana(reading):
        if c in KEYS:
            if piece:
                out.append(to_keys(piece))
                piece = ""
            out.append(KEYS[c])
        else:
            piece += c
    if piece:
        out.append(to_keys(piece))
    if any(k is None for k in out):
        raise ValueError(f"cannot type {reading!r}")
    return "".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", type=Path)
    args = ap.parse_args()
    data = args.file.read_bytes() if args.file else urllib.request.urlopen(URL).read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SHA256:
        sys.exit(f"evaluation_items.json has SHA-256 {digest}, not {SHA256}")
    rows, contexts = [], []
    for item in json.loads(data):
        clean = lambda t: t.replace("\t", " ").replace("\n", " ")  # noqa: E731
        rows.append("\t".join(["ajimee", str(item["index"]), keys_for(item["input"])] + [clean(e) for e in item["expected_output"]]))
        contexts.append(f"{item['index']}\t{clean(item.get('context_text', ''))}")
    (ROOT / "sets" / "ajimee.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    (ROOT / "sets" / "ajimee.context.tsv").write_text("\n".join(contexts) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(rows)} items -> sets/ajimee.tsv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
