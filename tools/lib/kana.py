"""Kana -> romaji keys (MS-IME style), and a reader that checks the keys type
the kana back with TEKITO's installed japanese-romaji table.

Vendored from the repo's eval/ja/kana-to-keys.py and the Romaji class in
scripts/en/build-expression-packs.py, so building sets does not move when
the repo does."""
from __future__ import annotations

import os
from pathlib import Path

ROMAJI = {
    "あ": "a", "い": "i", "う": "u", "え": "e", "お": "o",
    "か": "ka", "き": "ki", "く": "ku", "け": "ke", "こ": "ko",
    "さ": "sa", "し": "shi", "す": "su", "せ": "se", "そ": "so",
    "た": "ta", "ち": "chi", "つ": "tsu", "て": "te", "と": "to",
    "な": "na", "に": "ni", "ぬ": "nu", "ね": "ne", "の": "no",
    "は": "ha", "ひ": "hi", "ふ": "fu", "へ": "he", "ほ": "ho",
    "ま": "ma", "み": "mi", "む": "mu", "め": "me", "も": "mo",
    "や": "ya", "ゆ": "yu", "よ": "yo",
    "ら": "ra", "り": "ri", "る": "ru", "れ": "re", "ろ": "ro",
    "わ": "wa", "を": "wo", "ん": "nn",
    "が": "ga", "ぎ": "gi", "ぐ": "gu", "げ": "ge", "ご": "go",
    "ざ": "za", "じ": "ji", "ず": "zu", "ぜ": "ze", "ぞ": "zo",
    "だ": "da", "ぢ": "di", "づ": "du", "で": "de", "ど": "do",
    "ば": "ba", "び": "bi", "ぶ": "bu", "べ": "be", "ぼ": "bo",
    "ぱ": "pa", "ぴ": "pi", "ぷ": "pu", "ぺ": "pe", "ぽ": "po",
    "ゔ": "vu",
    "ぁ": "xa", "ぃ": "xi", "ぅ": "xu", "ぇ": "xe", "ぉ": "xo", "ゃ": "xya", "ゅ": "xyu", "ょ": "xyo",
    "ー": "-", "。": ".", "、": ",", "？": "?", "！": "!",
}
DIGRAPHS = {
    "しゃ": "sha", "しゅ": "shu", "しょ": "sho", "しぇ": "she", "ちゃ": "cha", "ちゅ": "chu", "ちょ": "cho",
    "ちぇ": "che", "じゃ": "ja", "じゅ": "ju", "じょ": "jo", "じぇ": "je", "てぃ": "thi", "でぃ": "dhi",
    "でゅ": "dhu", "ふぁ": "fa", "ふぃ": "fi", "ふぇ": "fe", "ふぉ": "fo", "うぃ": "wi", "うぇ": "we",
    "ゔぁ": "va", "ゔぃ": "vi", "ゔぇ": "ve", "ゔぉ": "vo",
}
for _kana, _c in zip("きぎにひびぴみり", "k g n h b p m r".split()):
    for _small, _vowel in (("ゃ", "a"), ("ゅ", "u"), ("ょ", "o")):
        DIGRAPHS[_kana + _small] = f"{_c}y{_vowel}"
MARKS = {".": "。", ",": "、", "!": "！", "?": "？", "-": "ー"}


def hiragana(text: str) -> str:
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)


def to_keys(kana: str) -> str | None:
    """The romaji keys a person types for `kana`, or None if a character cannot be typed."""
    kana = hiragana(kana)
    out = []
    i = 0
    double = False
    while i < len(kana):
        if kana[i] == "っ":
            double = True
            i += 1
            continue
        piece = DIGRAPHS.get(kana[i:i + 2])
        step = 2
        if piece is None:
            piece, step = ROMAJI.get(kana[i]), 1
        if piece is None:
            return None
        if piece == "nn":
            # ん before a consonant other than n, y: one n is enough.
            nxt = kana[i + 1:i + 2]
            following = DIGRAPHS.get(kana[i + 1:i + 3]) or ROMAJI.get(nxt, "")
            if following and following[0] not in "aiueony.,?!-" and nxt != "っ":
                piece = "n"
        if double:
            if not piece[0].isalpha() or piece[0] in "aiueon":
                out.append("xtu")
            else:
                piece = piece[0] + piece
            double = False
        out.append(piece)
        i += step
    if double:
        out.append("xtu")
    return "".join(out)


def data_dir() -> Path:
    return Path(os.environ.get("TEKITO_DATA_PACK_DIR") or Path(os.environ["LOCALAPPDATA"]) / "TEKITO" / "data")


class Romaji:
    """The japanese-romaji table, read the way JapaneseComposer reads keys."""

    def __init__(self, table: Path | None = None) -> None:
        table = table or data_dir() / "japanese-romaji" / "romaji.tsv"
        self.rules: dict[str, tuple[str, str]] = {}
        for line in table.read_text(encoding="utf-8").splitlines():
            keys, output, pending = line.split("\t")
            self.rules[keys] = (output, pending)
        self.longer = {keys[:i] for keys in self.rules for i in range(1, len(keys))}

    def kana(self, keys: str) -> str | None:
        """The kana `keys` type, or None when a key is left unread."""
        out: list[str] = []
        pending = ""

        def feed(key: str) -> bool:
            nonlocal pending
            for _ in range(64):
                typed = pending + key
                if typed in self.longer:
                    pending = typed
                    return True
                if typed in self.rules:
                    output, keep = self.rules[typed]
                    out.append(output)
                    pending = keep if typed.endswith(keep) else ""
                    return True
                if not pending:
                    return False
                if not flush_once():
                    return False
            return False

        def flush_once() -> bool:
            nonlocal pending
            held, pending = pending, ""
            for length in range(len(held), 0, -1):
                rule = self.rules.get(held[:length])
                if rule and not rule[1]:
                    out.append(rule[0])
                    return all(feed(rest) for rest in held[length:])
            return False

        for key in keys:
            if not feed(key):
                return None
        while pending:
            if not flush_once():
                return None
        return "".join(out)

    def reads_back(self, keys: str, kana: str) -> bool:
        """Whether `keys` (letters, then . , ! ? at the end) type exactly `kana`."""
        letters = keys.rstrip(".,!?")
        tail = "".join(MARKS[c] for c in keys[len(letters):])
        read = self.kana(letters) if letters else ""
        return read is not None and read + tail == hiragana(kana)
