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
        self.ids = set()
        self.scripts = set()
        self.theme_options = 0
        self.in_theme_select = False
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
        if values.get("id"):
            self.ids.add(values["id"])
        if tag == "script" and values.get("src"):
            self.scripts.add(values["src"])
        if tag == "select" and values.get("id") == "theme-select":
            self.in_theme_select = True
        if tag == "option" and self.in_theme_select:
            self.theme_options += 1
        for attribute in ("href", "src"):
            if values.get(attribute):
                self.links.append(values[attribute])

    def handle_endtag(self, tag):
        if tag == "select":
            self.in_theme_select = False


pages = {}
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
    if "theme-select" not in parser.ids or parser.theme_options != 6:
        errors.append(f"{relative}: expected accessible six-option theme selector")
    if "/assets/theme-init.js" not in parser.scripts:
        errors.append(f"{relative}: missing early theme initialization")
    pages[page] = parser
    for link in parser.links:
        parsed = urlparse(link)
        if parsed.scheme or link.startswith(("mailto:", "tel:", "#")):
            if parsed.scheme == "http":
                errors.append(f"{relative}: external link must use HTTPS: {link}")
            continue
        if parsed.path.startswith("/"):
            target = ROOT / parsed.path.lstrip("/")
            if parsed.path.endswith("/"):
                target /= "index.html"
            if not target.exists():
                errors.append(f"{relative}: broken local reference {link}")
            elif parsed.fragment and target.suffix == ".html":
                target_parser = pages.get(target)
                if target_parser is None:
                    target_parser = PageParser()
                    target_parser.feed(target.read_text(encoding="utf-8"))
                if parsed.fragment not in target_parser.ids:
                    errors.append(f"{relative}: missing local fragment {link}")

if errors:
    print("\n".join(errors))
    sys.exit(1)
print(f"Site metadata, six-theme controls, and local references OK ({len(pages)} pages)")
