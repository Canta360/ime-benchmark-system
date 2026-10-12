"""Builds the results page (site/index.html) from the result bundles: every
number is computed here from the raw outputs, the sets and labels.tsv.

  python tools/site.py [--out site]
"""
from __future__ import annotations

import argparse
import datetime
import os
import subprocess
import json
import math
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bench  # noqa: E402

ROOT = bench.KIT
NAMES = {
    "tekito": "TEKITO", "tekitolive": "TEKITO (live)", "tekitomix": "TEKITO Mix", "tekitoauto": "TEKITO Auto",
    "tekitodirect": "TEKITO Direct", "msime": "Microsoft IME", "google": "Google 日本語入力",
    "copilot": "Copilot Keyboard", "mozc": "Mozc", "meltype": "Meltype",
}
GOOD = {"exact", "A"}


def wilson(k: int, n: int) -> tuple[float, float]:
    if not n:
        return 0.0, 0.0
    z, p = 1.96, k / n
    mid = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return 100 * (mid - half), 100 * (mid + half)


def display(system: str) -> str:
    name = system.removeprefix("real.")
    base, _, mode = name.partition("-")
    return NAMES.get(base, base) + (f" ({mode})" if mode else "")


def find_browser() -> str:
    """A Chrome or Edge to print the page: CHROME, or the usual install paths."""
    candidates = [os.environ.get("CHROME", ""), "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
                  r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                  r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"]
    for c in candidates:
        if c and (shutil.which(c) or Path(c).exists()):
            return shutil.which(c) or c
    sys.exit("no Chrome or Edge found for --pdf (set CHROME)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "site"))
    ap.add_argument("--pdf", action="store_true", help="also write report.ja.pdf and report.en.pdf (A4) with a headless Chrome or Edge")
    args = ap.parse_args()
    sets = bench.load_sets("dev")
    labels = bench.load_labels("dev")
    data = {"sets": {}, "commitments": [], "generated": datetime.date.today().isoformat()}
    for bundle in sorted(p for p in (ROOT / "results").iterdir() if (p / "out").is_dir()):
        meta = json.loads((bundle / "meta.json").read_text(encoding="utf-8"))
        verified = "maintainer" in meta.get("measured_by", "")
        for (system, set_name), texts in bench.load_outputs(bundle).items():
            s = sets.get(set_name)
            if not s:
                continue
            entry = data["sets"].setdefault(set_name, {"kind": s["kind"], "rows": [], "systems": []})
            if not entry["rows"]:
                entry["rows"] = [{"id": f"{r['source']}:{r['id']}", "meant": r["meant"]} for r in s["rows"]]
            if s["kind"] in bench.ENGLISH_KINDS:
                # English: right is the sentence exactly as meant.
                en, per = bench.score_english(s["rows"], texts)
                sc = {"n": en["n"], "exact": en["exact"], "fair": en["exact"], "lenient": en["exact"], "pending": 0,
                      "cer": 0.0}
            else:
                sc, per = bench.score_sentences(s["rows"], texts, labels)
            lo, hi = wilson(sc["fair"], sc["n"])
            ime_key = system.removeprefix("real.").partition("-")[0]
            imes = meta.get("imes", {})
            # A mode of one input method (tekitolive) may be recorded under its name (tekito).
            info = imes.get(ime_key) or next((v for k, v in imes.items() if ime_key.startswith(k)), "")
            row_out = {f"{r['source']}:{r['id']}": texts.get((r["source"], r["id"]), "") for r in s["rows"]}
            sysd = {
                "system": system, "name": display(system), "bundle": bundle.name, "verified": verified,
                "date": meta.get("date", ""), "learning": meta.get("learning", ""), "windows": meta.get("windows", ""),
                "version": info if isinstance(info, str) else f"{info.get('product', '')} {info.get('version', '')}".strip(),
                "n": sc["n"], "exact": 100 * sc["exact"] / sc["n"], "fair": 100 * sc["fair"] / sc["n"],
                "lenient": 100 * sc["lenient"] / sc["n"], "cer": sc["cer"], "lo": lo, "hi": hi, "pending": sc["pending"],
                "verdict": per, "out": row_out,
            }
            if s["kind"] == "ajimee":
                aj = bench.score_ajimee(s["rows"], texts)
                sysd["acc1"] = 100 * aj["acc1"] / sc["n"]
                sysd["mincer"] = aj["mincer"]
            entry["systems"].append(sysd)
    # McNemar for every pair on the same set.
    for entry in data["sets"].values():
        systems = entry["systems"]
        entry["systems"].sort(key=lambda d: -d["fair"])
        pairs = {}
        for a in systems:
            for b in systems:
                if a is b:
                    continue
                common = [r for r in a["verdict"] if r in b["verdict"]]
                x = sum(1 for r in common if a["verdict"][r] in GOOD and b["verdict"][r] not in GOOD)
                y = sum(1 for r in common if b["verdict"][r] in GOOD and a["verdict"][r] not in GOOD)
                pairs[f"{a['system']}|{b['system']}"] = {"a": x, "b": y, "p": bench.mcnemar(x, y)}
        entry["pairs"] = pairs
    # Overview: each input method's main score on every set, side by side.
    order = {"ajimee": 0, "ja": 1, "jatypo": 2, "postsja": 3, "mixB": 4, "mixC": 5, "postsmixB": 6, "postsmixC": 7,
             "en": 8, "enclean": 9, "postsen": 10, "postsentypo": 11}
    names = sorted(data["sets"], key=lambda n: (order.get(data["sets"][n]["kind"], 99), n))
    rows = {}
    for set_name in names:
        for sysd in data["sets"][set_name]["systems"]:
            base = sysd["system"].removeprefix("real.").partition("-")[0]
            label = NAMES.get(base, base)
            row = rows.setdefault(label, {"name": label, "values": {}, "bundles": {}})
            if sysd["bundle"] >= row["bundles"].get(set_name, ""):
                row["values"][set_name] = sysd["fair"]
                row["bundles"][set_name] = sysd["bundle"]
    data["overview"] = {"sets": names, "rows": sorted(rows.values(), key=lambda r: r["name"])}
    for f in sorted((ROOT / "heldout").glob("*_commitments.txt")):
        data["commitments"].append({"cycle": f.stem.split("_")[0],
                                    "lines": [l for l in f.read_text(encoding="utf-8").splitlines() if l and not l.startswith("#")]})
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    page = (Path(__file__).parent / "site_template.html").read_text(encoding="utf-8")
    payload = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    (out / "index.html").write_text(page.replace("/*DATA*/null", payload), encoding="utf-8", newline="\n")
    shutil.copyfile(ROOT / "assets" / "logotext.svg", out / "logotext.svg")
    shutil.copyfile(ROOT / "assets" / "icon.png", out / "icon.png")
    for name in ("capitata.svg", "capitata-dark.png"):
        shutil.copyfile(ROOT / "assets" / name, out / name)
    print(f"wrote {out / 'index.html'}: {len(data['sets'])} sets")
    if args.pdf:
        browser = find_browser()
        for lang in ("ja", "en"):
            pdf = (out / f"report.{lang}.pdf").resolve()
            url = (out / "index.html").resolve().as_uri() + f"?print=1&lang={lang}"
            subprocess.run([browser, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                            "--run-all-compositor-stages-before-draw", "--virtual-time-budget=20000",
                            f"--print-to-pdf={pdf}", url], check=True, capture_output=True, timeout=180)
            print(f"wrote {pdf}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
