# Writing the rest of held-out cycle c3

Write NEW natural text people really type on a PC. Never copy from any corpus, website, book or earlier set. No duplicates. Follow WRITE_JA.md for the Japanese reading rules (chunks in hiragana, punctuation kept at the end of its chunk). Every line of a .jsonl file must be valid JSON.

## mix_A.jsonl, mix_B.jsonl, mix_C.jsonl (150 lines each): Japanese with English words
{"text": "...", "chunks": [...], "level": "A|B|C", "use": "..."}
- chunks: hiragana phrases, and each English word as its own chunk written "@word" in lower case, as typed (e.g. text "Netflixで" -> chunk "@netflix";  {"text": "明日のmeetingは10時から。", "chunks": ["あしたの", "@meeting", "は", "じゅうじから。"]} — note numbers are read in hiragana). Every sentence has 1-3 English words.
- A: common English words (meeting, PC, OK, email). B: words where case or spelling matters (iPhone, GitHub, Zoom, Slack), mixed with some Japanese homophones. C: product names, technical terms, abbreviations (Kubernetes, API, PR, CI), several English words.
- use: chat, work, names, numbers, tech, daily.

## ctx_ja.jsonl (200 lines): sentences that need the sentence before them
{"context": "<the previous sentence, plain Japanese>", "text": "...", "chunks": [...], "level": "B", "use": "..."}
- The text alone must be ambiguous (homophone) and the context decides it, e.g. context "新しい工場に機械を入れた。", text "きかいの調子がいい。" -> "機械の調子がいい。". No English.

## posts_ja.jsonl (200 lines): tweet-like posts, 2-4 sentences each
{"kind": "ja"|"mix", "text": "...", "chunks": [...]}
- 100 with kind "ja" (no Latin letters) and 100 with kind "mix" (1-4 English words, "@word" chunks).

## en_sentences.txt (300 lines) and posts_en.txt (100 lines)
- One correctly spelled English sentence (or one post of 2-3 sentences) per line, everyday chat, work mail and tech talk. Plain ASCII only.

## Extra rules (after the first draft)
- Mix sentences: no digits at all in the text (write numbers in kanji or avoid them), and no hyphens or other symbols inside English words.
- ctx_ja: the text ALONE must be read by a careful native reader as a genuinely ambiguous homophone choice (two or more conversions are equally natural without context), and the context must make exactly one of them right. Reject pairs where the text is clear by itself.
