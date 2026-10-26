from html.parser import HTMLParser
import json
from pathlib import Path
import unittest
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / ".github" / "drafts" / "pixelbridge"


class DraftParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()
        self.editions = set()
        self.robots = None
        self.forbidden_elements = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        if values.get("data-edition"):
            self.editions.add(values["data-edition"])
        if tag == "meta" and values.get("name") == "robots":
            self.robots = values.get("content")
        if tag in ("iframe", "video", "audio", "form") or "download" in values:
            self.forbidden_elements.append(tag)
        for attribute in ("href", "src"):
            if attribute in values:
                self.links.append(values[attribute])


class PixelBridgeDraftTests(unittest.TestCase):
    def test_publication_is_held_and_release_facts_are_not_invented(self):
        contract = json.loads((DRAFT / "publication.json").read_text(encoding="utf-8"))
        self.assertEqual(contract["state"], "draft")
        self.assertIs(contract["publicationAuthorized"], False)
        self.assertEqual(contract["sourceVisibility"], "private")
        self.assertEqual(contract["intendedRoute"], "/pixelbridge/")
        self.assertEqual(
            contract["publicDistributionRepository"],
            "https://github.com/QuasarLI/PixelBridge-Distribution",
        )
        self.assertEqual(contract["confirmedReleasePlan"]["version"], "1.2.0")
        self.assertEqual(
            contract["confirmedReleasePlan"]["expectedArtifactNames"],
            [
                f"PixelBridge-v1.2.0-{edition}-win-x64.zip"
                for edition in ("Free", "FreewithAds", "Supporter", "Pro")
            ],
        )
        facts = contract["releaseFacts"]
        for field, value in facts.items():
            if field != "editions":
                self.assertIsNone(value, field)
        self.assertEqual(
            {edition["id"] for edition in facts["editions"]},
            {"free", "free-with-ads", "supporter", "pro"},
        )
        for edition in facts["editions"]:
            for field, value in edition.items():
                if field not in ("id", "displayName"):
                    self.assertIsNone(value, f"{edition['id']}.{field}")

    def test_drafts_remain_inside_the_pages_excluded_directory(self):
        self.assertTrue(DRAFT.is_relative_to(ROOT / ".github"))
        workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("actions/upload-pages-artifact@v3", workflow)
        self.assertFalse((ROOT / "pixelbridge").exists())
        for page in ROOT.rglob("*.html"):
            if ".git" in page.parts or ".github" in page.relative_to(ROOT).parts:
                continue
            text = page.read_text(encoding="utf-8").lower()
            self.assertNotIn("pixelbridge", text, str(page))
        self.assertNotIn(
            "pixelbridge", (ROOT / "sitemap.xml").read_text(encoding="utf-8").lower()
        )

    def test_draft_links_are_real_and_have_no_release_or_commerce_placeholders(self):
        for page in DRAFT.glob("*.html"):
            parser = DraftParser()
            parser.feed(page.read_text(encoding="utf-8"))
            self.assertEqual(parser.robots, "noindex, nofollow", page.name)
            self.assertEqual(parser.forbidden_elements, [], page.name)
            for link in parser.links:
                with self.subTest(page=page.name, link=link):
                    self.assertTrue(link)
                    parsed = urlparse(link)
                    if parsed.scheme:
                        self.assertEqual(parsed.scheme, "https")
                        self.assertIn(
                            link,
                            {
                                "https://github.com/QuasarLI",
                                "https://github.com/QuasarLI/PixelBridge-Distribution",
                            },
                        )
                        continue
                    self.assertFalse(parsed.netloc)
                    self.assertTrue(not parsed.path or parsed.path.startswith("/"))
                    target = ROOT / parsed.path.lstrip("/") if parsed.path else page
                    if target.is_dir():
                        target /= "index.html"
                    self.assertTrue(target.is_file(), str(target))
                    if parsed.fragment:
                        target_parser = DraftParser()
                        target_parser.feed(target.read_text(encoding="utf-8"))
                        self.assertIn(parsed.fragment, target_parser.ids)

    def test_product_presents_all_editions_and_verification_boundaries(self):
        text = (DRAFT / "index.html").read_text(encoding="utf-8")
        parser = DraftParser()
        parser.feed(text)
        self.assertEqual(
            parser.editions, {"free", "free-with-ads", "supporter", "pro"}
        )
        self.assertTrue(
            {"features", "streaming", "editions", "downloads", "integrity"}
            <= parser.ids
        )
        for phrase in (
            "all usable Xbox controller mappings and standard importable profiles",
            "GitHub OIDC-backed Sigstore bundles",
            "No Authenticode claim",
            "No production download is listed yet.",
            "No games, ROMs, BIOS files, or keys are bundled.",
            "direct-HDMI TV output/setup",
            "No router WAN port forwarding or UPnP is required",
            "still have their provider and internet latency",
        ):
            self.assertIn(phrase.casefold(), text.casefold())
        for page in DRAFT.glob("*.html"):
            parser = DraftParser()
            parser.feed(page.read_text(encoding="utf-8"))
            self.assertNotIn("https://github.com/QuasarLI/PixelBridge", parser.links)


if __name__ == "__main__":
    unittest.main()
