# Contributing

<p><b>English</b> | <a href="CONTRIBUTING_JP.md">日本語</a></p>

## Sharing a result

1. Download `ImeBench.exe` from Releases (or build it, see the README) into `runner\`.
2. Run it, choose the input method and its mode in its text box, choose
   whether learning is on, and press **Start** or **Measure all**. Leave the
   PC alone until it is done.
3. Check the result:

   ```powershell
   python tools\bench.py check results\<your run>
   python tools\bench.py score results\<your run>
   ```

4. Open a pull request. **Share the result** in the app shows the steps and opens GitHub's upload page, where dragging the folder is enough. Or open a pull request yourself that adds the run folder under `results/` as it is.
   Name the folder `<date>-<input method>-<your name>` if you like; do not
   edit the files in it.
5. A check runs on the pull request. If it fails, the message says which row
   or field is wrong.
6. Outputs nobody has judged yet are judged by the maintainers, which can
   take a few days. Your result then appears on the results page as
   **community**.

One input method, one Windows build and one learning setting per run.

## Proposing a change

- **A wrong judgement:** open an issue with the line of `labels.tsv`.
- **New sentences or a new test:** open an issue first; held-out sets are
  written by the maintainers, so new public sentences become a later public set.
- **How scores are computed:** open an issue with the reason. Changes are made
  in public and noted in the README.

## Code

Pull requests to `runner/` and `tools/` are welcome. Keep the scoring
compatible with published results, or say why it changes.
