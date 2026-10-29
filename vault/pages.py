#!/usr/bin/env python3
"""Blog posts and the collection page, written in the Obsidian vault `fragments`, published to the Hugo site.

  import  one time: copy the site's current posts, collection page and their images into the vault
  sync    write published posts to content/blog/ and the collection to content/collection.md

  fragments/blog/<slug>.md          one post per note; the filename is the address (/blog/<slug>/)
  fragments/blog/images/            images for posts, embedded in notes as ![[photo.jpg]]
  fragments/collection/collection.md
  fragments/collection/images/
"""
import datetime as dt
import re
import shutil
import sys
from pathlib import Path

from words import SITE, Note, dump_yaml

ROOT = Path(__import__("os").environ.get("KOTONOHA_VAULT", Path.home() / "Documents" / "fragments"))
BLOG, COLLECTION = ROOT / "blog", ROOT / "collection"
IMAGES = SITE / "static" / "images"


# ---------------------------------------------------------------- import (site -> vault, once)

def parse_toml_front(text):
    """The simple `key = value` TOML front matter Hugo wrote for the existing posts."""
    data = {}
    for line in text.splitlines():
        m = re.match(r"(\w+)\s*=\s*(.+)$", line.strip())
        if not m:
            continue
        key, raw = m.groups()
        if raw.startswith("["):
            data[key] = re.findall(r"""['"]([^'"]*)['"]""", raw)
        elif raw in ("true", "false"):
            data[key] = raw == "true"
        else:
            data[key] = raw.strip("'\"")
    return data


def split_front(text):
    m = re.match(r"(\+\+\+|---)\n(.*?)\n\1\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    fence, front, body = m.groups()
    from words import parse_yaml
    return (parse_toml_front(front) if fence == "+++" else parse_yaml(front)), body


def to_vault_images(body, kind, dest):
    """![](/images/blog/x.jpg) -> ![[x.jpg]], copying each image next to the notes."""
    def swap(m):
        name = m.group(2)
        src = IMAGES / kind / name
        if src.exists():
            dest.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest / name)
        return f"![[{name}]]"
    return re.sub(rf"!\[([^\]]*)\]\(/images/{kind}/([^)]+)\)", swap, body)


def write_note(path, meta, body):
    if path.exists():
        print(f"  skipped {path.relative_to(ROOT)} (already in the vault)")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{dump_yaml(meta)}\n---\n{body.lstrip(chr(10))}", encoding="utf-8")
    print(f"  imported {path.relative_to(ROOT)}")


def import_site():
    for src in sorted((SITE / "content" / "blog").glob("*.md")):
        if src.name == "_index.md":
            continue
        front, body = split_front(src.read_text(encoding="utf-8"))
        meta = {"title": front.get("title", src.stem), "date": front.get("date", ""),
                "tags": front.get("tags", []), "publish": not front.get("draft", False)}
        write_note(BLOG / src.name, meta, to_vault_images(body, "blog", BLOG / "images"))
    src = SITE / "content" / "collection.md"
    front, body = split_front(src.read_text(encoding="utf-8"))
    write_note(COLLECTION / "collection.md", {"title": front.get("title", "collection")},
               to_vault_images(body, "collection", COLLECTION / "images"))
    template = ROOT / "_templates" / "post.md"
    if not template.exists():
        template.parent.mkdir(parents=True, exist_ok=True)
        template.write_text('---\ntitle:\ndate: "{{date:YYYY-MM-DD}}"\ntags: []\npublish: false\n---\n', encoding="utf-8")
        print(f"  wrote {template.relative_to(ROOT)}")


# ---------------------------------------------------------------- sync (vault -> site)

def find_image(name):
    """Images can sit anywhere in the vault (Obsidian's attachment folder setting decides)."""
    for p in ROOT.rglob(name):
        if ".obsidian" not in p.parts and ".trash" not in p.parts:
            return p
    return None


def to_site(body, kind, posts):
    """Obsidian syntax -> plain Markdown: embeds become /images/<kind>/..., [[post]] links become real links."""
    def embed(m):
        name = m.group(1).split("|")[0].strip()
        src = find_image(name)
        if not src:
            print(f"  warning: image {name} not found in the vault")
            return ""
        dest = IMAGES / kind / src.name
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists() or dest.read_bytes() != src.read_bytes():
            shutil.copy2(src, dest)
            print(f"  copied static/images/{kind}/{src.name}")
        return f"![](/images/{kind}/{src.name})"

    def link(m):
        target, _, label = m.group(1).partition("|")
        target = target.split("#")[0].strip()
        return f"[{label or target}](/blog/{target}/)" if target in posts else (label or target)

    def convert(text):
        text = re.sub(r"!\[\[([^\]]+)\]\]", embed, text)
        text = re.sub(r"(?<!!)\[\[([^\]]+)\]\]", link, text)
        return re.sub(r"==(.+?)==", r"\1", text)
    return outside_code(body, convert)


def outside_code(body, fn):
    """Apply fn to the text but not inside ``` fences or `inline code`."""
    parts = re.split(r"(```.*?```|`[^`\n]*`)", body, flags=re.S)
    return "".join(part if i % 2 else fn(part) for i, part in enumerate(parts))


def hugo_date(value):
    v = str(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
        return f"{v}T00:00:00+09:00"
    return v or dt.datetime.now().astimezone().isoformat(timespec="seconds")


def sync():
    content = SITE / "content" / "blog"
    notes = [Note(p) for p in sorted(BLOG.glob("*.md")) if not p.name.startswith("_")] if BLOG.is_dir() else []
    published = [n for n in notes if n.get("publish") is True]
    posts = {n.word for n in published}
    keep = {"_index.md"}
    for n in published:
        meta = {"title": n.get("title") or n.word, "date": hugo_date(n.get("date")),
                "tags": n.get("tags") or [], "draft": False}
        for k, v in n.meta.items():  # anything else you add in Obsidian goes through as is
            if k not in meta and k != "publish":
                meta[k] = v
        out = content / f"{n.word}.md"
        text = f"---\n{dump_yaml(meta)}\n---\n{to_site(n.body, 'blog', posts)}"
        if not out.exists() or out.read_text(encoding="utf-8") != text:
            out.write_text(text, encoding="utf-8")
            print(f"  wrote content/blog/{out.name}")
        keep.add(out.name)
    if BLOG.is_dir():
        for f in content.glob("*.md"):
            if f.name not in keep:
                f.unlink()
                print(f"  removed content/blog/{f.name}")

    page = COLLECTION / "collection.md"
    if page.exists():
        n = Note(page)
        meta = {"title": n.get("title") or "collection"}
        text = f"---\n{dump_yaml(meta)}\n---\n{to_site(n.body, 'collection', posts)}"
        out = SITE / "content" / "collection.md"
        if out.read_text(encoding="utf-8") != text:
            out.write_text(text, encoding="utf-8")
            print("  wrote content/collection.md")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "sync"
    if cmd == "import":
        import_site()
    elif cmd == "sync":
        print("blog & collection")
        sync()
    else:
        sys.exit(__doc__)
