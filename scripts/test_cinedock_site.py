from html.parser import HTMLParser
from pathlib import Path
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

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
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
            if "<h2>Products</h2>" in text:
                self.assertIn('href="/cinedock/"', text, str(file))

    def test_development_pages_do_not_publish_downloads_or_private_assets(self):
        for route in ROUTES:
            with self.subTest(route=route):
                text, page = read_page(route)
                self.assertEqual(page.forbidden, [])
                self.assertEqual(
                    page.scripts,
                    ["/assets/theme-init.js", "/assets/site.js?v=20261024-3"],
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
            "No public installer, download, or release date",
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
