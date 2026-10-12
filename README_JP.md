<p align="center">
  <img src="assets/logotext.svg" alt="IME精度測定 IME Benchmark system" width="560">
</p>

<p align="center">
  Windows の日本語入力（IME）を測る、公開のベンチマークです。<br>
  日本語・英語・英語まじりの日本語を、どの IME にも同じ手順で打ちます。<br>
  出力と判定はすべて公開しています。
</p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="#方針">方針</a> ·
  <a href="#測り方">測り方</a> ·
  <a href="#結果ページ">結果ページ</a> ·
  <a href="#結果の共有">結果の共有</a> ·
  <a href="https://capitata.dev">capitata.dev</a>
</p>

小さな Windows アプリ（`runner/ImeBench.exe`）が、各文のローマ字を自分の入力欄に打
ち、モードに合わせて確定し（Space のあと Enter、または Enter）、入った文字を記録し
ます。読み取るのは使用中の IME が何かだけなので、TSF の IME ならどれでも測れます。

測る内容:

- **日本語**: 区切らずに打ったローマ字
- **英語**: 打ち間違いのある英文とない英文（英語を自動修正する IME 向け）
- **英語まじりの日本語**: 英単語の前後をスペースで区切る打ち方と、区切らない打ち方

## 方針

IME精度測定は、TEKITO という IME の作り手でもある Capitata が作っています。測られる
側が作るベンチマークは疑われて当然なので、信頼してもらうのではなく、確かめられる
ように作っています。

- **見せるためでなく、測るため。** IME の実力を知るためのもので、TEKITO が負けて
  いる結果や、見つかった TEKITO の不具合もそのまま載せます。
- **テストに合わせた調整をしない。** TEKITO の開発者が見られるのは held-out の点数
  だけで、文も出力も見ません。held-out の文はハッシュで TEKITO の学習データから除い
  ています。評価は TEKITO の開発とは切り離して行います。
- **すべての IME を同じ条件で。** TEKITO を含むすべての IME を、同じプログラムで同
  じキーを打って測ります。使うのは公開済みの版で、比べるのはこの計測だけです。
- **すべて確かめられる。** コード、セット、生の出力、すべての判定、held-out のハッ
  シュを公開しています。誰でもすべての結果を採点し直せます。
- **誰でも参加できる。** 結果の提出や、セット・方法の改善の提案はプルリクエストで
  受け付けます。採点方法を変えるときは、理由とともに公開の場で変えます。

## セット

| テスト | 内容 | 数 | 出典・ライセンス |
|---|---|---|---|
| AJIMEE | AJIMEE-Bench の全問を公開どおりに使用（ローマ字のキーを追加） | 200 | azooKey/AJIMEE-Bench、CC BY-SA 3.0 |
| MOZC | Mozc 評価データのうち変換結果が 1 つに決まる行 | 297 | google/mozc、BSD-3-Clause |
| JA | 日本語の文（短文〜長文） | 998 | このベンチ |
| JA-SLIP | JA の各文に打ち間違いを 2 つ入れたもの | 998 | このベンチ |
| MIX-SP | 英語まじりの日本語、英単語の前後をスペースで区切る | 500 | このベンチ |
| MIX-RUN | 同じ文を区切らずに打つ | 500 | このベンチ |
| EN | 英文 | 498 | このベンチ |
| EN-SLIP | EN の各文に打ち間違いを 2 つ入れたもの | 498 | このベンチ |
| POST-JA | 投稿のような文章（日本語） | 100 | このベンチ |
| POST-MIX-SP、POST-MIX-RUN | 英語まじりの投稿（区切りあり・なし） | 各 100 | このベンチ |
| POST-EN、POST-EN-SLIP | 英語の投稿（打ち間違いなし・あり） | 各 100 | このベンチ |

このベンチ用のセットは、held-out サイクル c1（`heldout/c1/` に無変更で公開。
`heldout/c1_commitments.txt` と一致）に、同じ方法で書いた文を足して大きくしたもので
す。現在の held-out サイクル c2 も、同じテストをほぼ同じ数で持っています。

**held-out セット**は、IME を調整する人が見ていない文で、数字の公正さを保つためのも
のです。

1. サイクルごとに Claude Sonnet 5.5 が新しく書きます（人が実際に打つ自然な文。既存
   のコーパスは使いません）。読みはすべて Claude Opus 5.5 が校正し、ローマ字のキーと
   合うことをスクリプトで確かめます。
2. 結果より先に、全ファイルの SHA-256 を公開します（`heldout/cN_commitments.txt`）。
3. サイクルを退役させたら中身を公開し、公開セットにします。

TEKITO の開発者が見られるのは held-out の点数だけです。学習データからの除外もハッシ
ュで行います。

## 判定

意図した文と違う出力が、いつも間違いとは限りません（後で／あとで、文に合う同音異義
語など）。言語モデルが、意図した文と出力だけを IME 名を伏せて見て、文全体で判定しま
す（`JUDGE.md`）。

- **A**: 同じ言葉で表記だけが違う（漢字とかな、送りがな、全角半角、大文字小文字）
- **B**: 違う言葉だが自然に読める
- **C**: 読む人が気づく誤り

（意図した文、出力）の組ごとに一度だけ判定し、`labels.tsv` で公開します。200 件で
Claude Opus 5.5 と Claude Sonnet 5.5 の判定は 98.5% 一致しました（Cohen's kappa
0.94）。ふだんの判定は Sonnet です。

## 指標

- **文**: 完全一致 %、**fair %**（完全一致 + A）、+B %、CER。95% 信頼区間（Wilson）付き
- **AJIMEE**: AJIMEE-Bench の acc@1 と MinCER
- **投稿**: 全体が正しい投稿の割合、**投稿 1 件あたりの修正箇所数**、CER
- **英語**: 正しい文の割合、直った打ち間違い、壊された正しい単語
- **比較**: 同じ文での正確な McNemar 検定。p ≥ 0.05 は差なしとします

## 測り方

1. Releases から `ImeBench.exe` を `runner\\` にダウンロードするか、一度だけビルドします（コンパイラは Windows に入っています）。

   ```powershell
   & "$env:WINDIR\Microsoft.NET\Framework64\v4.0.30319\csc.exe" -nologo -target:winexe -win32icon:runner\icon\app.ico -r:System.Drawing.dll -out:runner\ImeBench.exe runner\ImeBench.cs runner\ImeBenchApp.cs
   ```

2. `runner\ImeBench.exe` を起動し、入力欄をクリックして、いつもの方法（Win+Space な
   ど）で測る IME とモードにします。
3. セット、モード、学習の ON/OFF を選び、**測定開始** を押します。進捗バーが終わるま
   で PC には触らないでください。最初の 3 文がローマ字のままなら、止めて知らせます。

画面は日本語と英語を切り替えられます。結果は `results/<日時>-<名前>-<モード>/` に、
出力と `meta.json`（Windows のビルド、IME の DLL とバージョン、モード、学習、セット
の SHA-256、アプリのハッシュ）が入ります。続けて:

```powershell
python tools\bench.py check results\<run>
python tools\bench.py score results\<run>
```

`runner\realime.ps1` は、画面なしで複数の IME を測るメンテナー用です。

## 結果ページ

push のたびに `tools/site.py` が結果ページ（GitHub Pages、日本語と英語）を作ります。
fair % と 95% 信頼区間、全組み合わせの McNemar 検定、文ごとの出力を載せます。
`--pdf` を付けると、Chrome か Edge で A4 のレポート（`report.ja.pdf`、
`report.en.pdf`）も作ります。

## 結果の共有

手順は [CONTRIBUTING_JP.md](CONTRIBUTING_JP.md) にあります。

測った結果のフォルダを編集せずに `results/` に入れ、プルリクエストを出してください。
GitHub Actions が検査し（全行が 1 回ずつあるか、セットのハッシュ、必要な情報）、生の
出力から採点します。提出に書かれた点数は使いません。新しい出力はメンテナーが判定し
て `labels.tsv` に追加します。結果ページでは、メンテナーの計測を **verified**、それ
以外を **community** と表示します。

## 今後の予定

- 前の文脈ありの AJIMEE-Bench。プログラムで入力欄に入れた文を、測った IME は読みま
  せんでした。そのため今は外しています。
- 入力中に表示されるライブ変換と、英語まじりでのライブ変換
- 英語まじり入力での 1 文字あたりのキー数（モード切り替えも数える）
- 学習 OFF を主な条件にする

## ライセンス

コード（`runner/`、`tools/`、`.github/`）は Apache License 2.0（`LICENSE`）です。デ
ータはそれぞれのライセンスに従います。

| データ | ライセンス |
|---|---|
| `sets/ajimee.*` | CC BY-SA 3.0。azooKey/AJIMEE-Bench（コミット 401666cd）、日本語 Wikipedia 入力誤りデータセット v2 に基づく。ローマ字のキーを追加 |
| `sets/mozc.tsv` | BSD-3-Clause。google/mozc の `evaluation.tsv`（コミット b9c3fcbd）。ローマ字のキーを追加 |
| held-out の文、`results/`、`labels.tsv` | CC BY 4.0 |
| `assets/`、`runner/icon/`（ロゴ、アイコン） | Capitata が権利を保有 |

ロゴの文字は [851ゴチカクット](https://pm85122.onamae.jp/851fontpage.html)（試）と
[f.k 機械彫刻](https://font.kim/)（IME精度測定）をアウトライン化して使っています。
結果ページのデザインはデジタル庁デザインシステムを使用しています。

IME精度測定は [Capitata](https://capitata.dev) が作成しています。

<p align="center">
  <a href="https://capitata.dev">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset="assets/capitata-dark.png">
      <img src="assets/capitata-light.png" alt="Capitata" width="160">
    </picture>
  </a>
</p>
