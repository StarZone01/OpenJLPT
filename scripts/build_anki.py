import csv
import hashlib
import re
from pathlib import Path

import genanki

ROOT = Path("anki_exports")
OUT = Path("Japanese_JLPT_N5_N4_Full.apkg")

STYLE = """
.card {
  font-family: -apple-system, BlinkMacSystemFont, "Noto Sans JP", sans-serif;
  font-size: 22px; line-height: 1.65; text-align: left;
  color: #263238; background: #fff; padding: 20px;
}
.nightMode .card { color: #edf2f7; background: #20242a; }
.prompt { text-align: center; font-size: 1.35em; font-weight: 650; padding: 10px 4px; }
.headword { text-align: center; font-size: 1.45em; font-weight: 750; color: #245b9e; margin: 8px 0 16px; }
.info { margin: 8px 0; padding: 9px 12px; border-radius: 10px; background: #f0f4f8; }
.info-label { font-size: .78em; font-weight: 750; letter-spacing: .04em; text-transform: uppercase; color: #526579; display: block; }
.example-ja { margin-top: 13px; padding: 13px 14px; border-left: 5px solid #2996a6; border-radius: 8px; background: #eaf7f8; color: #153d48; font-size: 1.16em; }
.example-en { margin: 0 0 12px; padding: 8px 14px 12px; color: #39716b; font-size: .92em; }
ruby rt { color: #8752a1; font-size: .58em; }
.target { color: #a34d00; background: #ffedb8; border-radius: 4px; padding: 0 2px; font-weight: 800; }
.note { margin: 10px 0; padding: 9px 12px; border-left: 3px solid #9b83c7; background: #f5f1fa; border-radius: 6px; font-size: .9em; }
.nightMode .info { background: #303945; }
.nightMode .example-ja { background: #17343b; color: #d8f4f5; }
.nightMode .example-en { color: #a5d9d1; }
.nightMode .note { background: #332d40; }
.tags { font-size: 11px; color: #8a929c; margin-top: 18px; }
hr { margin: 18px 0; border: 0; border-top: 1px solid #ccd4dc; }
"""

FIELDS = [{"name": "Front"}, {"name": "Back"}, {"name": "Tags"}]
regular_model = genanki.Model(
    2059111501, "Japanese JLPT N5-N4 Study",
    fields=FIELDS,
    templates=[{
        "name": "Study",
        "qfmt": "<div class='prompt'>{{Front}}</div>",
        "afmt": "{{FrontSide}}<hr id='answer'>{{Back}}<div class='tags'>{{Tags}}</div>"
    }],
    css=STYLE,
)
listening_model = genanki.Model(
    2059111508, "Japanese JLPT N5-N4 Listening",
    fields=FIELDS,
    templates=[{
        "name": "Listen",
        "qfmt": "<div class='prompt'>{{tts ja_JP:Front}}</div>",
        "afmt": "{{FrontSide}}<hr id='answer'>{{Back}}<div class='tags'>{{Tags}}</div>"
    }],
    css=STYLE,
)

def strip_tts(text):
    return re.sub(r"\[anki:tts\s+lang=[^]]+\](.*?)\[/anki:tts\]", r"\1", text, flags=re.S)

def add_furigana(text):
    return re.sub(r"\{([^{}|]+)\|([^{}|]+)\}", r"<ruby>\1<rt>\2</rt></ruby>", text)

def format_back(raw):
    raw = add_furigana(strip_tts(raw))
    lines = [line.strip() for line in raw.split("<br>") if line.strip()]
    out = []
    term = ""
    if lines and lines[0].startswith("<b>"):
        term = re.sub(r"<.*?>", "", lines[0])
        out.append(f"<div class='headword'>{lines.pop(0)}</div>")
    for line in lines:
        if line.startswith("<i>") and line.endswith("</i>"):
            out.append(f"<div class='example-en'>{line}</div>")
        elif line.startswith("Reading:") or line.startswith("Meaning:") or line.startswith("Formation:"):
            label, value = line.split(":", 1)
            out.append(f"<div class='info'><span class='info-label'>{label}</span>{value.strip()}</div>")
        elif re.search(r"[ぁ-んァ-ヶ一-龯]", re.sub(r"<.*?>", "", line)):
            if term:
                needle = term.replace("〜", "")
                if needle and needle in line:
                    line = line.replace(needle, f"<span class='target'>{needle}</span>", 1)
            out.append(f"<div class='example-ja'>{line}</div>")
        elif "Original memory cue:" in line:
            out.append(f"<div class='note'>{line}</div>")
        else:
            out.append(f"<div class='info'>{line}</div>")
    return "\n".join(out)

specs = [
    ("n5_vocabulary.tsv", "Japanese JLPT::N5::Vocabulary", 2059111502),
    ("n5_kanji.tsv", "Japanese JLPT::N5::Kanji", 2059111503),
    ("n5_grammar.tsv", "Japanese JLPT::N5::Grammar", 2059111504),
    ("n4_vocabulary.tsv", "Japanese JLPT::N4::Vocabulary", 2059111505),
    ("n4_kanji.tsv", "Japanese JLPT::N4::Kanji", 2059111506),
    ("n4_grammar.tsv", "Japanese JLPT::N4::Grammar", 2059111507),
]

decks = []
total = 0
for filename, deck_name, deck_id in specs:
    deck = genanki.Deck(deck_id, deck_name)
    with (ROOT / filename).open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            front = strip_tts((row.get("Front") or "").strip())
            raw_back = (row.get("Back") or "").strip()
            if not front:
                continue
            back = format_back(raw_back)
            tags = [tag for tag in (row.get("Tags") or "").split() if tag]
            model = listening_model if "listening" in tags else regular_model
            guid = hashlib.sha1((deck_name + "\0" + front + "\0" + raw_back).encode("utf-8")).hexdigest()[:20]
            note = genanki.Note(
                model=model,
                fields=[front, back, " ".join(tags)],
                tags=tags,
                guid=guid,
            )
            deck.add_note(note)
            total += 1
    decks.append(deck)

package = genanki.Package(decks)
package.write_to_file(OUT)
print(f"Created {OUT} with {total} notes across {len(decks)} subdecks; {OUT.stat().st_size} bytes")
