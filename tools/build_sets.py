"""Builds benchmark sets from written sources (evaluator tool).

  python build_sets.py --src <sources dir> --out <sets dir> [--gzip] [--name c1]

Sources (any may be missing):
  ja_*.jsonl      {"text", "chunks": [hiragana phrase, ...]}             -> ja, jatypo
  mix_*.jsonl     {"text", "chunks": [hiragana | "@english", ...]}      -> mixB, mixC
  en_sentences.txt  one correctly spelled sentence per line             -> en, enclean
  posts_ja.jsonl  {"kind": "ja"|"mix", "text", "chunks"}                 -> postsja, postsmixB, postsmixC
  posts_en.txt    one post per line                                     -> postsen, postsentypo

Set rows: source, id, keys, meant text (tab-separated). Keys are what is
typed: Japanese run together; Mix B with Space around English words (each
space-separated piece is converted with Space); Mix C all run together.
Every Japanese chunk must type back as its kana with the installed romaji
table, and the English letters must be the ones in the text, or the row is
left out (reported). Slips are seeded by --name, so a set is reproducible.
"""
from __future__ import annotations

import argparse
import gzip
import json
import random
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "lib"))
from kana import Romaji, hiragana, to_keys  # noqa: E402
from slips import add_slips, japanese_slips  # noqa: E402

PUNCT = "、。！？"
LATIN = re.compile(r"[A-Za-z]+")


class Bad(ValueError):
    pass


def chunk_keys(chunks: list[str], romaji: Romaji) -> list[tuple[bool, str]]:
    """(english, keys) per chunk, checked."""
    out = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        if chunk.startswith("@"):
            # A name of two words in one chunk ("@uber eats") is two English chunks.
            for word in chunk[1:].split():
                if not re.fullmatch(r"[a-z]+", word):
                    raise Bad(f"english chunk {chunk!r}")
                out.append((True, word))
            continue
        if re.search(r"[A-Za-z0-9]", chunk):
            raise Bad(f"latin or digit in kana chunk {chunk!r}")
        keys = to_keys(chunk)
        if keys is None:
            raise Bad(f"cannot type {chunk!r}")
        # Punctuation inside a chunk is typed as is; check the kana around it.
        for piece in re.split(r"[、。！？]", hiragana(chunk)):
            if piece and not romaji.reads_back(to_keys(piece), piece):
                raise Bad(f"{to_keys(piece)!r} does not type {piece!r}")
        out.append((False, keys))
    return out


def check_text(text: str, parts: list[tuple[bool, str]], mix: bool) -> None:
    if re.search(r"[0-9０-９]", text):
        raise Bad("digit in text")
    if any(c in text for c in "「」（）()・…～〜#＃"):
        raise Bad("symbol in text")
    english = [k for e, k in parts if e]
    in_text = [w.lower() for w in LATIN.findall(text)]
    if not mix and (english or in_text):
        raise Bad("latin in a Japanese-only row")
    if "".join(in_text) != "".join(english):
        raise Bad(f"english {english} does not match text {in_text}")
    # Japanese punctuation must agree in count.
    typed = "".join(k for e, k in parts if not e)
    for mark, key in zip(PUNCT, ",.!?"):
        if text.count(mark) != typed.count(key):
            raise Bad(f"punctuation {mark} differs between text and chunks")


def keys_b(parts: list[tuple[bool, str]]) -> str:
    """Mix as typed with Space around English: Japanese runs together, each
    English word its own piece; punctuation right after English stays on it."""
    pieces: list[str] = []
    last_english = False
    for english, keys in parts:
        if english:
            pieces.append(keys)
            last_english = True
            continue
        if last_english:
            lead = re.match(r"[.,!?]*", keys).group(0)
            if lead:
                pieces[-1] += lead
                keys = keys[len(lead):]
            if keys:
                pieces.append(keys)
        elif pieces:
            pieces[-1] += keys
        else:
            pieces.append(keys)
        last_english = False if keys else last_english
    return " ".join(pieces)


def keys_c(parts: list[tuple[bool, str]]) -> str:
    return "".join(k for _, k in parts)


def split_sentences(text: str, chunks: list[str]) -> list[tuple[str, list[str]]]:
    """A post as its sentences: text cut after 。！？, chunks after the chunk ending with one."""
    texts = [t for t in re.findall(r"[^。！？]*[。！？]+|[^。！？]+$", text) if t.strip()]
    groups: list[list[str]] = [[]]
    for chunk in chunks:
        groups[-1].append(chunk)
        if not chunk.startswith("@") and chunk.strip() and chunk.strip()[-1] in "。！？":
            groups.append([])
    groups = [g for g in groups if g]
    if len(texts) != len(groups):
        raise Bad(f"{len(texts)} sentences in text, {len(groups)} in chunks")
    return list(zip(texts, groups))


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--gzip", action="store_true")
    ap.add_argument("--name", default="set")
    args = ap.parse_args()
    romaji = Romaji()
    sets: dict[str, list[list[str]]] = {}
    kinds: dict[str, str] = {}
    dropped: list[str] = []

    def add(name: str, kind: str, row: list[str]) -> None:
        sets.setdefault(name, []).append(row)
        kinds[name] = kind

    rng = lambda tag: random.Random(f"{args.name}:{tag}")  # noqa: E731

    # Japanese sentences: ja (run together) and jatypo (two slips).
    typo_rng = rng("jatypo")
    for path in sorted(args.src.glob("ja_*.jsonl")):
        tag = path.stem[3:]
        for n, row in enumerate(read_jsonl(path), 1):
            rid = f"{tag}-{n:03d}"
            try:
                parts = chunk_keys(row["chunks"], romaji)
                check_text(row["text"], parts, mix=False)
            except (Bad, KeyError) as e:
                dropped.append(f"{path.name}:{n}: {e}")
                continue
            keys = keys_c(parts)
            add("ja", "ja", ["ja", rid, keys, row["text"].strip()])
            slipped = japanese_slips(keys, 2, typo_rng)
            if slipped:
                add("jatypo", "jatypo", ["jatypo", rid, slipped, row["text"].strip()])

    # Japanese with English words: B (spaced) and C (run together).
    for path in sorted(args.src.glob("mix_*.jsonl")):
        tag = path.stem[4:]
        for n, row in enumerate(read_jsonl(path), 1):
            rid = f"{tag}-{n:03d}"
            try:
                parts = chunk_keys(row["chunks"], romaji)
                check_text(row["text"], parts, mix=True)
                if not any(e for e, _ in parts):
                    raise Bad("no English word")
            except (Bad, KeyError) as e:
                dropped.append(f"{path.name}:{n}: {e}")
                continue
            add("mixB", "mixB", ["mixB", rid, keys_b(parts), row["text"].strip()])
            add("mixC", "mixC", ["mixC", rid, keys_c(parts), row["text"].strip()])

    # Posts: one row per sentence, ids <post>-<sentence>.
    path = args.src / "posts_ja.jsonl"
    if path.exists():
        for n, row in enumerate(read_jsonl(path), 1):
            mix = row.get("kind") == "mix"
            try:
                rows = []
                for i, (text, chunks) in enumerate(split_sentences(row["text"], row["chunks"])):
                    parts = chunk_keys(chunks, romaji)
                    check_text(text, parts, mix=mix)
                    rows.append((f"{n}-{i}", parts, text.strip()))
                if mix and not any(e for _, parts, _ in rows for e, _ in parts):
                    raise Bad("mix post without English")
            except (Bad, KeyError) as e:
                dropped.append(f"{path.name}:{n}: {e}")
                continue
            for rid, parts, text in rows:
                if mix:
                    add("postsmixB", "postsmixB", ["postsmix", rid, keys_b(parts), text])
                    add("postsmixC", "postsmixC", ["postsmix", rid, keys_c(parts), text])
                else:
                    add("postsja", "postsja", ["postsja", rid, keys_c(parts), text])

    # English: as typed right, and with two slips per sentence.
    for src, clean, typo, slipped_kind in (("en_sentences.txt", "enclean", "en", "en"),
                                           ("posts_en.txt", "postsen", "postsentypo", "postsentypo")):
        path = args.src / src
        if not path.exists():
            continue
        r = rng(typo)
        for n, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            s = " ".join(line.split())
            if not s:
                continue
            if not s.isascii() or '"' in s:
                dropped.append(f"{src}:{n}: not plain ASCII")
                continue
            rid = f"{n:03d}"
            add(clean, clean, [clean, rid, s, s])
            words = add_slips(s.split(" "), 2, r)
            if words:
                add(typo, slipped_kind, [typo, rid, " ".join(words), s])

    args.out.mkdir(parents=True, exist_ok=True)
    for name, rows in sets.items():
        data = "".join("\t".join(r) + "\n" for r in rows).encode("utf-8")
        if args.gzip:
            (args.out / f"{name}.tsv.gz").write_bytes(gzip.compress(data, mtime=0))
        else:
            (args.out / f"{name}.tsv").write_bytes(data)
        print(f"{name:12} {len(rows):4} rows")
    (args.out / "sets.json").write_text(json.dumps(kinds, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for d in dropped:
        print("  left out", d, file=sys.stderr)
    print(f"left out {len(dropped)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
