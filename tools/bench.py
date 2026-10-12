"""Scores benchmark runs, keeps the judge's labels, writes reports.

  python bench.py score <run dir> [--with <run dir>...] [--prev <run dir>|none]
      Scores every output in the run (and in --with runs, e.g. a real-IME run
      for comparison), writes report.md and scores.json into the run and
      compares with the previous run of the same group (regressions flagged).
  python bench.py judge-export <group> [--runs <run dir>...] [--size 150]
      Writes blind batches (meant text vs output only, shuffled, no input
      method names) of outputs not judged yet, to <group>/judging/.
  python bench.py judge-import <group>
      Reads <group>/judging/batch_*.labels.tsv into the group's label cache
      and removes the batches.
  python bench.py rotate <cycle> <prefix>
      Demotes held-out cycle <cycle> to dev: its sets become dev sets
      <prefix>_<name>, its labels join the dev labels (evaluator only).

<group> is "dev" or "heldout". A run dir holds out/<system>__<set>.tsv[.gz]
(source, id, text) and meta.json. Held-out files are gzipped so a text
search of the kit does not show them.
"""
from __future__ import annotations

import argparse
import difflib
import gzip
import json
import math
import random
import re
import shutil
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

KIT = Path(__file__).resolve().parent
if KIT.name == "tools":  # the public repository: tools/bench.py
    KIT = KIT.parent
# Public layout: sets/, labels.tsv, results/<bundle>/ at the top (one group, "dev").
PUBLIC = (KIT / "results").is_dir() and not (KIT / "dev").is_dir()
JUDGED_KINDS = {"ajimee", "ja", "jatypo", "mixB", "mixC", "postsja", "postsmixB", "postsmixC"}
POST_KINDS = {"postsja", "postsmixB", "postsmixC"}
ENGLISH_KINDS = {"en", "enclean", "postsen", "postsentypo"}
SKIP_SOURCES = {"chunk-sentence"}  # English-only rows in the old dev Mix sets
LABELS = ("A", "B", "C")


# ---------- files

def read_text(path: Path) -> str:
    if path.suffix == ".gz":
        return gzip.decompress(path.read_bytes()).decode("utf-8")
    return path.read_text(encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    if path.suffix == ".gz":
        path.write_bytes(gzip.compress(text.encode("utf-8"), mtime=0))
    else:
        path.write_text(text, encoding="utf-8", newline="\n")


def rows_of(path: Path) -> list[list[str]]:
    return [line.split("\t") for line in read_text(path).splitlines() if line.strip()]


def group_dir(group: str) -> Path:
    if group not in ("dev", "heldout"):
        sys.exit("group must be dev or heldout")
    return KIT if PUBLIC else KIT / group


def runs_dir(group: str) -> Path:
    return KIT / "results" if PUBLIC else group_dir(group) / "runs"


def current_cycle() -> str:
    return (KIT / "heldout" / "current.txt").read_text(encoding="utf-8").strip()


def sets_dir(group: str) -> Path:
    if PUBLIC:
        return KIT / "sets"
    return KIT / "dev" / "sets" if group == "dev" else KIT / "heldout" / current_cycle() / "sets"


def gz(group: str) -> str:
    return ".gz" if group == "heldout" else ""


def group_of(run: Path) -> str:
    return "heldout" if "heldout" in run.resolve().parts else "dev"


def load_sets(group: str) -> dict[str, dict]:
    d = sets_dir(group)
    kinds = json.loads((d / "sets.json").read_text(encoding="utf-8"))
    sets = {}
    for name, kind in kinds.items():
        path = d / f"{name}.tsv{gz(group)}"
        if not path.exists():
            continue
        rows, seen = [], set()
        for f in rows_of(path):
            if f[0] in SKIP_SOURCES or f[2] in seen:
                continue  # the same keys twice (two corpora) count once
            seen.add(f[2])
            rows.append({"source": f[0], "id": f[1], "keys": f[2], "meant": f[3], "forms": f[3:]})
        ctx_path = d / f"{name}.context.tsv"
        if ctx_path.exists():
            ctx = dict(l.split("	", 1) for l in ctx_path.read_text(encoding="utf-8").splitlines() if "	" in l)
            for row in rows:
                row["context"] = ctx.get(row["id"], "")
        sets[name] = {"kind": kind, "rows": rows}
    return sets


def load_outputs(run: Path) -> dict[tuple[str, str], dict[tuple[str, str], str]]:
    """(system, set) -> (source, id) -> text."""
    out = {}
    for path in sorted((run / "out").glob("*__*.tsv*")):
        name = path.name.split(".tsv")[0]
        system, set_name = name.split("__", 1)
        texts = {}
        for f in rows_of(path):
            f = f + [""] * (3 - len(f))
            texts[(f[0], f[1])] = f[2]
        out[(system, set_name)] = texts
    return out


# ---------- labels

def norm(text: str) -> str:
    """Width, letter case and spaces do not count."""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text)).lower()


def labels_path(group: str) -> Path:
    return group_dir(group) / f"labels.tsv{gz(group)}"


def load_labels(group: str) -> dict[tuple[str, str], str]:
    path = labels_path(group)
    labels = {}
    if path.exists():
        for f in rows_of(path):
            labels[(norm(f[0]), norm(f[1]))] = f[2]
    return labels


# ---------- scoring

def distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def places(want: str, got: str) -> int:
    """Places to fix: runs of differing characters."""
    ops = difflib.SequenceMatcher(None, want, got, autojunk=False).get_opcodes()
    return sum(1 for op in ops if op[0] != "equal")


def verdict(row: dict, got: str, labels: dict) -> str:
    """exact, A, B, C, or ? (not judged yet)."""
    g = norm(got)
    if any(norm(f) == g for f in row["forms"]):
        return "exact"
    return labels.get((norm(row["meant"]), g), "?")


def score_sentences(rows, texts, labels) -> tuple[dict, dict]:
    c = defaultdict(int)
    per_row = {}
    errors = chars = 0
    for row in rows:
        got = texts.get((row["source"], row["id"]))
        if got is None:
            c["missing"] += 1
            continue
        v = verdict(row, got, labels)
        c[v] += 1
        per_row[f"{row['source']}:{row['id']}"] = v
        best = min((norm(f) for f in row["forms"]), key=lambda f: distance(norm(got), f))
        errors += distance(norm(got), best)
        chars += len(best)
    n = sum(c[k] for k in ("exact", "A", "B", "C", "?"))
    s = {"n": n, "exact": c["exact"], "fair": c["exact"] + c["A"], "lenient": c["exact"] + c["A"] + c["B"],
         "B": c["B"], "pending": c["?"], "missing": c["missing"], "cer": 100 * errors / max(chars, 1)}
    return s, per_row


def score_posts(rows, texts, labels) -> tuple[dict, dict]:
    posts = defaultdict(list)
    for row in rows:
        posts[row["id"].split("-")[0]].append(row)
    n = right = right_exact = fair_places = raw_places = errors = chars = pending = 0
    per_row = {}
    for pid, parts in posts.items():
        n += 1
        ok_all = exact_all = True
        for row in parts:
            got = texts.get((row["source"], row["id"]), "")
            v = verdict(row, got, labels)
            per_row[f"{row['source']}:{row['id']}"] = v
            p = places(norm(row["meant"]), norm(got))
            raw_places += p
            if v not in ("exact", "A"):
                fair_places += p
                ok_all = False
            if v != "exact":
                exact_all = False
            pending += v == "?"
        right += ok_all
        right_exact += exact_all
        want = norm("".join(r["meant"] for r in parts))
        got = norm("".join(texts.get((r["source"], r["id"]), "") for r in parts))
        errors += distance(want, got)
        chars += len(want)
    s = {"n": n, "exact": right_exact, "fair": right, "places": fair_places / max(n, 1),
         "raw_places": raw_places / max(n, 1), "pending": pending, "cer": 100 * errors / max(chars, 1)}
    return s, per_row


def score_english(rows, texts) -> tuple[dict, dict]:
    n = right = fixed = slips = broken = changed = place = 0
    per_row = {}
    for row in rows:
        got = texts.get((row["source"], row["id"]))
        if got is None:
            continue
        got = " ".join(got.split())
        typed, meant = row["keys"], row["meant"]
        n += 1
        ok = got == meant
        right += ok
        per_row[f"{row['source']}:{row['id']}"] = "exact" if ok else "C"
        changed += got != typed
        t, m, g = typed.split(), meant.split(), got.split()
        ops = difflib.SequenceMatcher(None, m, g, autojunk=False).get_opcodes()
        place += sum(1 for op in ops if op[0] != "equal")
        if len(t) == len(m) == len(g):
            for a, b, x in zip(t, m, g):
                if a != b:
                    slips += 1
                    fixed += x == b
                elif x != b:
                    broken += 1
        else:
            # Words joined or split: counted as a slip not fixed per slip typed.
            slips += sum(a != b for a, b in zip(t, m)) if len(t) == len(m) else 1
    s = {"n": n, "exact": right, "fair": right, "slips": slips, "fixed": fixed, "broken": broken,
         "changed": changed, "places": place / max(n, 1)}
    return s, per_row


def score_ajimee(rows, texts) -> dict:
    """AJIMEE-Bench's own metrics (its utils.py): acc@1 = output exactly one of
    the expected texts (no normalization), MinCER = mean over items of the
    lowest CER against any expected text; also split by left context."""
    acc = {True: [0, 0], False: [0, 0]}
    cer = 0.0
    for row in rows:
        got = texts.get((row["source"], row["id"]), "").strip()
        has = bool(row.get("context"))
        acc[has][0] += 1
        acc[has][1] += got in row["forms"]
        cer += min(distance(f, got) / len(f) for f in row["forms"])
    n = acc[True][0] + acc[False][0]
    return {"acc1": acc[True][1] + acc[False][1], "mincer": cer / max(n, 1),
            "ctx_n": acc[True][0], "ctx_acc1": acc[True][1], "noctx_n": acc[False][0], "noctx_acc1": acc[False][1]}


def wilson(k: int, n: int) -> str:
    """95% interval of k/n, in percent."""
    if not n:
        return ""
    z, p = 1.96, k / n
    mid = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return f"{100 * (mid - half):.1f}–{100 * (mid + half):.1f}"


def mcnemar(b: int, c: int) -> float:
    """Exact two-sided McNemar p for b vs c discordant pairs."""
    n = b + c
    if not n:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def significance(per_row: dict, scores: dict) -> list[str]:
    """TEKITO vs each other input method on the same set and rows: right (exact
    or A) on rows where only one of the two is right, exact McNemar test."""
    good = {"exact", "A"}
    lines = []
    by_set = defaultdict(list)
    for key in per_row:
        system, set_name = key.split("__")
        by_set[set_name].append(system)
    for set_name, systems in sorted(by_set.items()):
        # Real input against real input when TEKITO was measured that way too.
        ours = [s for s in systems if s.startswith("real.tekito")] or [s for s in systems if s.startswith("tekito.")]
        others = [s for s in systems if s.startswith("real.") and not s.startswith("real.tekito")]
        for a in ours:
            for b in others:
                ra, rb = per_row[f"{a}__{set_name}"], per_row[f"{b}__{set_name}"]
                common = [r for r in ra if r in rb]
                x = sum(1 for r in common if ra[r] in good and rb[r] not in good)
                y = sum(1 for r in common if rb[r] in good and ra[r] not in good)
                p = mcnemar(x, y)
                lines.append(f"| {set_name} | {a} | {b} | {len(common)} | {x} | {y} | {p:.3f}{' *' if p < 0.05 else ''} |")
    if not lines:
        return []
    return ["## Significance (TEKITO vs others, same rows)", "",
            "| set | TEKITO | other | rows | only TEKITO right | only other right | p (McNemar) |",
            "|---|---|---|---|---|---|---|"] + lines + ["", "* p < 0.05: the difference is unlikely to be chance.", ""]


def score_run(run: Path, extra: list[Path]) -> tuple[dict, dict]:
    group = group_of(run)
    sets = load_sets(group)
    labels = load_labels(group)
    scores, rows_out = {}, {}
    for r in [run] + extra:
        for (system, set_name), texts in load_outputs(r).items():
            if set_name not in sets:
                continue
            kind = sets[set_name]["kind"]
            rows = sets[set_name]["rows"]
            if kind == "ajimee":
                s, per = score_sentences(rows, texts, labels)
                s.update(score_ajimee(rows, texts))
            elif kind in ENGLISH_KINDS:
                s, per = score_english(rows, texts)
            elif kind in POST_KINDS:
                s, per = score_posts(rows, texts, labels)
            else:
                s, per = score_sentences(rows, texts, labels)
            s["kind"] = kind
            scores[f"{system}__{set_name}"] = s
            rows_out[f"{system}__{set_name}"] = per
    return scores, rows_out


# ---------- report

MODE_NAMES = {"jp": "Japanese", "live": "Japanese live", "mix": "Mix", "auto": "English Auto", "direct": "Direct"}


def family(system: str) -> str:
    mode = system.split(".")[-1]
    return {"live": "Japanese", "jp": "Japanese"}.get(mode, MODE_NAMES.get(mode, mode))


def pct(a, n):
    return f"{100 * a / n:.1f}" if n else "-"


def table(scores: dict, kinds: set[str], header: str, cell) -> list[str]:
    keys = sorted(k for k, s in scores.items() if s["kind"] in kinds)
    if not keys:
        return []
    lines = [header, "|" + "|".join("---" for _ in range(header.count("|") - 1)) + "|"]
    for k in keys:
        system, set_name = k.split("__")
        lines.append(cell(system, set_name, scores[k]))
    return lines + [""]


def report(run: Path, scores: dict, prev_scores: dict | None, prev_name: str | None, meta: dict,
           per_row: dict | None = None) -> str:
    group = group_of(run)
    out = [f"# {group} run {run.name}", ""]
    if meta:
        out += [f"repo {meta.get('repo', '?')} at {meta.get('commit', '?')}; {meta.get('note', '')}".strip(), ""]
    pend = sum(s.get("pending", 0) for s in scores.values())
    if pend:
        out += [f"**{pend} outputs not judged yet** (count as wrong in fair %): run judge-export / judge-import.", ""]
    out += ["## Sentences (Japanese, Japanese live, Mix)", ""]
    out += table(scores, {"ajimee", "ja", "jatypo", "mixB", "mixC"},
                 "| system | set | n | right % (exact) | fair % | 95% CI | +B % | CER % | not judged |",
                 lambda sy, se, s: f"| {sy} | {se} | {s['n']} | {pct(s['exact'], s['n'])} | **{pct(s['fair'], s['n'])}** | "
                                   f"{wilson(s['fair'], s['n'])} | {pct(s['lenient'], s['n'])} | {s['cer']:.1f} | {s['pending'] or ''} |")
    out += ["## AJIMEE-Bench (its own metrics)", ""]
    out += table(scores, {"ajimee"},
                 "| system | n | acc@1 % | 95% CI | MinCER | acc@1, items without left context |",
                 lambda sy, se, s: f"| {sy} | {s['n']} | **{pct(s['acc1'], s['n'])}** | {wilson(s['acc1'], s['n'])} | "
                                   f"{s['mincer']:.3f} | {pct(s['noctx_acc1'], s['noctx_n'])} ({s['noctx_n']}) |")
    if any(s["kind"] == "ajimee" for s in scores.values()):
        out += ["AJIMEE items are typed without their left context (input methods did not read context put in",
                "the text box), so only the items without context are fully comparable with published results.", ""]
    out += ["## Posts (tweet-like, several sentences)", ""]
    out += table(scores, POST_KINDS,
                 "| system | set | posts | right % (exact) | fair right % | places/post (fair) | places/post (raw) | CER % | not judged |",
                 lambda sy, se, s: f"| {sy} | {se} | {s['n']} | {pct(s['exact'], s['n'])} | **{pct(s['fair'], s['n'])}** | "
                                   f"**{s['places']:.2f}** | {s['raw_places']:.2f} | {s['cer']:.1f} | {s['pending'] or ''} |")
    out += ["## English", ""]
    out += table(scores, ENGLISH_KINDS,
                 "| system | set | n | right % | slips fixed | correct words broken | places/row | changed from typed |",
                 lambda sy, se, s: f"| {sy} | {se} | {s['n']} | **{pct(s['exact'], s['n'])}** | "
                                   f"{s['fixed']}/{s['slips']}{' (' + pct(s['fixed'], s['slips']) + '%)' if s['slips'] else ''} | "
                                   f"{s['broken']} | {s['places']:.2f} | {s['changed']} |")
    out += ["Direct (real.tekitodirect) must leave every row as typed: its 'changed from typed' must be 0.", ""]
    out += significance(per_row or {}, scores)
    out += regression(scores, prev_scores, prev_name)
    out += ["fair % = exact (width, case, spaces ignored) + notation variants judged A. +B = also other",
            "readings judged to read naturally. places/post counts places to fix in sentences not exact/A.", ""]
    return "\n".join(out)


def regression(scores: dict, prev: dict | None, prev_name: str | None) -> list[str]:
    if not prev:
        return ["## Against the previous run", "", "No previous run of this group to compare with.", ""]
    out = [f"## Against the previous run ({prev_name})", ""]
    worse, better = [], []
    fam = defaultdict(list)
    for k, s in sorted(scores.items()):
        p = prev.get(k)
        if not p or p.get("n") != s.get("n"):
            continue
        system, set_name = k.split("__")
        d_fair = s["fair"] - p["fair"]
        msgs_w, msgs_b = [], []
        limit = max(2, round(0.01 * s["n"]))
        if d_fair <= -limit:
            msgs_w.append(f"fair {pct(p['fair'], p['n'])}→{pct(s['fair'], s['n'])} ({d_fair:+d})")
        elif d_fair >= limit:
            msgs_b.append(f"fair {pct(p['fair'], p['n'])}→{pct(s['fair'], s['n'])} ({d_fair:+d})")
        if "places" in s and s["kind"] in POST_KINDS:
            d = s["places"] - p["places"]
            if d >= 0.05:
                msgs_w.append(f"places/post {p['places']:.2f}→{s['places']:.2f}")
            elif d <= -0.05:
                msgs_b.append(f"places/post {p['places']:.2f}→{s['places']:.2f}")
        if s["kind"] in ENGLISH_KINDS:
            if s["broken"] - p["broken"] >= 2:
                msgs_w.append(f"broken words {p['broken']}→{s['broken']}")
            if s["fixed"] - p["fixed"] <= -2:
                msgs_w.append(f"slips fixed {p['fixed']}→{s['fixed']}")
            if s["fixed"] - p["fixed"] >= 2:
                msgs_b.append(f"slips fixed {p['fixed']}→{s['fixed']}")
        elif s["kind"] not in POST_KINDS and s["cer"] - p["cer"] >= 0.3:
            msgs_w.append(f"CER {p['cer']:.1f}→{s['cer']:.1f}")
        if p.get("pending") or s.get("pending"):
            note = " (judging incomplete in one run)"
        else:
            note = ""
        if msgs_w:
            worse.append(f"- **{system} {set_name}**: " + ", ".join(msgs_w) + note)
        if msgs_b:
            better.append(f"- {system} {set_name}: " + ", ".join(msgs_b) + note)
        if s["n"]:
            fam[family(system)].append(100 * d_fair / s["n"])
    out += ["Regressions:"] + (worse or ["- none"]) + ["", "Improvements:"] + (better or ["- none"]) + [""]
    if fam:
        out += ["Balance (mean change in fair/right %, per mode): " +
                ", ".join(f"{f} {sum(v) / len(v):+.1f}" for f, v in sorted(fam.items())), ""]
    return out


def previous_run(run: Path) -> Path | None:
    runs = sorted(p for p in run.parent.iterdir() if p.is_dir() and (p / "scores.json").exists() and p.name < run.name)
    return runs[-1] if runs else None


def cmd_score(args) -> int:
    run = Path(args.run).resolve()
    extra = [Path(p).resolve() for p in args.with_runs]
    scores, per_row = score_run(run, extra)
    prev = None if args.prev == "none" else (Path(args.prev).resolve() if args.prev else previous_run(run))
    prev_scores = json.loads((prev / "scores.json").read_text(encoding="utf-8"))["scores"] if prev else None
    meta_path = run / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    text = report(run, scores, prev_scores, prev.name if prev else None, meta, per_row)
    (run / "report.md").write_text(text, encoding="utf-8", newline="\n")
    group = group_of(run)
    rows_name = "rows.json.gz" if group == "heldout" else "rows.json"
    write_text(run / rows_name, json.dumps(per_row, ensure_ascii=False))
    (run / "scores.json").write_text(json.dumps({"scores": scores}, indent=1), encoding="utf-8")
    if group == "dev" and prev:
        flips(run, prev, per_row)
    if group == "heldout":
        # Scores only, safe to hand to the developer.
        dest = KIT / "scores" / f"heldout_{current_cycle()}_{run.name}.md"
        dest.write_text(text, encoding="utf-8", newline="\n")
        print(f"(copied to {dest.relative_to(KIT)})")
    print(text)
    return 0


def flips(run: Path, prev: Path, per_row: dict) -> None:
    """Dev only: rows that went right->wrong or wrong->right since the previous run."""
    old_path = prev / "rows.json"
    if not old_path.exists():
        return
    old = json.loads(old_path.read_text(encoding="utf-8"))
    sets = load_sets("dev")
    good = {"exact", "A"}
    lines = [f"# Rows changed since {prev.name}", ""]
    for key, rows in sorted(per_row.items()):
        set_name = key.split("__")[1]
        meant = {f"{r['source']}:{r['id']}": r["meant"] for r in sets.get(set_name, {"rows": []})["rows"]}
        lost = [r for r, v in rows.items() if v not in good and old.get(key, {}).get(r) in good]
        won = [r for r, v in rows.items() if v in good and old.get(key, {}).get(r) not in good | {None}]
        if lost or won:
            lines.append(f"## {key}: {len(lost)} lost, {len(won)} won")
            lines += [f"- lost {r}: {meant.get(r, '')}" for r in lost]
            lines += [f"- won {r}: {meant.get(r, '')}" for r in won]
            lines.append("")
    (run / "flips.md").write_text("\n".join(lines), encoding="utf-8", newline="\n")


# ---------- judging

def cmd_judge_export(args) -> int:
    group = args.group
    runs = [Path(r).resolve() for r in args.runs] or sorted(
        p for p in runs_dir(group).iterdir() if (p / "out").exists())
    sets = load_sets(group)
    labels = load_labels(group)
    pairs = {}
    for run in runs:
        for (system, set_name), texts in load_outputs(run).items():
            s = sets.get(set_name)
            if not s or s["kind"] not in JUDGED_KINDS:
                continue
            for row in s["rows"]:
                got = texts.get((row["source"], row["id"]))
                if got is None or verdict(row, got, labels) != "?":
                    continue
                pairs[(norm(row["meant"]), norm(got))] = (row["meant"], got.strip())
    jd = group_dir(group) / "judging"
    jd.mkdir(exist_ok=True)
    if list(jd.glob("batch_*.tsv")):
        sys.exit(f"{jd} still has batches; import them first")
    items = list(pairs.values())
    random.Random().shuffle(items)  # no order to tell which input method wrote what
    batches = [items[i:i + args.size] for i in range(0, len(items), args.size)]
    for b, batch in enumerate(batches, 1):
        text = "".join(f"{b}-{i}\t{m}\t{o}\n" for i, (m, o) in enumerate(batch, 1))
        (jd / f"batch_{b:02d}.tsv").write_text(text, encoding="utf-8", newline="\n")
    print(f"{len(items)} outputs to judge in {len(batches)} batches in {jd}")
    return 0


def cmd_judge_import(args) -> int:
    group = args.group
    jd = group_dir(group) / "judging"
    path = labels_path(group)
    existing = read_text(path) if path.exists() else ""
    added = 0
    missing = []
    for batch in sorted(jd.glob("batch_*.tsv")):
        if batch.name.endswith(".labels.tsv"):
            continue
        lab_path = batch.with_name(batch.stem + ".labels.tsv")
        if not lab_path.exists():
            missing.append(batch.name)
            continue
        items = {f[0]: (f[1], f[2]) for f in (l.split("\t") for l in batch.read_text(encoding="utf-8").splitlines()) if len(f) >= 3}
        for line in lab_path.read_text(encoding="utf-8").splitlines():
            f = line.split("\t")
            if len(f) < 2 or f[0] not in items or f[1].strip() not in LABELS:
                continue
            meant, got = items[f[0]]
            note = f[2].strip() if len(f) > 2 else ""
            existing += f"{meant}\t{got}\t{f[1].strip()}\t{note}\n"
            added += 1
        batch.unlink()
        lab_path.unlink()
    write_text(path, existing)
    print(f"added {added} labels to {path.name}" + (f"; batches without labels: {missing}" if missing else ""))
    return 0


def file_sha256(path: Path) -> str:
    import hashlib
    return hashlib.sha256(read_text(path).encode("utf-8")).hexdigest()


def cmd_check(args) -> int:
    """Checks result bundles before they are scored: meta.json says what was
    measured and how; every output file belongs to a set whose content has the
    hash recorded at measuring time, with each row of the set exactly once."""
    problems = []
    group = "dev"
    sets_path = sets_dir(group)
    kinds = json.loads((sets_path / "sets.json").read_text(encoding="utf-8"))
    for bundle in map(Path, args.bundles):
        meta_path = bundle / "meta.json"
        if not meta_path.exists():
            problems.append(f"{bundle}: no meta.json")
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        for key in ("date", "windows", "imes", "learning", "sets_sha256"):
            if key not in meta:
                problems.append(f"{bundle}: meta.json has no {key}")
        for path in sorted((bundle / "out").glob("*__*.tsv*")):
            system, set_name = path.name.split(".tsv")[0].split("__", 1)
            if set_name not in kinds:
                problems.append(f"{path}: no set {set_name}")
                continue
            set_file = sets_path / f"{set_name}.tsv{gz(group)}"
            if meta.get("sets_sha256", {}).get(set_name) != file_sha256(set_file):
                problems.append(f"{path}: measured on another version of set {set_name}")
            want = [(f[0], f[1]) for f in rows_of(set_file)]
            got = [(f[0], f[1]) for f in rows_of(path)]
            if sorted(got) != sorted(want):
                problems.append(f"{path}: rows differ from the set ({len(got)} vs {len(want)})")
    for p in problems:
        print("PROBLEM", p)
    print(f"checked {len(args.bundles)} bundles: {len(problems)} problems")
    return 1 if problems else 0


def cmd_agree_export(args) -> int:
    """A random sample of judged outputs, for a second, different judge."""
    rows = [f for f in rows_of(labels_path(args.group)) if len(f) >= 3 and f[2] in LABELS]
    random.Random(args.seed).shuffle(rows)
    jd = group_dir(args.group) / "judging"
    jd.mkdir(exist_ok=True)
    text = "".join(f"x-{i}\t{f[0]}\t{f[1]}\n" for i, f in enumerate(rows[:args.size], 1))
    (jd / "agree.tsv").write_text(text, encoding="utf-8", newline="\n")
    print(f"{min(args.size, len(rows))} judged outputs in {jd / 'agree.tsv'}; a second judge writes agree.labels.tsv")
    return 0


def cmd_agree_import(args) -> int:
    """Agreement of the second judge with the first: percent and Cohen's kappa."""
    jd = group_dir(args.group) / "judging"
    first = load_labels(args.group)
    items = {f[0]: (f[1], f[2]) for f in rows_of(jd / "agree.tsv")}
    pairs = []
    for f in rows_of(jd / "agree.labels.tsv"):
        if f[0] in items and f[1].strip() in LABELS:
            m, o = items[f[0]]
            pairs.append((first[(norm(m), norm(o))], f[1].strip()))
    n = len(pairs)
    po = sum(a == b for a, b in pairs) / n
    pe = sum((sum(a == l for a, _ in pairs) / n) * (sum(b == l for _, b in pairs) / n) for l in LABELS)
    kappa = (po - pe) / (1 - pe) if pe < 1 else 1.0
    fair = sum((a == "A") == (b == "A") for a, b in pairs) / n
    table = ["| first / second | " + " | ".join(LABELS) + " |", "|---|---|---|---|"]
    for a in LABELS:
        table.append(f"| {a} | " + " | ".join(str(sum(1 for x, y in pairs if x == a and y == b)) for b in LABELS) + " |")
    text = "\n".join([f"# Judge agreement ({args.group}, {args.note})", "",
                      f"{n} outputs judged twice: agreement {100 * po:.1f}%, Cohen's kappa {kappa:.2f}; "
                      f"same fair/not-fair decision (A vs B/C) {100 * fair:.1f}%.", ""] + table) + "\n"
    out = KIT / "scores" / f"judge_agreement_{args.group}.md"
    out.write_text(text, encoding="utf-8", newline="\n")
    (jd / "agree.tsv").unlink()
    (jd / "agree.labels.tsv").unlink()
    print(text)
    return 0


def cmd_rotate(args) -> int:
    cyc = KIT / "heldout" / args.cycle
    src = cyc / "sets"
    kinds = json.loads((src / "sets.json").read_text(encoding="utf-8"))
    dev_sets = KIT / "dev" / "sets"
    dev_kinds = json.loads((dev_sets / "sets.json").read_text(encoding="utf-8"))
    for name, kind in kinds.items():
        new = f"{args.prefix}_{name}"
        (dev_sets / f"{new}.tsv").write_text(read_text(src / f"{name}.tsv.gz"), encoding="utf-8", newline="\n")
        dev_kinds[new] = kind
    (dev_sets / "sets.json").write_text(json.dumps(dev_kinds, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    ho_labels = labels_path("heldout")
    if ho_labels.exists():
        dev_path = labels_path("dev")
        dev_text = dev_path.read_text(encoding="utf-8") if dev_path.exists() else ""
        dev_path.write_text(dev_text + read_text(ho_labels), encoding="utf-8", newline="\n")
    sources = cyc / "sources"
    if sources.exists():
        dest = KIT / "dev" / "sources" / args.prefix
        dest.mkdir(parents=True, exist_ok=True)
        for p in sources.iterdir():
            (dest / p.name.removesuffix(".gz")).write_text(read_text(p), encoding="utf-8", newline="\n")
    retired = KIT / "heldout" / "retired"
    retired.mkdir(exist_ok=True)
    shutil.move(str(cyc), str(retired / args.cycle))
    print(f"{args.cycle} is now dev ({', '.join(f'{args.prefix}_{n}' for n in kinds)}); "
          f"build the next cycle and write its name to heldout/current.txt")
    return 0


def main() -> int:
    # Reports hold Japanese and en dashes; a Japanese Windows console is cp932.
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("check")
    p.add_argument("bundles", nargs="+")
    p.set_defaults(func=cmd_check)
    p = sub.add_parser("score")
    p.add_argument("run")
    p.add_argument("--with", dest="with_runs", nargs="*", default=[])
    p.add_argument("--prev")
    p.set_defaults(func=cmd_score)
    p = sub.add_parser("judge-export")
    p.add_argument("group")
    p.add_argument("--runs", nargs="*", default=[])
    p.add_argument("--size", type=int, default=150)
    p.set_defaults(func=cmd_judge_export)
    p = sub.add_parser("judge-import")
    p.add_argument("group")
    p.set_defaults(func=cmd_judge_import)
    p = sub.add_parser("agree-export")
    p.add_argument("group")
    p.add_argument("--size", type=int, default=200)
    p.add_argument("--seed", type=int, default=1)
    p.set_defaults(func=cmd_agree_export)
    p = sub.add_parser("agree-import")
    p.add_argument("group")
    p.add_argument("--note", default="second judge")
    p.set_defaults(func=cmd_agree_import)
    p = sub.add_parser("rotate")
    p.add_argument("cycle")
    p.add_argument("prefix")
    p.set_defaults(func=cmd_rotate)
    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
