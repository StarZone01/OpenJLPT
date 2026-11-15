import csv
import hashlib
import re
from pathlib import Path

import genanki

ROOT = Path("anki_exports")
STYLE = r"""
.card { font-family: -apple-system, BlinkMacSystemFont, "Noto Sans JP", sans-serif; font-size: 21px; line-height: 1.65; text-align: left; color:#24313b; background:#fff; padding:20px; }
.nightMode .card { color:#edf2f7; background:#20242a; }
.prompt { text-align:center; font-size:1.35em; font-weight:700; padding:12px 4px; }
.audio-top { text-align:center; min-height:34px; margin:0 0 12px; }
.audio-top .replay-button, .audio-top a { font-size:1.05em; }
.headword { text-align:center; font-size:1.7em; font-weight:800; margin:8px 0 16px; }
.info { margin:8px 0; padding:9px 12px; border-radius:10px; background:#f0f4f8; }
.info-label { display:block; font-size:.72em; font-weight:800; letter-spacing:.06em; text-transform:uppercase; color:#526579; }
.example-ja { display:block; margin:13px 0 4px; padding:0 !important; border:0 !important; border-left:0 !important; border-radius:0 !important; background:transparent !important; box-shadow:none !important; color:inherit; font-size:1.17em; }
.example-en { margin:0 0 12px; padding:8px 14px 13px; color:#344b5b; font-size:.94em; }
ruby rt { color:#6d5593; font-size:.58em; font-weight:500; }
.match { font-weight:800; }
.noun { color:#245db2; }
.verb { color:#08784f; }
.adjective { color:#a65300; }
.adverb { color:#007c88; }
.particle { color:#a52f70; }
.grammar { color:#7541a5; }
.kanji { color:#48576a; }
.pair-0{color:#245db2}.pair-1{color:#08784f}.pair-2{color:#a65300}.pair-3{color:#a52f70}.pair-4{color:#7541a5}.pair-5{color:#007c88}.pair-6{color:#b0447b}.pair-7{color:#7b641c}
.v-a { color:#d13c3c; font-weight:900; } .v-i { color:#d07818; font-weight:900; }
.v-u { color:#9b8611; font-weight:900; } .v-e { color:#16824e; font-weight:900; }
.v-o { color:#2768bd; font-weight:900; }
.mnemonic { margin:13px 0; padding:12px 14px; border-left:4px solid #9b75c8; background:#f5f0fb; border-radius:7px; font-size:.93em; }
.legend { display:flex; flex-wrap:wrap; gap:5px 9px; font-size:10px; margin:5px 0 12px; color:#536170; }
.legend span { white-space:nowrap; }
.nightMode .info { background:#303945; } .nightMode .example-ja { background:transparent !important; border:0 !important; box-shadow:none !important; color:#d8f4f5; }
.nightMode .example-en { color:#d0dae4; } .nightMode .mnemonic { background:#332d40; }
.nightMode .noun { color:#a9c7ff; background:#243957; } .nightMode .verb { color:#a0e5bd; background:#1e4031; }
.nightMode .adjective { color:#ffd19a; background:#49351f; } .nightMode .adverb { color:#a2e9ed; background:#1c4145; }
.nightMode .particle { color:#f3b0d1; background:#48283a; } .nightMode .grammar { color:#d3b7f4; background:#3c2e50; }
.nightMode .kanji { color:#d0d9e5; background:#343d49; }
.tags { font-size:10px; color:#8a929c; margin-top:16px; }
hr { margin:17px 0; border:0; border-top:1px solid #ccd4dc; }
"""

FIELDS = [{"name":"Front"},{"name":"Back"},{"name":"Audio"},{"name":"Tags"}]
def model(mid, name, question, answer):
    return genanki.Model(mid, name, fields=FIELDS, templates=[{"name":"Card","qfmt":question,"afmt":answer}], css=STYLE)

recognition_model = model(
    2059111601, "Japanese JLPT Recognition",
    "<div class='audio-top'>{{tts ja_JP:Audio}}</div><div class='prompt'>{{Front}}</div>",
    "{{FrontSide}}<hr id='answer'>{{Back}}<div class='tags'>{{Tags}}</div>"
)
recall_model = model(
    2059111602, "Japanese JLPT Recall",
    "<div class='prompt'>{{Front}}</div>",
    "{{FrontSide}}<hr id='answer'><div class='audio-top'>{{tts ja_JP:Audio}}</div>{{Back}}<div class='tags'>{{Tags}}</div>"
)
listening_model = model(
    2059111603, "Japanese JLPT Listening",
    "<div class='audio-top'>{{tts ja_JP:Audio}}</div><div class='prompt'>Listen, then identify the word</div>",
    "{{FrontSide}}<hr id='answer'>{{Back}}<div class='tags'>{{Tags}}</div>"
)

def strip_tts(s):
    return re.sub(r"\[anki:tts\s+lang=[^]]+\](.*?)\[/anki:tts\]", r"\1", s, flags=re.S)

def add_furigana(s):
    return re.sub(r"\{([^{}|]+)\|([^{}|]+)\}", r"<ruby>\1<rt>\2</rt></ruby>", s)

def vowel_of(ch):
    hira = ord(ch)
    if 0x30A1 <= hira <= 0x30F6:
        ch = chr(hira - 0x60)
    groups = {
        "a":"あかさたなはまやらわがざだばぱぁゃ",
        "i":"いきしちにひみりぎじぢびぴぃ",
        "u":"うくすつぬふむゆるぐずづぶぷぅゅ",
        "e":"えけせてねへめれげぜでべぺぇ",
        "o":"おこそとのほもよろをごぞどぼぽぉょ",
    }
    for vowel, chars in groups.items():
        if ch in chars:
            return vowel
    return None

def color_vowels(s):
    out = []
    for ch in s:
        v = vowel_of(ch)
        out.append(f"<span class='v-{v}'>{ch}</span>" if v else ch)
    return "".join(out)

def classify(tags, term, meaning):
    t = term.replace("〜","")
    if "kanji" in tags: return "kanji"
    if "grammar" in tags or term.startswith("〜"): return "grammar"
    if t in {"は","が","を","に","へ","で","と","も","の","から","まで","より","ね","よ"}: return "particle"
    m = meaning.lower().strip()
    if m.startswith("to ") or m.startswith("become ") or m.startswith("be ") or "verb" in m: return "verb"
    if any(x in m for x in ["-like","blue","red","green","white","black","big","small","large","small","bright","dark","cold","hot","warm","easy","difficult","hard","good","bad","beautiful","quiet","busy","expensive","cheap","new","old","fast","slow","happy","sad"]): return "adjective"
    if m.endswith("ly") or m.startswith("very "): return "adverb"
    return "noun"

def highlight_japanese(line, term):
    plain = re.sub(r"\{([^{}|]+)\|([^{}|]+)\}", r"\1", line)
    base = term.replace("〜","").replace("（","").split("（")[0].strip()
    base = re.sub(r"[/／].*$","",base).strip()
    candidates = [base]
    # Inflected verbs and grammar forms: try useful substrings, longest first.
    for n in range(len(base)-1, 0, -1):
        for i in range(0, len(base)-n+1):
            piece = base[i:i+n]
            if piece not in candidates and not all(ch in "〜・（）() " for ch in piece):
                candidates.append(piece)
    target = next((x for x in candidates if len(x) >= 1 and x in plain), None)
    if not target:
        # For a kanji headword, a kanji stem commonly remains visible after conjugation.
        target = next((ch for ch in base if "\u4e00" <= ch <= "\u9fff" and ch in plain), None)
    if target:
        # Highlight one first occurrence in the original, retaining any furigana markup.
        pat = re.compile(r"\{([^{}|]+)\|([^{}|]+)\}")
        found = False
        def wrap_group(m):
            nonlocal found
            if not found and target in m.group(1):
                found = True
                return "<span class='match TARGET'>" + m.group(0) + "</span>"
            return m.group(0)
        line = pat.sub(wrap_group, line)
        if not found:
            line = line.replace(target, "<span class='match TARGET'>" + target + "</span>", 1)
    return line

def highlight_english(line, meaning, kind):
    words = [w.lower() for w in re.findall(r"[A-Za-z']{3,}", meaning) if w.lower() not in {"the","and","for","with","from","that","this","have","there","when","someone","something"}]
    for word in sorted(set(words), key=len, reverse=True):
        line = re.sub(r"(?i)\b(" + re.escape(word) + r")\b", r"<span class='match " + kind + r"'>\1</span>", line, count=1)
    return line

MORA_HOOKS = {
    "あ":"ah!", "い":"eel", "う":"ooze", "え":"egg", "お":"oar",
    "か":"car", "き":"key", "く":"cuckoo", "け":"cake", "こ":"coat",
    "さ":"saw", "し":"she", "す":"soup", "せ":"sail", "そ":"soap",
    "た":"taco", "ち":"cheese", "つ":"tsunami", "て":"tea", "と":"toe",
    "な":"gnat", "に":"knee", "ぬ":"noodle", "ね":"net", "の":"nose",
    "は":"hat", "ひ":"heel", "ふ":"food", "へ":"hen", "ほ":"hoe",
    "ま":"map", "み":"me", "む":"moo", "め":"met", "も":"mop",
    "や":"yarn", "ゆ":"you", "よ":"yoga", "ら":"ram", "り":"reef",
    "る":"ruler", "れ":"red", "ろ":"rope", "わ":"waffle",
    "が":"goat", "ぎ":"gift", "ぐ":"goo", "げ":"gate", "ご":"go",
    "ざ":"zebra", "じ":"jeep", "ず":"zoo", "ぜ":"zero", "ぞ":"zombie",
    "だ":"dog", "ぢ":"jeep", "づ":"zoo", "で":"desk", "ど":"dough",
    "ば":"ball", "び":"bee", "ぶ":"boot", "べ":"bell", "ぼ":"boat",
    "ぱ":"pan", "ぴ":"pizza", "ぷ":"pool", "ぺ":"pen", "ぽ":"pot",
    "きゃ":"key-cat", "しゃ":"shepherd", "ちゃ":"cheese", "にゃ":"nyan cat",
    "りょ":"Rio", "しゅ":"shoe", "ちょ":"choo-choo"
}
SPECIAL_WORD_STORIES = {
    "あう":"The sound is close to “ow!” Picture two people bumping noses, both cry “ow!”, then laugh because they have just met.",
    "あお":"“A-oar”: picture a huge oar painted bright blue. あお means blue.",
    "あか":"“A car”: picture a tiny car with brilliant red paint. あか means red.",
    "あかい":"“A car”: picture a tiny car with brilliant red paint. あかい means red.",
    "ねこ":"“Net-co”: picture a cat tangled in a fishing net, glaring at you. ねこ means cat.",
    "いぬ":"“Eel-noo”: picture a dog chasing an eel-shaped toy. いぬ means dog."
}
def morae(reading):
    s = re.sub(r"[ァ-ヶ]", lambda m: chr(ord(m.group(0))-0x60), reading)
    out=[]; i=0
    while i < len(s):
        if s[i] in "っんー・、。 ":
            i += 1; continue
        if i+1 < len(s) and s[i+1] in "ゃゅょ":
            out.append(s[i:i+2]); i += 2
        else:
            out.append(s[i]); i += 1
    return out

RADICAL_MEANINGS = {
    "日":"sun", "一":"one straight line", "人":"person", "亻":"person", "囗":"enclosure",
    "大":"a person spreading their arms wide", "木":"tree", "水":"water", "氵":"water drops",
    "火":"fire", "灬":"flames", "口":"mouth", "女":"woman", "子":"child", "心":"heart",
    "忄":"heart", "手":"hand", "扌":"hand", "言":"words", "糸":"thread", "金":"metal",
    "土":"earth", "山":"mountain", "艹":"grass", "宀":"roof", "辶":"a winding road",
    "刀":"sword", "刂":"blade", "力":"muscle", "月":"moon", "雨":"rain", "門":"gate",
    "田":"rice field", "禾":"grain", "足":"foot", "車":"cart", "食":"food", "貝":"shell",
    "魚":"fish", "虫":"insect", "王":"king", "石":"stone", "示":"altar", "彳":"step",
    "攵":"a hand taking action", "冫":"ice", "广":"shelter", "尸":"body", "犭":"animal",
    "疒":"illness", "戈":"spear", "酉":"sake jar", "竹":"bamboo", "米":"rice"
}
GRAMMAR_HOOKS = [
    ("やすい", "Yasu is the helpful guide: whenever Yasu joins a verb, the action becomes easy to do."),
    ("にくい", "Nicky is the stubborn gatekeeper: whenever Nicky blocks a verb, the action becomes difficult to do."),
    ("てしまう", "Shima sweeps the action completely off the table: it is finished, often with a sense of regret."),
    ("ておく", "Imagine doing the job and leaving it neatly in its place ahead of time: ておく is preparation."),
    ("てみる", "Mira says, “Let’s see!” She tries the action to find out what happens."),
    ("ていく", "Picture the action walking away from the speaker into the future: ていく moves onward."),
    ("てくる", "Picture the action coming back toward the speaker: てくる approaches the present."),
    ("始める", "A starter pistol fires: 始める marks the moment an action begins."),
    ("終わる", "A finish-line ribbon breaks: 終わる marks the action reaching its end."),
    ("続ける", "Imagine a runner continuing lap after lap: 続ける keeps the action going."),
    ("間に", "Picture one little event slipping into a gap on a timeline: 間に is at some point during the interval."),
    ("間", "Stretch a long ribbon across the whole timeline: 間 covers the entire period."),
    ("ばかり", "Imagine a plate piled with nothing but one food: ばかり means mostly/only that thing."),
    ("ところ", "Imagine a camera freezing one exact moment in an action: ところ marks that stage."),
    ("ながら", "Picture two hands working at once: ながら means doing one thing while doing another."),
    ("ために", "Imagine a clear target with an arrow pointing toward it: ために gives the purpose or reason."),
    ("ように", "Imagine setting a small goal sign so that an action reaches the intended result: ように expresses that aim."),
    ("たい", "Picture a big heart-shaped 'I WANT!' sign attached to the verb: たい marks desire."),
    ("ましょう", "Imagine inviting a friend with an open hand: ましょう is 'let's do it'."),
    ("ない", "Imagine a red stop sign over the verb: ない makes the action negative.")
]
def make_mnemonic(term, reading, meaning, tags, raw_lines):
    if "grammar" in tags:
        for key, story in GRAMMAR_HOOKS:
            if key in term:
                return "Memory story: " + story
        return f"Memory story: Imagine this pattern as a road sign saying “{meaning}”. When you see {term}, let that sign change how you understand the sentence."
    if "kanji" in tags:
        radical = ""
        for line in raw_lines:
            m = re.search(r"radical\s+([^;,.]+)", line, re.I)
            if m: radical = m.group(1).strip(); break
        part = RADICAL_MEANINGS.get(radical, f"the component {radical}" if radical else "the character's shape")
        return f"Visual story: Imagine {part} taking centre stage in a tiny scene about “{meaning}”. Let that picture remind you of {term}."
    r = reading or term
    if r in SPECIAL_WORD_STORIES:
        return "Sound-and-image story: " + SPECIAL_WORD_STORIES[r]
    ms = morae(r)
    hooks = [MORA_HOOKS.get(m, m) for m in ms[:2]]
    hook = " + ".join(hooks) if hooks else r
    gloss = meaning.split(";")[0].strip()
    if gloss.lower().startswith("to "):
        action = gloss[3:]
        scene = f"Imagine a giant {hooks[0] if hooks else 'object'} trying to {action} in an exaggerated, funny way."
    else:
        scene = f"Picture a giant {hooks[0] if hooks else 'object'} vividly transformed into “{gloss}”."
    return f"Sound hook: {r} → {hook}. {scene} Link that ridiculous image to {term} = {gloss}."


LEXICON = {}
PARTICLE_GLOSSES = {"の":["of","'s"],"は":["as for","is","are"],"が":["but","is","are"],"を":["the"],"に":["to","at","in"],"へ":["to","toward"],"で":["by","at","with","in"],"と":["and","with"],"も":["also","too"],"から":["from","because"],"まで":["until","to"],"より":["than"],"ね":["right","isn't it"],"ですね":["isn't it","right"]}
def load_lexicon():
    for path in ROOT.glob("n[45]_vocabulary.tsv"):
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f, delimiter="\t"):
                back = row.get("Back", "")
                tm = re.search(r"<b>(.*?)</b>", back)
                mm = re.search(r"Meaning:\s*(.*?)<br>", back)
                rm = re.search(r"Reading:\s*(.*?)<br>", back)
                if not tm or not mm: continue
                term = re.sub(r"<.*?>", "", tm.group(1)).strip()
                gloss = mm.group(1).split(";")[0].strip()
                reading = rm.group(1).strip() if rm else ""
                for key in (term, reading):
                    if key: LEXICON.setdefault(key, gloss)

def align_example(jp, en, term, meaning):
    pairs = []
    def english_match(gloss):
        gloss = gloss.strip().lower()
        variants = {
            "to meet": ["meet", "met", "meets", "meeting"], "meet": ["meet", "met", "meets", "meeting"],
            "to go": ["go", "goes", "went", "gone", "going"], "to come": ["come", "comes", "came", "coming"],
            "to see": ["see", "sees", "saw", "seen", "seeing"], "to eat": ["eat", "eats", "ate", "eaten", "eating"],
            "to buy": ["buy", "buys", "bought", "buying"], "to write": ["write", "writes", "wrote", "written", "writing"],
            "to read": ["read", "reads", "reading"], "to speak": ["speak", "speaks", "spoke", "spoken", "speaking"],
            "to do": ["do", "does", "did", "done", "doing"], "to make": ["make", "makes", "made", "making"],
        }
        candidates = variants.get(gloss, [gloss.removeprefix("to ")])
        return next((w for w in candidates if re.search(r"(?i)\b"+re.escape(w)+r"\b", en)), None)
    for token, glosses in PARTICLE_GLOSSES.items():
        if token in jp:
            found = next((english_match(g) for g in glosses if english_match(g)), None)
            if found: pairs.append((token, found))
    for m in re.finditer(r"\{([^{}|]+)\|([^{}|]+)\}", jp):
        base, reading = m.group(1), m.group(2)
        gloss = LEXICON.get(base) or LEXICON.get(reading)
        if not gloss:
            for vocab, vocab_gloss in LEXICON.items():
                if (base in vocab or vocab in base) and (reading in vocab or vocab in reading):
                    gloss = vocab_gloss
                    break
        if not gloss and any(ch in term for ch in base): gloss = meaning.split(";")[0].strip()
        found = english_match(gloss) if gloss else None
        if found: pairs.append((m.group(0), found))
    head = term.replace("〜","").strip()
    found = english_match(meaning.split(";")[0].strip())
    if head and found:
        stem = next((ch for ch in head if "\u4e00" <= ch <= "\u9fff" and ch in jp), None)
        target = stem or (head if head in jp else None)
        if target: pairs.insert(0,(target,found))
    jp_out, en_out, used_jp, used_en = jp, en, set(), set()
    for i,(j,e) in enumerate(pairs):
        if j in used_jp or e.lower() in used_en: continue
        used_jp.add(j); used_en.add(e.lower()); cls=f"pair-{i%8}"
        if j.startswith("{"):
            base, reading = j[1:-1].split("|",1)
            rep=f"<span class='{cls}'>{{{base}|{reading}}}</span>"
        else: rep=f"<span class='{cls}'>{j}</span>"
        jp_out=jp_out.replace(j,rep,1)
        en_out=re.sub(r"(?i)\b("+re.escape(e)+r")\b",r"<span class='"+cls+r"'>\1</span>",en_out,count=1)
    return jp_out,en_out

def format_back(raw, tags):
    raw = re.sub(r"\[anki:tts\s+lang=[^]]+\].*?\[/anki:tts\]", "", raw, flags=re.S)
    lines = [x.strip() for x in raw.split("<br>") if x.strip() and "Original memory cue:" not in x]
    if not lines: return ""
    term = re.sub(r"<.*?>", "", lines[0]).replace("<b>","").replace("</b>","") if lines[0].startswith("<b>") else ""
    reading = ""
    meaning = ""
    for line in lines:
        if line.startswith("Reading:"): reading = line.split(":",1)[1].strip()
        if line.startswith("Meaning:"): meaning = line.split(":",1)[1].strip()
    kind = classify(tags, term, meaning)
    out = ["<div class='legend'><span>🟦 Noun</span><span>🟩 Verb</span><span>🟧 Adjective</span><span>🩷 Particle</span><span>🟪 Grammar</span><span>🔤 Vowels: a/i/u/e/o</span></div>"]
    if term:
        head = f"<ruby>{term}<rt>{reading}</rt></ruby>" if reading and re.search(r"[\u4e00-\u9fff]", term) else term
        out.append(f"<div class='headword'><span class='match {kind}'>{head}</span></div>")
    for line in lines[1:]:
        if line.startswith("Reading:"):
            out.append(f"<div class='info'><span class='info-label'>Reading · vowel colours</span>{color_vowels(reading)}</div>")
        elif line.startswith("Meaning:"):
            value = line.split(":",1)[1].strip()
            out.append(f"<div class='info'><span class='info-label'>Meaning</span><span class='match {kind}'>{value}</span></div>")
        elif line.startswith("Formation:"):
            value = line.split(":",1)[1].strip()
            out.append(f"<div class='info'><span class='info-label'>Formation</span><span class='match grammar'>{value}</span></div>")
        elif line.startswith("<i>") and line.endswith("</i>"):
            value = line[3:-4]
            out.append(f"<div class='example-en'>{value}</div>")
        elif re.search(r"[ぁ-んァ-ヶ一-龯]", re.sub(r"<.*?>","",line)):
            out.append(f"<div class='example-ja'>{line}</div>")
        elif line.startswith("On:") or line.startswith("Kun:") or line.startswith("Strokes:") or line.startswith("Words:"):
            label, value = line.split(":",1)
            out.append(f"<div class='info'><span class='info-label'>{label}</span>{value.strip()}</div>")
        elif "Original memory cue:" in line:
            continue
        else:
            out.append(f"<div class='info'>{line}</div>")
    cue = make_mnemonic(term, reading, meaning, tags, lines)
    out.append(f"<div class='mnemonic'><b>Memory story</b><br>{cue}</div>")
    ja_idx = next((i for i,x in enumerate(out) if "example-ja" in x), None)
    en_idx = next((i for i,x in enumerate(out) if "example-en" in x), None)
    if ja_idx is not None and en_idx is not None:
        ja = re.sub(r"^.*?example-ja'>(.*?)</div>$", r"\1", out[ja_idx], flags=re.S)
        en = re.sub(r"^.*?example-en'>(.*?)</div>$", r"\1", out[en_idx], flags=re.S)
        ja,en = align_example(ja,en,term,meaning)
        out[ja_idx] = f"<div class='example-ja'>{add_furigana(ja)}</div>"
        out[en_idx] = f"<div class='example-en'>{en}</div>"
    return "\n".join(out)

load_lexicon()

specs = [
    ("n5_vocabulary.tsv", "Japanese JLPT N5::Vocabulary", 2059111611),
    ("n5_kanji.tsv", "Japanese JLPT N5::Kanji", 2059111612),
    ("n5_grammar.tsv", "Japanese JLPT N5::Grammar", 2059111613),
    ("n4_vocabulary.tsv", "Japanese JLPT N4::Vocabulary", 2059111621),
    ("n4_kanji.tsv", "Japanese JLPT N4::Kanji", 2059111622),
    ("n4_grammar.tsv", "Japanese JLPT N4::Grammar", 2059111623),
]

decks = {"N5": [], "N4": []}
totals = {"N5": 0, "N4": 0}
for filename, deck_name, deck_id in specs:
    level = "N5" if "n5_" in filename else "N4"
    deck = genanki.Deck(deck_id, deck_name)
    with (ROOT / filename).open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            front_raw = (row.get("Front") or "").strip()
            raw_back = (row.get("Back") or "").strip()
            if not front_raw: continue
            tags = [x for x in (row.get("Tags") or "").split() if x]
            audio_match = re.search(r"\[anki:tts\s+lang=[^]]+\](.*?)\[/anki:tts\]", raw_back, flags=re.S)
            audio = audio_match.group(1).strip() if audio_match else strip_tts(front_raw)
            front = strip_tts(front_raw)
            back = format_back(raw_back, tags)
            if not back: continue
            # Give kanji listening cards a real spoken word rather than an ambiguous isolated character.
            if "kanji" in tags:
                words = re.search(r"Words:\s*([^<]+)", raw_back)
                if words:
                    audio = words.group(1).split("、")[0].strip()
            if "listening" in tags:
                model_used = listening_model
                question = audio
            elif "recall" in tags:
                model_used = recall_model
                question = front
            else:
                model_used = recognition_model
                question = front
            guid = hashlib.sha1((deck_name + "\0" + question + "\0" + raw_back).encode("utf-8")).hexdigest()[:20]
            note = genanki.Note(model=model_used, fields=[question, back, audio, " ".join(tags)], tags=tags, guid=guid)
            deck.add_note(note)
            totals[level] += 1
    decks[level].append(deck)

for level in ("N5","N4"):
    out = Path(f"Japanese_JLPT_{level}.apkg")
    genanki.Package(decks[level]).write_to_file(out)
    print(f"Created {out} with {totals[level]} cards across {len(decks[level])} subdecks; {out.stat().st_size} bytes")
