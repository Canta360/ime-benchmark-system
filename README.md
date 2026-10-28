<p align="center">
  <img src="assets/logotext.svg" alt="IME精度測定 IME Benchmark system" width="560">
</p>

<p align="center">
  An open benchmark for Japanese input methods on Windows.<br>
  Japanese, English, and Japanese with English words, typed the same way into every input method.<br>
  Every output and every judgement is published.
</p>

<p align="center">
  <a href="https://canta360.github.io/ime-benchmark-system/"><img src="assets/results-banner.en.svg" alt="View the results" width="560"></a>
</p>

<p align="center">
  <a href="README_JP.md">日本語</a> ·
  <a href="#measuring">Measuring</a> ·
  <a href="#results-page">Results page</a> ·
  <a href="#sharing-results">Sharing results</a> ·
  <a href="#principles">Principles</a> ·
  <a href="https://capitata.dev">capitata.dev</a>
</p>

A small Windows app (`runner/ImeBench.exe`) types each sentence's romaji into
its own text box, commits as the mode needs (Space then Enter, or Enter), and
records the text. It reads only which input method is in use, so any TSF
input method can be measured.

What is measured, each kind shown on its own (no score adds them up):

- **Japanese**: romaji typed without separators.
- **Japanese with English words**, typed two ways and measured apart:
  - (1) in one mode, Space around the English, for input methods made for it;
  - (2) switching the input method's mode for the English, for every input method.
- **English**: typed in the input method's English mode.

## Sets

The current sets are cycle 3 (`sets/c3_*.tsv`). Every slip set has at most
one slip per sentence.

| test | what | size |
|---|---|---|
| JA-A / JA-B / JA-C | Japanese with little / some / much ambiguity (names, terms, numbers) | 300 / 298 / 298 |
| JA-SLIP | sentences from JA-A to C with one slip | 300 |
| JA-CTX | Japanese only the sentence before decides; that sentence is put in the box first | 200 |
| POST-JA / POST-JA-SLIP | tweet-like posts (right / up to one slip a sentence) | 100 posts (203 sentences) each |
| MIX-A / MIX-B / MIX-C | with English, little / some / much ambiguity (product names, abbreviations) | 148 / 147 / 150 |
| MIX-SLIP | with English and one slip (half in the Japanese, half in an English word) | 296 |
| POST-MIX / POST-MIX-SLIP | posts with English (right / with slips) | 99 posts (198 sentences) each |
| EN / EN-SLIP | English (right / one slip) | 300 each |
| POST-EN / POST-EN-SLIP | posts in English (right / one slip) | 100 posts each |
| AJIMEE | AJIMEE-Bench, all items, exactly as published (romaji keys added) | 200 |
| MOZC | Mozc evaluation rows with one expected conversion | 296 |

- The sets with English come for both ways of typing; (2) is `c3_mix*2.tsv`, switching at "|".
- Sizes are the rows scored: rows with the very same keys count once. Posts are typed and scored sentence by sentence.
- Each row's ambiguity and use (chat, work, names, numbers, tech, daily) is in `sets/c3_meta.tsv`.
- AJIMEE comes from azooKey/AJIMEE-Bench (CC BY-SA 3.0), MOZC from google/mozc (BSD-3-Clause); the rest was written for this benchmark.

The sentences were written fresh by Claude Sonnet 5.5 (JA-CTX by Claude Opus
5.5), not taken from any corpus; every kana reading was proofread by Claude
Opus 5.5 and checked by script against the romaji keys. The instructions and
the written sources are in `sources/c3/`.

**Earlier sets**: the sets before cycle 3 (JA, JA-SLIP, MIX-SP, MIX-RUN and
so on, with two slips) and the results measured on them stay as they are. The
held-out cycles c1 and c2 are published in `heldout/c1/` and `heldout/c2/`,
matching `heldout/c1_commitments.txt` and `heldout/c2_commitments.txt`.

## Judging

An output that differs from the meant text is not always wrong (後で/あとで,
or a homophone that fits). A language model judges each one as a whole
sentence, seeing only the meant text and the output, with no input method
names (`JUDGE.md`):

- **A**: same words, other notation (kanji/kana, okurigana, width, case)
- **B**: other words that still read naturally
- **C**: an error a reader would notice

Each (meant text, output) pair is judged once and published in `labels.tsv`.
Claude Opus 5.5 and Claude Sonnet 5.5 agreed on 98.5% of 200 outputs (Cohen's
kappa 0.94); Sonnet does routine judging.

## Metrics

- **Sentences**: exact %, **fair %** (exact + A), +B %, CER, with 95% Wilson intervals.
- **AJIMEE**: AJIMEE-Bench's own acc@1 and MinCER.
- **Posts**: posts right, **places to fix per post**, CER.
- **English**: sentences right, slips fixed, correct words broken.
- **Comparisons**: exact McNemar test on the same rows; p ≥ 0.05 counts as no difference.

## Measuring

1. Download `ImeBench.exe` from Releases into `runner\\`, or build it once (the compiler ships with Windows):

   ```powershell
   & "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe" -nologo -target:winexe -win32icon:runner\icon\app.ico -r:System.Drawing.dll -out:runner\ImeBench.exe runner\ImeBench.cs runner\ImeBenchApp.cs
   ```

2. Run `runner\ImeBench.exe`, click its text box, and switch to the input
   method and mode to measure as usual (Win+Space and so on).
3. Choose the set, the mode and whether learning is on, then press **Start**.
   If the first three rows stay romaji, it stops and tells you.

While it runs, it shows the rows and time left. Touching the mouse or keys
pauses it; it goes on 5 s after they stop, typing the row it was on again.

The window is in Japanese or English. Results go to
`results/<date-time>-<name>-<mode>/`:

- `out/`: the outputs
- `meta.json`: Windows build, the input method's DLL and version, mode,
  learning, the set's SHA-256, the app's hash
- `times/`: when each row was typed
- `manifest.sha256`: the hash of every file

Then:

```powershell
python tools\bench.py check results\<run>
python tools\bench.py score results\<run>
```

`runner\realime.ps1` measures several input methods without the window (for maintainers).

## Results page

`tools/site.py` builds the [results page](https://canta360.github.io/ime-benchmark-system/) (GitHub Pages, Japanese and
English) on every push:

- a rank per kind of text (Japanese, with English, English), with 95%
  intervals and whether each is different from the first
- a dot plot of the score on every set
- a page per input method: points written from the numbers, where it does
  better and worse, rows only it got wrong
- the McNemar test for every pair, and every sentence's outputs

`--pdf` also writes A4 portrait PDFs with Chrome or Edge, each with when and
where the results were measured:

| PDF | what |
|---|---|
| `report-summary.en.pdf` | summary (one page) |
| `report-full.en.pdf` | every set in full |
| `report.<input method>.en.pdf` | one input method (one page) |

Japanese ones end in `.ja.pdf`.

## Sharing results

The steps are in [CONTRIBUTING.md](CONTRIBUTING.md).

Add your run folder under `results/` in a pull request, without editing it.
**Share the result** in the app shows the steps and opens GitHub's upload page.
GitHub Actions checks it (every row once, the set's hash, the metadata, a
released build of the app, no file changed after measuring, each row typed in
the time its keys take) and scores it from the raw outputs; scores in a
submission are never used.
Maintainers judge new outputs and add them to `labels.tsv`. The results page
marks **verified** the maintainers' runs and runs whose sample of rows the
maintainers measured again with the same version and got the same outputs;
others are **community**.

## Planned

- Every input method on cycle 3, with learning and cloud features off as the
  main condition.
- The effort to fix a result, as the extra keys it takes.
- Live conversion as shown while typing.

## Principles

IME Benchmark system is made by Capitata, which also makes the TEKITO input
method. A benchmark run by one of the measured parties is easy to doubt, so
this one is built to be checked, not trusted.

- **A measure, not a showcase.** It exists to find out how input methods
  actually do, including where TEKITO does worse and TEKITO's own bugs.
- **No tuning to the test.** TEKITO is developed against its own tests, not
  this benchmark, and this benchmark is run apart from TEKITO's development.
- **Same conditions for every input method.** Every input method, TEKITO
  included, is typed by the same program with the same keys, using released
  builds. Only these runs are compared.
- **Everything checkable.** Code, sets, raw outputs and every judgement are
  public. Anyone can re-score every result.
- **Open to others.** Anyone can submit results or propose sets and changes
  through pull requests. Changes to how scores are computed are made in
  public, with the reason.

## License

Code (`runner/`, `tools/`, `.github/`): Apache License 2.0 (`LICENSE`). Data
keeps its own license:

| data | license |
|---|---|
| `sets/ajimee.*` | CC BY-SA 3.0; azooKey/AJIMEE-Bench (commit 401666cd), built on the Japanese Wikipedia Typo Dataset v2; romaji keys added |
| `sets/mozc.tsv` | BSD-3-Clause; google/mozc `evaluation.tsv` (commit b9c3fcbd); romaji keys added |
| text written for this benchmark (`sets/`, `heldout/`, `sources/`), `results/`, `labels.tsv` | CC BY 4.0 |
| `assets/`, `runner/icon/` (logos, icon) | all rights reserved by Capitata |

The logo lettering uses [851ゴチカクット](https://pm85122.onamae.jp/851Gkktt.html)
(試) and [f.k 機械彫刻](https://font.kim/) (IME精度測定), converted to outlines.
The results page uses the Digital Agency Design System.

IME Benchmark system is made by [Capitata](https://capitata.dev).

<p align="center">
  <a href="https://capitata.dev">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="assets/capitata-dark.png">
      <img src="assets/capitata-light.png" alt="Capitata" width="160">
    </picture>
  </a>
</p>
