#!/usr/bin/env python3
"""words: Japanese words kept in the Obsidian vault `fragments`, published to radusz.com/words/.

  enrich  fill empty reading / accent / pos / ja / en fields from Japanese Wiktionary and Jisho
  sync    write every note with `publish: true` to content/words/ (and remove unpublished ones)
  today   write 今日の言葉.md into the vault: one published word for today + "a year ago" words
  all     enrich, sync, today

Notes live in $KOTONOHA_VAULT/kotonoha/ (default ~/Documents/fragments). The note's filename is the word.
"""
import datetime as dt
import json
import random
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path
import os

VAULT = Path(os.environ.get("KOTONOHA_VAULT", Path.home() / "Documents" / "fragments")) / "kotonoha"
SITE = Path(__file__).resolve().parent.parent
CONTENT = SITE / "content" / "words"
SITE_URL = "https://radusz.com/words/"
TODAY_NOTE = "_今日の言葉.md"
UA = "kotonoha/1.0 (https://radusz.com/words/)"

# traditional colour names -> hue, used for each word's sheet
COLORS = {"wakatake": 150, "fuji": 262, "nadeshiko": 340, "sora": 205,
          "yamabuki": 42, "byakuroku": 120, "usuzumi": 230, "sakura": 355}

FIELDS = ["found", "book", "author", "page", "publish", "color",
          "reading", "accent", "pos", "ja", "en", "enriched"]


# ---------------------------------------------------------------- notes

def parse_yaml(text):
    """Just enough YAML for Obsidian properties: scalars, quoted strings, [] and block lists."""
    data, key = {}, None
    for line in text.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        item = re.match(r"\s+-\s?(.*)$", line)
        if item and key:
            if not isinstance(data[key], list):
                data[key] = []
            data[key].append(scalar(item.group(1)))
            continue
        m = re.match(r"([^:\s][^:]*):\s*(.*)$", line)
        if not m:
            continue
        key, raw = m.group(1).strip(), m.group(2).strip()
        if raw.startswith("[") and raw.endswith("]"):
            inner = raw[1:-1].strip()
            data[key] = [scalar(x) for x in re.split(r",\s*", inner)] if inner else []
        else:
            data[key] = scalar(raw)
    return data


def scalar(raw):
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"') and len(raw) > 1:
        return json.loads(raw)
    if raw.startswith("'") and raw.endswith("'") and len(raw) > 1:
        return raw[1:-1].replace("''", "'")
    if raw in ("true", "false"):
        return raw == "true"
    return raw


def dump_yaml(data):
    def q(v):
        if isinstance(v, bool):
            return "true" if v else "false"
        s = str(v)
        if s == "" or re.search(r'[:#\[\]{}",\'&*!|>%@`]|^\s|\s$|^-', s) or s in ("true", "false"):
            return json.dumps(s, ensure_ascii=False)
        return s
    out = []
    for k, v in data.items():
        if isinstance(v, list):
            out.append(f"{k}:" if v else f"{k}: []")
            out += [f"  - {q(x)}" for x in v]
        elif v is None or v == "":
            out.append(f"{k}:")
        else:
            out.append(f"{k}: {q(v)}")
    return "\n".join(out)


class Note:
    def __init__(self, path):
        self.path = path
        self.word = path.stem
        text = path.read_text(encoding="utf-8")
        m = re.match(r"---\n(.*?)\n---\n?(.*)$", text, re.S)
        self.meta, self.body = (parse_yaml(m.group(1)), m.group(2)) if m else ({}, text)

    def save(self):
        self.path.write_text(f"---\n{dump_yaml(self.meta)}\n---\n{self.body}", encoding="utf-8")

    def get(self, key, default=""):
        v = self.meta.get(key, default)
        return default if v is None else v

    def section(self, title):
        m = re.search(rf"^##\s*{title}\s*\n(.*?)(?=^##\s|\Z)", self.body, re.S | re.M)
        return m.group(1).strip() if m else ""

    def quote(self):
        """The sentence from ## 出会い, and the word as written in it (==marked== in Obsidian, else the word)."""
        lines = [re.sub(r"^>\s?", "", l) for l in self.section("出会い").splitlines() if l.startswith(">")]
        text = "".join(l.strip() for l in lines)
        marked = re.search(r"==(.+?)==", text)
        text = clean_md(text)
        if marked:
            return text, marked.group(1)
        return text, self.word if self.word in text else ""

    def notes(self):
        return clean_md(self.section("覚え書き"), keep_md=True)


def clean_md(s, keep_md=False):
    s = re.sub(r"==(.+?)==", r"\1", s)
    s = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", s)
    s = re.sub(r"\[\[([^\]]+)\]\]", r"\1", s)
    if not keep_md:
        s = re.sub(r"[*_]{1,2}(.+?)[*_]{1,2}", r"\1", s)
    return s.strip()


def notes():
    if not VAULT.is_dir():
        sys.exit(f"No vault folder at {VAULT}")
    return [Note(p) for p in sorted(VAULT.glob("*.md"))
            if not p.name.startswith("_") and p.name != TODAY_NOTE]


# ---------------------------------------------------------------- dictionaries

def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.load(r)


def wiktionary_page(title):
    q = urllib.parse.urlencode({"action": "parse", "page": title, "prop": "wikitext",
                                "format": "json", "formatversion": 2, "redirects": 1})
    return fetch_json(f"https://ja.wiktionary.org/w/api.php?{q}").get("parse", {}).get("wikitext")


POS = {"noun": "名詞", "verb": "動詞", "adjective": "形容詞", "adjectivenoun": "形容動詞",
       "adverb": "副詞", "conjunction": "接続詞", "interjection": "感動詞", "prefix": "接頭辞",
       "suffix": "接尾辞", "pronoun": "代名詞", "particle": "助詞", "idiom": "成句",
       "phrase": "成句", "proverb": "ことわざ", "rentaishi": "連体詞"}


def strip_wiki(s):
    s = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", s)
    s = re.sub(r"<[^>]+>", "", s)
    for _ in range(3):
        s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    s = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]", r"\1", s)
    s = s.replace("'''", "").replace("''", "")
    return s.strip(" 　")


def wiktionary(word, hops=1):
    """Japanese definitions, accent and part of speech; follows 「〜を参照」 / wagokanji pointers once."""
    text = wiktionary_page(word)
    if not text:
        return None
    m = re.search(r"^==\s*(?:\{\{(?:L\|)?ja\}\}|日本語)\s*==\s*$(.*?)(?=^==[^=]|\Z)", text, re.S | re.M)
    if not m:
        return None
    ja = m.group(1)
    defs = [l[1:].strip() for l in ja.splitlines() if re.match(r"#(?![*:])", l)]
    pointer = re.search(r"\{\{wagokanji of\|([^}|]+)", ja)
    if not pointer and len(defs) == 1 and "参照" in defs[0]:
        pointer = re.search(r"\[\[([^\]|]+)", defs[0])
    if pointer and hops > 0:
        target = wiktionary(pointer.group(1).strip(), hops - 1)
        if target:
            return target
    acc = re.search(r"\{\{ja-pron[^}]*?\|acc=(\d+)", ja)
    pos = next((POS[p] for p in re.findall(r"^===+\s*\{\{(\w+)\}\}\s*===+", ja, re.M) if p in POS), "")
    clean = [d for d in (strip_wiki(d) for d in defs) if d and "参照" not in d]
    return {"ja": clean, "accent": acc.group(1) if acc else "", "pos": pos,
            "url": "https://ja.wiktionary.org/wiki/" + urllib.parse.quote(word)}


JISHO_POS = [("Suru verb", "サ変"), ("Noun", "名詞"), ("Na-adjective", "形容動詞"),
             ("I-adjective", "形容詞"), ("Adverb", "副詞"), ("verb", "動詞")]


def jisho(word):
    q = urllib.parse.quote(word)
    data = fetch_json(f"https://jisho.org/api/v1/search/words?keyword={q}").get("data", [])
    for entry in data:
        forms = entry.get("japanese", [])
        if any(word in (f.get("word"), f.get("reading")) for f in forms):
            form = next(f for f in forms if word in (f.get("word"), f.get("reading")))
            sense = entry["senses"][0]
            tags = " ".join(sense.get("parts_of_speech", []))
            pos = "・".join(ja for en, ja in JISHO_POS if en in tags)
            return {"reading": form.get("reading") or word,
                    "en": "; ".join(sense["english_definitions"][:4]), "pos": pos}
    return None


# ---------------------------------------------------------------- commands

def enrich():
    for n in notes():
        changed = False
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(n.get("found"))):  # empty, or a template placeholder left as is
            n.meta["found"] = dt.date.fromtimestamp(n.path.stat().st_birthtime).isoformat()
            changed = True
        if n.get("enriched") is not True:
            try:
                wk, js = wiktionary(n.word), jisho(n.word)
            except OSError as e:
                print(f"  {n.word}: lookup failed ({e}), will retry next run")
                wk = js = None
            if wk or js:
                wk, js = wk or {}, js or {}
                fill = {"reading": js.get("reading"), "accent": wk.get("accent"),
                        "pos": wk.get("pos") or js.get("pos"), "ja": wk.get("ja"), "en": js.get("en")}
                for k, v in fill.items():
                    if v and not n.get(k):
                        n.meta[k] = v
                n.meta["enriched"] = True
                print(f"  enriched {n.word}" + ("" if wk.get("ja") else " (no Wiktionary entry)"))
                changed = True
        for k in FIELDS:
            n.meta.setdefault(k, [] if k == "ja" else "")
        if changed:
            n.save()


def morae(reading):
    out = []
    for c in reading:
        if c in "ゃゅょぁぃぅぇぉャュョァィゥェォ" and out:
            out[-1] += c
        else:
            out.append(c)
    return out


KANA = dict(zip(
    "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをん"
    "がぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽぁぃぅぇぉゔ",
    "a i u e o ka ki ku ke ko sa shi su se so ta chi tsu te to na ni nu ne no ha hi fu he ho "
    "ma mi mu me mo ya yu yo ra ri ru re ro wa o n ga gi gu ge go za ji zu ze zo da ji zu de do "
    "ba bi bu be bo pa pi pu pe po a i u e o vu".split()))
YOON = {"ゃ": "a", "ゅ": "u", "ょ": "o"}


def romaji(reading):
    """Hepburn romaji for a kana reading, used as the page address: しゅんじゅん → shunjun."""
    kana = "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in reading)
    out, double = "", False
    for c in kana:
        if c == "っ":
            double = True
            continue
        if c == "ー":
            out += out[-1:] if out[-1:] in ("a", "i", "u", "e", "o") else ""
            continue
        if c in YOON and out and out[-1] == "i":
            base = out[:-1]
            out = base + ("" if base.endswith(("sh", "ch", "j")) else "y") + YOON[c]
            continue
        r = KANA.get(c, "")
        if double and r:
            r = ("t" if r.startswith("ch") else r[0]) + r
        double = False
        out += r
    return re.sub(r"[^a-z-]", "", out) or "word"


def hue(note):
    name = str(note.get("color")).strip().lower()
    if name in COLORS:
        return COLORS[name]
    return list(COLORS.values())[sum(map(ord, note.word)) % len(COLORS)]


def published():
    """Published notes, each with its page slug: the romaji reading, numbered when two words share it."""
    out, used = [], set()
    for n in notes():
        if n.get("publish") is not True:
            continue
        base = romaji(str(n.get("reading")) or n.word)
        slug, i = base, 2
        while slug in used:
            slug, i = f"{base}-{i}", i + 1
        used.add(slug)
        n.slug = slug
        out.append(n)
    return out


def sync():
    CONTENT.mkdir(parents=True, exist_ok=True)
    keep = set()
    for n in published():
        quote, qword = n.quote()
        reading = str(n.get("reading")) or n.word
        acc = str(n.get("accent")).strip()
        fm = {"title": n.word, "date": str(n.get("found")), "slug": n.slug,
              "reading": reading, "morae": morae(reading), "accent": int(acc) if acc.isdigit() else -1,
              "pos": n.get("pos"), "hue": hue(n),
              "ja": [d for d in n.get("ja", []) if d] if isinstance(n.get("ja"), list) else [n.get("ja")],
              "en": n.get("en"), "quote": quote, "qword": qword,
              "author": n.get("author"), "book": n.get("book"), "page": str(n.get("page"))}
        out = CONTENT / f"{n.slug}.md"
        text = json.dumps(fm, ensure_ascii=False, indent=2) + "\n\n" + n.notes() + "\n"
        if not out.exists() or out.read_text(encoding="utf-8") != text:
            out.write_text(text, encoding="utf-8")
            print(f"  wrote {out.relative_to(SITE)}")
        keep.add(out.name)
    for f in CONTENT.glob("*.md"):
        if f.name != "_index.md" and f.name not in keep:
            f.unlink()
            print(f"  removed {f.relative_to(SITE)}")


def today():
    words = published()
    date = dt.date.today()
    lines = [f"# 今日の言葉　{date.isoformat()}", ""]
    if not words:
        lines.append("No published words yet. Set `publish: true` on a note in this folder.")
    else:
        n = random.Random(date.isoformat()).choice(words)
        quote, _ = n.quote()
        source = "".join(filter(None, [n.get("author"), f"『{n.get('book')}』" if n.get("book") else ""]))
        lines += [f"## [[{n.word}]]", str(n.get("reading")), ""]
        if quote:
            lines += [f"> {quote}"] + ([f"> ――{source}"] if source else []) + [""]
        meaning = [f"> {d}" for d in (n.get("ja") or [])] + ([f"> {n.get('en')}"] if n.get("en") else [])
        if meaning:
            lines += ["> [!note]- 意味"] + meaning + [""]
        lines += [f"[{SITE_URL}{n.slug}/]({SITE_URL}{n.slug}/)", ""]
        past = [m for m in words
                if str(m.get("found"))[5:] == date.isoformat()[5:] and str(m.get("found"))[:4] < str(date.year)]
        if past:
            lines += ["### 一年前の今日"] + [f"- [[{m.word}]] ({m.get('found')})" for m in past]
    (VAULT / TODAY_NOTE).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  wrote {TODAY_NOTE}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    steps = {"enrich": [enrich], "sync": [sync], "today": [today], "all": [enrich, sync, today]}
    if cmd not in steps:
        sys.exit(__doc__)
    for step in steps[cmd]:
        print(step.__name__)
        step()
