from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import struct
import unittest
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
DRAFT = ROOT / ".github" / "drafts" / "pixelbridge"
CHECKOUT_URLS = {
    "supporter": "https://quasarlabs3.gumroad.com/l/kdxoac",
    "pro": "https://quasarlabs3.gumroad.com/l/mqkmz",
}
PROFILE_DOC_URLS = {
    f"https://docs.libretro.com/library/{core}/"
    for core in ("nestopia", "snes9x", "genesis_plus_gx", "flycast", "mupen64plus")
}


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
        self.assertIs(contract["publicationReady"], False)
        self.assertIs(contract["userAuthorizedPublicationAfterSignedRelease"], True)
        self.assertIs(contract["awaitingCoordinatorSignedReleaseHandoff"], True)
        self.assertEqual(contract["sourceVisibility"], "private")
        self.assertEqual(contract["intendedRoute"], "/pixelbridge/")
        self.assertEqual(
            contract["publicDistributionRepository"],
            "https://github.com/QuasarLI/PixelBridge-Distribution",
        )
        self.assertEqual(contract["confirmedReleasePlan"]["version"], "1.2.0")
        self.assertEqual(
            contract["documentaryBasis"]["privateSourceCommit"],
            "6322a75cb58544401b8ae6a864ddf98cd558c45a",
        )
        self.assertEqual(
            contract["contentReview"]["releaseManifestSha256"],
            "7d480908eafca07ae04fa5ec6e802923200f1253884307ec28e21a086507c424",
        )
        self.assertEqual(
            contract["confirmedReleasePlan"]["expectedArtifactNames"],
            [
                f"PixelBridge-v1.2.0-{edition}-win-x64.zip"
                for edition in ("Free", "FreewithAds", "Supporter", "Pro")
            ],
        )
        facts = contract["releaseFacts"]
        self.assertEqual(facts["version"], "1.2.0")
        self.assertEqual(facts["supportedWindowsVersions"], ["Windows 11"])
        self.assertEqual(facts["architectures"], ["x64"])
        self.assertEqual(
            facts["runtimeAndInstallPrerequisites"]["runtime"], ".NET Framework 4.8"
        )
        for field in (
            "channel", "tag", "releaseUrl", "releaseNotesUrl", "checksumManifestUrl",
            "checksumManifestBundleUrl", "sigstoreOidcIssuer",
            "sigstoreCertificateIdentity", "signingWorkflowUrl",
            "verificationInstructions", "artifactVerificationEvidence",
        ):
            self.assertIsNone(facts[field], field)
        self.assertEqual(
            {edition["id"] for edition in facts["editions"]},
            {"free", "free-with-ads", "supporter", "pro"},
        )
        self.assertEqual(
            [edition["artifactName"] for edition in facts["editions"]],
            contract["confirmedReleasePlan"]["expectedArtifactNames"],
        )
        for edition in facts["editions"]:
            for field in (
                "availability", "artifactUrl", "sizeBytes", "sha256", "sigstoreBundleUrl"
            ):
                self.assertIsNone(edition[field], f"{edition['id']}.{field}")
            if edition["id"] in CHECKOUT_URLS:
                self.assertEqual(
                    edition["approvedCheckoutUrl"], CHECKOUT_URLS[edition["id"]]
                )
                self.assertIsNone(edition["approvedPriceAndCurrency"])
                self.assertIsNone(edition["deliveryMethod"])
                self.assertEqual(edition["priceDisplay"], "See current price on Gumroad")
                self.assertIs(edition["oneTimePurchase"], True)

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

    def test_draft_links_use_only_approved_routes_without_release_placeholders(self):
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
                                *CHECKOUT_URLS.values(),
                                *PROFILE_DOC_URLS,
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
            {"features", "streaming", "controllers", "editions", "downloads", "integrity"}
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
            "Standard profiles and import/export stay free.",
            "Windows 11 x64 and .NET Framework 4.8",
            "A previously verified one-time purchase remains usable indefinitely offline",
            "Live customer-key activation is an untested acceptance gap",
            "Earlier Xbox streaming success with the predecessor app does not establish",
            "actual new emulator/controller gameplay, HDMI display/audio, and clean-PC Sunshine/Moonlight pairing have not been verified",
            "not proof of receiver pairing, encoding, game compatibility, or TV audio",
            "Pro edits port-1 digital remap destinations",
            "analog axes remain unchanged",
        ):
            self.assertIn(phrase.casefold(), text.casefold())
        for page in DRAFT.glob("*.html"):
            parser = DraftParser()
            parser.feed(page.read_text(encoding="utf-8"))
            self.assertNotIn("https://github.com/QuasarLI/PixelBridge", parser.links)

    def test_checkout_and_profile_links_are_present_without_hardcoded_prices(self):
        text = (DRAFT / "index.html").read_text(encoding="utf-8")
        parser = DraftParser()
        parser.feed(text)
        self.assertTrue(set(CHECKOUT_URLS.values()) <= set(parser.links))
        self.assertTrue(PROFILE_DOC_URLS <= set(parser.links))
        self.assertNotRegex(text, r"[$\u00a3\u20ac]\s*\d")
        contract = json.loads((DRAFT / "publication.json").read_text(encoding="utf-8"))
        facts = contract["releaseFacts"]
        targets = facts["documentedNativeProfileTargets"]
        self.assertEqual(len(targets["profiles"]), 5)
        self.assertEqual(
            {profile["documentationUrl"] for profile in targets["profiles"]},
            PROFILE_DOC_URLS,
        )
        self.assertEqual(
            len(facts["productionCompatibilityEvidence"]["untestedAcceptanceGaps"]), 4
        )

    def test_approved_branding_bytes_and_dimensions_are_preserved(self):
        contract = json.loads((DRAFT / "publication.json").read_text(encoding="utf-8"))
        assets = contract["releaseFacts"]["approvedBrandingAssets"]
        self.assertEqual(len(assets), 2)
        for asset in assets:
            with self.subTest(asset=asset["path"]):
                path = ROOT / asset["path"]
                self.assertTrue(path.is_relative_to(DRAFT))
                content = path.read_bytes()
                self.assertEqual(content[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(len(content), asset["sizeBytes"])
                self.assertEqual(hashlib.sha256(content).hexdigest(), asset["sha256"])
                self.assertEqual(
                    list(struct.unpack(">II", content[16:24])), asset["dimensions"]
                )


if __name__ == "__main__":
    unittest.main()
