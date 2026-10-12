# Judging instructions (for the blind judge agent)

You judge Japanese input-method output. You get a batch file: one line per
item, tab-separated:

    <item id> <TAB> <meant text> <TAB> <output>

The meant text is what the person wanted to write. The output is what an
input method produced from the same keys. You are not told which input method
wrote an output, and you must not try to find out: read only the batch file
you were given, nothing else in this folder.

Read the output as a whole sentence, the way a reader of the message would,
and give each item one label:

- **A — same text, notation differs.** A reader gets exactly the meant words
  and meaning. Only the writing differs: kanji vs kana (あとで/後で,
  ください/下さい), okurigana, old/new or variant kanji of the same word,
  full/half width, punctuation style (、/，, ！/!), letter case of English
  (github/GitHub), a space or none between English and Japanese, an English
  word written in katakana for the same word (push/プッシュ) or the reverse.
- **B — other words, still reads naturally.** The output uses different words
  (usually a homophone) but the whole sentence still reads as natural,
  grammatical Japanese that someone could plausibly have meant, e.g. 会う/合う
  where both fit, 早い/速い where both fit. Use B only when a native reader
  would not stop at it as an error.
- **C — wrong.** Anything a reader would see as a conversion error: a word
  that does not fit the sentence, broken or odd phrase boundaries, leftover
  kana or romaji letters, English where Japanese was meant or the reverse
  (other than the same word as above), missing or extra text.

When unsure between A and B, ask: same words? (A). Between B and C: would a
careful reader of this message notice something wrong? (C).

Write your labels to the file named in your task (the batch name with
`.labels.tsv` instead of `.tsv`), one line per item, every item, tab-separated:

    <item id> <TAB> <A|B|C> <TAB> <a few words why, in English>

Keep reasons short (under 10 words). Do not change the batch file. Reply only
with the counts of A, B and C.
