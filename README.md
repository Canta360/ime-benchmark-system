<p align="center">
  <img src="assets/logotext.svg" alt="IME精度測定 IME Benchmark system" width="560">
</p>

<p align="center">
  An open benchmark for Japanese input methods on Windows.<br>
  Japanese, English, and Japanese with English words, typed the same way into every input method.<br>
  Every output and every judgement is published.
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

What is measured:

- **Japanese**: romaji typed without separators.
- **English**: English with and without slips, for input methods that correct it.
- **Japanese with English words**: typed with spaces around the English, and run together.

## Sets

| test | what | size | source, license |
|---|---|---|---|
| AJIMEE | AJIMEE-Bench, all items, exactly as published (romaji keys added) | 200 | azooKey/AJIMEE-Bench, CC BY-SA 3.0 |
| MOZC | Mozc evaluation rows with one expected conversion | 297 | google/mozc, BSD-3-Clause |
| JA | Japanese sentences, short to long | 998 | this benchmark |
| JA-SLIP | the JA sentences with two slips each | 998 | this benchmark |
| MIX-SP | Japanese with English words, Space around the English | 500 | this benchmark |
| MIX-RUN | the same, typed run together | 500 | this benchmark |
| EN | English sentences | 498 | this benchmark |
| EN-SLIP | the EN sentences with two slips each | 498 | this benchmark |
| POST-JA | tweet-like posts, Japanese | 100 | this benchmark |
| POST-MIX-SP, POST-MIX-RUN | posts with English words, spaced and run together | 100 each | this benchmark |
| POST-EN, POST-EN-SLIP | posts in English, as typed right and with slips | 100 each | this benchmark |

The sets written for this benchmark are held-out cycle c1 (published unchanged
in `heldout/c1/`, matching `heldout/c1_commitments.txt`) plus sentences
written the same way to make them larger. The current held-out cycle, c2, has
the same tests at about the same sizes.

**Held-out sets** keep the numbers honest: sentences nobody tuning an input
method has seen.

1. Written fresh each cycle by Claude Sonnet 5.5 (natural text people type,
   not from any corpus); every kana reading proofread by Claude Opus 5.5, and
   checked by script against the romaji keys.
2. The SHA-256 of every file is published before any result
   (`heldout/cN_commitments.txt`).
3. When the cycle is retired, the files are published and become public sets.

The TEKITO developer sees only held-out scores, and removes held-out text
from training data by hash.

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
   Leave the PC alone until the progress bar finishes. If the first three
   rows stay romaji, it stops and tells you.

The window is in Japanese or English. Results go to
`results/<date-time>-<name>-<mode>/`: the outputs and `meta.json` (Windows
build, the input method's DLL and version, mode, learning, the set's
SHA-256, the app's hash). Then:

```powershell
python tools\bench.py check results\<run>
python tools\bench.py score results\<run>
```

`runner\realime.ps1` measures several input methods without the window (for maintainers).

## Results page

`tools/site.py` builds the results page (GitHub Pages, Japanese and English)
on every push: fair % with 95% intervals, the McNemar test for every pair,
and every sentence's outputs. `--pdf` also writes A4 reports
(`report.ja.pdf`, `report.en.pdf`) with Chrome or Edge.

## Sharing results

The steps are in [CONTRIBUTING.md](CONTRIBUTING.md).

Add your run folder under `results/` in a pull request, without editing it.
GitHub Actions checks it (every row once, the set's hash, the metadata) and
scores it from the raw outputs; scores in a submission are never used.
Maintainers judge new outputs and add them to `labels.tsv`. The results page
marks maintainers' runs **verified** and others **community**.

## Planned

- AJIMEE-Bench with left context: the input methods measured did not read
  text placed in the box by the program, so it is left out for now.
- Live conversion as shown while typing, and in mixed input.
- Keystrokes per character in mixed input, counting mode switches.
- Learning off as the main condition.

## Principles

IME Benchmark system is made by Capitata, which also makes the TEKITO input
method. A benchmark run by one of the measured parties is easy to doubt, so
this one is built to be checked, not trusted.

- **A measure, not a showcase.** It exists to find out how input methods
  actually do, including where TEKITO does worse and TEKITO's own bugs.
- **No tuning to the test.** TEKITO's developers see only scores on held-out
  sets, never their sentences or outputs, and held-out text is removed from
  TEKITO's training data by hash. The sets are evaluated separately from
  TEKITO's development.
- **Same conditions for every input method.** Every input method, TEKITO
  included, is typed by the same program with the same keys, using released
  builds. Only these runs are compared.
- **Everything checkable.** Code, sets, raw outputs, every judgement and the
  held-out commitments are public. Anyone can re-score every result.
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
| held-out text, `results/`, `labels.tsv` | CC BY 4.0 |
| `assets/`, `runner/icon/` (logos, icon) | all rights reserved by Capitata |

The logo lettering uses [851ゴチカクット](https://pm85122.onamae.jp/851fontpage.html)
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
