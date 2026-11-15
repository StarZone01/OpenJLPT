import csv, hashlib, os
from pathlib import Path
import genanki

ROOT = Path("anki_exports")
OUT = Path("Japanese_JLPT_N5_N4_Full.apkg")
MODEL_ID = 2059111501
STYLE = """
.card { font-family: -apple-system, BlinkMacSystemFont, "Noto Sans JP", sans-serif; font-size: 24px; text-align: center; color: #222; background: #fff; padding: 22px; }
.nightMode .card { color: #eee; background: #222; }
.tags { font-size: 12px; color: #888; margin-top: 18px; }
hr { margin: 20px 0; }
"""
model = genanki.Model(
    MODEL_ID, "Japanese JLPT N5-N4 Full",
    fields=[{"name":"Front"},{"name":"Back"},{"name":"Tags"}],
    templates=[{
        "name":"Study",
        "qfmt":"<div class='prompt'>{{Front}}</div>",
        "afmt":"{{FrontSide}}<hr id='answer'><div>{{Back}}</div><div class='tags'>{{Tags}}</div>"
    }],
    css=STYLE
)
specs = [
    ("n5_vocabulary.tsv", "Japanese JLPT::N5::Vocabulary", 2059111502),
    ("n5_kanji.tsv", "Japanese JLPT::N5::Kanji", 2059111503),
    ("n5_grammar.tsv", "Japanese JLPT::N5::Grammar", 2059111504),
    ("n4_vocabulary.tsv", "Japanese JLPT::N4::Vocabulary", 2059111505),
    ("n4_kanji.tsv", "Japanese JLPT::N4::Kanji", 2059111506),
    ("n4_grammar.tsv", "Japanese JLPT::N4::Grammar", 2059111507),
]
decks=[]
total=0
for filename, deck_name, deck_id in specs:
    path=ROOT/filename
    deck=genanki.Deck(deck_id, deck_name)
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader=csv.DictReader(f, delimiter="\t")
        for row in reader:
            front=(row.get("Front") or "").strip()
            back=(row.get("Back") or "").strip()
            if not front:
                continue
            tags=[t for t in (row.get("Tags") or "").split() if t]
            guid=hashlib.sha1((deck_name+"\0"+front+"\0"+back).encode("utf-8")).hexdigest()[:20]
            note=genanki.Note(model=model, fields=[front,back," ".join(tags)], tags=tags, guid=guid)
            deck.add_note(note)
            total += 1
    decks.append(deck)
package=genanki.Package(decks)
package.write_to_file(OUT)
print(f"Created {OUT} with {total} notes across {len(decks)} subdecks; {OUT.stat().st_size} bytes")
