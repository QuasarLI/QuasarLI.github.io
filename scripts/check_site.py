from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse
import sys

ROOT = Path(__file__).resolve().parents[1]
errors = []


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.title = False
        self.description = False
        self.lang = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "html" and values.get("lang"):
            self.lang = True
        if tag == "title":
            self.title = True
        if tag == "meta" and values.get("name") == "description" and values.get("content"):
            self.description = True
        for attribute in ("href", "src"):
            if values.get(attribute):
                self.links.append(values[attribute])


for page in [p for p in ROOT.rglob("*.html") if ".git" not in p.parts]:
    parser = PageParser()
    relative = page.relative_to(ROOT)
    try:
        parser.feed(page.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{relative}: invalid HTML ({exc})")
        continue
    if not parser.title:
        errors.append(f"{relative}: missing title")
    if page.name != "404.html" and not parser.description:
        errors.append(f"{relative}: missing meta description")
    if not parser.lang:
        errors.append(f"{relative}: missing html lang")
    for link in parser.links:
        parsed = urlparse(link)
        if parsed.scheme or link.startswith(("mailto:", "tel:", "#")):
            continue
        if parsed.path.startswith("/"):
            target = ROOT / parsed.path.lstrip("/")
            if parsed.path.endswith("/"):
                target /= "index.html"
            if not target.exists():
                errors.append(f"{relative}: broken local reference {link}")

if errors:
    print("\n".join(errors))
    sys.exit(1)
print("Site metadata and local references OK")
