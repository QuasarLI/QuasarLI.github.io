from html.parser import HTMLParser
from pathlib import Path
import re
import unittest
from urllib.parse import urlparse
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
ROUTES = ("/cinedock/", "/cinedock/privacy/", "/cinedock/support/")
ORIGIN = "https://quasarli.github.io"


class CineDockParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids = []
        self.links = []
        self.scripts = []
        self.headings = 0
        self.canonical = None
        self.metadata = {}
        self.forbidden = []
        self.text = []
        self.navigations = []
        self.current_navigation = None
        self.elements = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        self.elements.append((tag, values))
        if tag == "nav":
            self.current_navigation = {
                "label": values.get("aria-label"),
                "classes": values.get("class", "").split(),
                "links": [],
            }
            self.navigations.append(self.current_navigation)
        if tag == "a" and self.current_navigation is not None:
            self.current_navigation["links"].append(values.get("href"))
        if "id" in values:
            self.ids.append(values["id"])
        if tag == "h1":
            self.headings += 1
        if tag == "link" and values.get("rel") == "canonical":
            self.canonical = values.get("href")
        if tag == "meta":
            self.metadata[values.get("property", values.get("name"))] = values.get("content")
        if tag == "script" and "src" in values:
            self.scripts.append(values["src"])
        if tag in ("form", "iframe", "video", "audio", "input") or "download" in values:
            self.forbidden.append(tag)
        for attribute in ("href", "src"):
            if attribute in values:
                self.links.append(values[attribute])

    def handle_data(self, data):
        self.text.append(data)

    def handle_endtag(self, tag):
        if tag == "nav":
            self.current_navigation = None


def read_page(route):
    page = ROOT / route.strip("/") / "index.html"
    text = page.read_text(encoding="utf-8")
    parser = CineDockParser()
    parser.feed(text)
    return text, parser


class CineDockSiteTests(unittest.TestCase):
    def test_product_routes_have_consistent_metadata_and_local_fragments(self):
        sitemap = ET.parse(ROOT / "sitemap.xml")
        locations = {
            entry.text
            for entry in sitemap.iter("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")
        }
        for route in ROUTES:
            with self.subTest(route=route):
                _, page = read_page(route)
                self.assertEqual(page.canonical, ORIGIN + route)
                self.assertEqual(page.metadata["og:url"], page.canonical)
                self.assertEqual(page.metadata["og:site_name"], "Quasar Labs")
                self.assertIn("CineDock", page.metadata["og:title"])
                self.assertEqual(page.headings, 1)
                self.assertEqual(len(page.ids), len(set(page.ids)))
                self.assertIn("main", page.ids)
                self.assertIn(ORIGIN + route, locations)
                for link in page.links:
                    if link.startswith("#"):
                        self.assertIn(link[1:], page.ids, link)

    def test_catalog_directory_support_and_product_navigation_include_cinedock(self):
        home, _ = read_page("/")
        catalog, catalog_page = read_page("/projects/")
        self.assertIn("<h3>CineDock</h3>", home)
        self.assertIn("cinedock", catalog_page.ids)
        self.assertIn("<h2>CineDock</h2>", catalog)
        for route in ("/", "/projects/", "/links/", "/about/", "/support/", "/privacy/"):
            with self.subTest(route=route):
                _, page = read_page(route)
                self.assertTrue(any(link.startswith("/cinedock/") for link in page.links))
        for file in ROOT.rglob("*.html"):
            text = file.read_text(encoding="utf-8")
            products = re.search(r"<div><h2>Products</h2>(.*?)</div>", text, re.DOTALL)
            if products:
                footer = CineDockParser()
                footer.feed(products.group(0))
                self.assertEqual(
                    footer.links,
                    [
                        "https://lircin.github.io",
                        "https://github.com/QuasarLI/TaskForge/releases/latest",
                        "/quasar/", "/cuspr/", "/pixelbridge/", "/cinedock/",
                    ],
                    str(file),
                )
                self.assertNotIn("Quasar preview", products.group(0))

    def test_development_pages_do_not_publish_downloads_or_private_assets(self):
        for route in ROUTES:
            with self.subTest(route=route):
                text, page = read_page(route)
                self.assertEqual(page.forbidden, [])
                self.assertEqual(
                    page.scripts,
                    ["/assets/theme-init.js", "/assets/site.js?v=20261029-1"],
                )
                self.assertIn("private development", " ".join(page.text).lower())
                for link in page.links:
                    parsed = urlparse(link)
                    self.assertNotEqual(parsed.scheme, "file")
                    self.assertNotIn("github.com/quasarli/cinedock", link.lower())
                    self.assertNotIn("/.github/", link.lower())
                    self.assertNotIn("/releases/download/", link)
                    self.assertNotIn(Path(parsed.path).suffix.lower(), (".zip", ".exe", ".msi"))
                for private_marker in ("C:\\Users\\", "D:\\", ".copilot", "client_secret"):
                    self.assertNotIn(private_marker, text)

    def test_status_licensing_and_optional_integrations_remain_qualified(self):
        _, page = read_page("/cinedock/")
        text = " ".join(page.text)
        for boundary in (
            "No public download. Release timing not announced.",
            "not a generally available or universally tested product",
            "external system browser",
            "keyboard and mouse",
            "separately installed and licensed SVPcode companion",
            "End-to-end attended runtime acceptance is incomplete",
            "embedded-login workaround",
            "CineDock-owned source is MIT-licensed.",
            "Copyright (c) 2026 Quasar Labs.",
            "Third-party components retain their own licenses",
            "not an MIT-only designation",
        ):
            self.assertIn(boundary, text)
        self.assertNotIn("licensing update in progress", text)
        self.assertNotIn("Source application of that choice is still pending", text)
        markup, _ = read_page("/cinedock/")
        hero = markup.split('<header class="cinedock-hero">', 1)[1].split("</header>", 1)[0]
        self.assertLess(hero.index("Private development"), hero.index('class="actions"'))
        self.assertLess(hero.index("No public download"), hero.index('class="actions"'))
        self.assertIn('href="/cinedock/support/#release-steps"', hero)

    def test_data_notes_do_not_masquerade_as_a_release_policy(self):
        _, page = read_page("/cinedock/privacy/")
        text = " ".join(page.text)
        for boundary in (
            "Not a finalized release privacy policy",
            "https://www.googleapis.com/auth/drive.readonly",
            "throughout your authorized Drive",
            "email address",
            "Playback downloads media bytes",
            "on-device loopback media bridge",
            "Windows DPAPI",
            "No global cache-retention limit has been verified",
            "not confirmation that Google has revoked access",
            "Do not assume disconnect clears history",
            "Completed downloads and converted outputs remain",
            "including its Limited Use requirements",
            "not yet a confirmed CineDock-specific privacy or deletion-request contact",
        ):
            self.assertIn(boundary, text)
        self.assertIn("https://myaccount.google.com/connections", page.links)
        self.assertIn("deletion", page.ids)
        self.assertIn("release-policy", page.ids)
        self.assertIn("/cinedock/support/#contact", page.links)
        self.assertIn("/cinedock/support/#release-steps", page.links)
        markup, _ = read_page("/cinedock/privacy/")
        self.assertNotIn("<ol>", markup.split('id="release-policy"', 1)[1])

    def test_parent_navigation_and_local_context_are_present_on_each_product_route(self):
        for route in ROUTES:
            with self.subTest(route=route):
                _, page = read_page(route)
                primary = next(
                    nav for nav in page.navigations if nav["label"] == "Primary navigation"
                )
                for destination in ("/projects/", "/about/", "/links/", "/support/"):
                    self.assertIn(destination, primary["links"])
                breadcrumb = next(
                    nav for nav in page.navigations if nav["label"] == "Breadcrumb"
                )
                self.assertIn("/", breadcrumb["links"])
                index = next(
                    nav for nav in page.navigations if nav["label"] == "On this page"
                )
                self.assertIn("section-index", index["classes"])
                if route == "/cinedock/privacy/":
                    self.assertTrue(
                        {"#google-data", "#storage", "#deletion", "#release-policy"}
                        <= set(index["links"])
                    )

    def test_development_status_and_notices_use_consistent_readable_roles(self):
        home, home_page = read_page("/")
        _, catalog = read_page("/projects/")
        _, product = read_page("/cinedock/")
        for page in (home_page, catalog, product):
            self.assertTrue(any(
                {"status", "development"} <= set(attrs.get("class", "").split())
                for _, attrs in page.elements
            ))
        self.assertIn('class="ledger-label development">Private development', home)
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        self.assertIn(
            ".status.development,.ledger-label.development,.signal-bar .development{color:var(--text)}",
            css,
        )
        self.assertIn(".cinedock-page .notice,#cinedock .notice{color:var(--text)}", css)

    def test_shared_navigation_only_collapses_after_handlers_are_ready(self):
        css = (ROOT / "assets" / "styles.css").read_text(encoding="utf-8")
        script = (ROOT / "assets" / "site.js").read_text(encoding="utf-8")
        for selector, declarations in re.findall(r"([^{}]+)\{([^{}]*)\}", css):
            if selector.strip() == ".nav-links":
                self.assertNotIn("display:none", declarations)
        self.assertIn(".nav-ready .nav-links{display:none", css)
        self.assertIn(".nav-ready .nav-links.open{display:flex}", css)
        self.assertLess(
            script.index('menuButton.addEventListener("click"'),
            script.index('document.documentElement.classList.add("nav-ready")'),
        )
        self.assertIn('event.key === "Escape"', script)
        self.assertIn("menuButton.focus()", script)

    def test_shared_asset_revisions_and_catalog_share_metadata_are_consistent(self):
        styles = set()
        scripts = set()
        for file in ROOT.rglob("*.html"):
            page = CineDockParser()
            page.feed(file.read_text(encoding="utf-8"))
            styles.update(link for link in page.links if urlparse(link).path == "/assets/styles.css")
            scripts.update(link for link in page.scripts if urlparse(link).path == "/assets/site.js")
        self.assertEqual(styles, {"/assets/styles.css?v=20261029-2"})
        self.assertEqual(scripts, {"/assets/site.js?v=20261029-1"})
        _, catalog = read_page("/projects/")
        for name in ("L'IRC'in", "TaskForge", "Quasar", "Cuspr", "PixelBridge", "CineDock"):
            self.assertIn(name, catalog.metadata["og:description"])
        self.assertIn("private-development", catalog.metadata["og:description"])
        self.assertEqual(catalog.metadata["og:site_name"], "Quasar Labs")
        self.assertEqual(catalog.metadata["twitter:card"], "summary_large_image")

    def test_support_uses_only_existing_general_contact_without_new_commitments(self):
        _, page = read_page("/cinedock/support/")
        text = " ".join(page.text)
        email_links = [link for link in page.links if link.startswith("mailto:")]
        self.assertEqual(
            email_links,
            ["mailto:quasarlabs-inc@outlook.com?subject=CineDock%20inquiry"],
        )
        self.assertIn("has not yet been confirmed", text)
        self.assertIn("no response-time or deletion-service commitment", text)
        self.assertIn("release-steps", page.ids)
        self.assertIn("contact", page.ids)

    def test_original_brand_asset_is_self_contained_and_ci_runs_checks(self):
        icon = ET.parse(ROOT / "assets" / "icon-cinedock.svg").getroot()
        self.assertEqual(icon.attrib["viewBox"], "0 0 256 256")
        for element in icon.iter():
            self.assertNotIn(element.tag.split("}")[-1], ("image", "script", "foreignObject"))
            self.assertFalse(any("href" in key for key in element.attrib))
        workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
        self.assertIn("python -m unittest scripts.test_cinedock_site", workflow)
        self.assertIn("github.event_name != 'pull_request'", workflow)


if __name__ == "__main__":
    unittest.main()
