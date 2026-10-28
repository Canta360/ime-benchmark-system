# Writing Japanese benchmark sentences (held-out cycle c3)

Write NEW natural Japanese sentences that people really type on a PC. Do not copy from any corpus, website, book or earlier set. No duplicates.

Output: JSON Lines, one object per line, UTF-8:
{"text": "<the sentence as meant>", "chunks": ["<hiragana phrase>", ...], "level": "A|B|C", "use": "<label>"}

- chunks: the reading of the text split into phrases (文節), all hiragana, in order. Joined together they must be exactly the reading of the whole text plus punctuation: keep 、。！？ at the end of the chunk it follows, exactly as in the text, e.g. {"text": "週末は釣りに行く。", "chunks": ["しゅうまつは", "つりに", "いく。"]}. Katakana words are read in hiragana (コーヒー -> こーひー). Numbers in text must be read as typed (e.g. 3時 -> さんじ); prefer writing numbers so the reading is unambiguous.
- No Latin letters in these sentences.
- level:
  - A: common everyday words, little ambiguity.
  - B: some homophones where context decides (e.g. 会う/合う, 早い/速い, 意外/以外, 機会/機械).
  - C: hard: proper nouns (people, places, companies), technical terms, numbers/dates/amounts, rare kanji words.
- use (one of): chat, work, names, numbers, tech, daily
- Length: mix short (8-15 chars), medium (16-35) and long (36-70) sentences, about 1:2:1.
- Spread the use labels evenly within each level (names/numbers/tech mostly in C).

Write each requested file in full; every line must be valid JSON.
