from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import struct
import unittest
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
PRODUCT = ROOT / "pixelbridge"
RELEASE_RECORD = ROOT / ".github" / "pixelbridge" / "release.json"
CHECKOUT_URLS = {
    "supporter": "https://quasarlabs3.gumroad.com/l/kdxoac",
    "pro": "https://quasarlabs3.gumroad.com/l/mqkmz",
}
PROFILE_DOC_URLS = {
    f"https://docs.libretro.com/library/{core}/"
    for core in ("nestopia", "snes9x", "genesis_plus_gx", "flycast", "mupen64plus")
}
RELEASE_BASE = "https://github.com/QuasarLI/PixelBridge-Distribution"
ASSET_BASE = f"{RELEASE_BASE}/releases/download/v1.2.0/"
DISTRIBUTION_COMMIT = "54450c3fcec56423c0521c9506d312fad8fbbfca"
SIGNING_IDENTITY = f"{RELEASE_BASE}/.github/workflows/release.yml@refs/heads/main"
OIDC_ISSUER = "https://token.actions.githubusercontent.com"
ZIP_FACTS = {
    "free": (155006, "8e9fcb082f0e386c8f6881be8b73c64fd90dd7e14b4fdc2b77a4c4e5c77cc5d6"),
    "free-with-ads": (179911, "0da81bd7e06fcbffd627ccf20926564563d14c0a048e94e046f103836e9252e6"),
    "supporter": (155006, "0fd01960f7fcedc58859c87fadc1d02e58378f224e76d56721e7b015762525ea"),
    "pro": (155005, "0b103dd3fd6daa149a95c8d3d6a862b84b4e3f72467d32c8fd3f290b9bf02f54"),
}


class ProductParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.ids = set()
        self.editions = set()
        self.robots = None
        self.forbidden_elements = []
        self.downloads = {}
        self.current_download = None
        self.code_blocks = []
        self.in_pre = False

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(values["id"])
        if values.get("data-edition"):
            self.editions.add(values["data-edition"])
        if tag == "article" and values.get("data-download-edition"):
            self.current_download = {"links": [], "text": []}
            self.downloads[values["data-download-edition"]] = self.current_download
        if tag == "pre":
            self.in_pre = True
            self.code_blocks.append("")
        if tag == "meta" and values.get("name") == "robots":
            self.robots = values.get("content")
        if tag in ("iframe", "video", "audio", "form") or "download" in values:
            self.forbidden_elements.append(tag)
        for attribute in ("href", "src"):
            if attribute in values:
                self.links.append(values[attribute])
                if self.current_download is not None:
                    self.current_download["links"].append(values[attribute])

    def handle_data(self, data):
        if self.current_download is not None:
            self.current_download["text"].append(data)
        if self.in_pre:
            self.code_blocks[-1] += data

    def handle_endtag(self, tag):
        if tag == "article":
            self.current_download = None
        if tag == "pre":
            self.in_pre = False


class PixelBridgeSiteTests(unittest.TestCase):
    def test_publication_is_authorized_and_release_facts_are_verified(self):
        contract = json.loads(RELEASE_RECORD.read_text(encoding="utf-8"))
        self.assertEqual(contract["state"], "release-ready")
        self.assertIs(contract["publicationReady"], True)
        self.assertIs(contract["userAuthorizedPublicationAfterSignedRelease"], True)
        self.assertIs(contract["awaitingCoordinatorSignedReleaseHandoff"], False)
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
        self.assertEqual(facts["channel"], "stable")
        self.assertEqual(facts["tag"], "v1.2.0")
        self.assertEqual(facts["releaseId"], 424286114)
        self.assertEqual(facts["releaseAssetCount"], 18)
        self.assertEqual(facts["releaseUrl"], f"{RELEASE_BASE}/releases/tag/v1.2.0")
        self.assertEqual(facts["releaseNotesUrl"], facts["releaseUrl"])
        self.assertEqual(facts["sigstoreCertificateIdentity"], SIGNING_IDENTITY)
        self.assertEqual(facts["sigstoreOidcIssuer"], OIDC_ISSUER)
        self.assertEqual(
            facts["signingWorkflowUrl"],
            f"{RELEASE_BASE}/blob/{DISTRIBUTION_COMMIT}/.github/workflows/release.yml",
        )
        self.assertEqual(facts["signingRunConclusion"], "success")
        self.assertEqual(
            facts["signingRunUrl"],
            f"{RELEASE_BASE}/actions/runs/40334369634/attempts/1",
        )
        self.assertEqual(
            facts["verificationInstructions"]["url"],
            f"{RELEASE_BASE}/blob/4c2937b867a1f6b5fbf04d2875e51d1b44f3ad6e/docs/VERIFYING.md",
        )
        self.assertEqual(
            facts["metadataMatchEvidence"]["status"], "metadata-matched-only"
        )
        evidence = facts["artifactVerificationEvidence"]
        self.assertEqual(evidence["status"], "passed")
        self.assertEqual(evidence["downloadedAssetCount"], 18)
        self.assertEqual(evidence["verifiedSigstoreSignatureCount"], 11)
        self.assertEqual(evidence["verifiedContainedExeCount"], 4)
        self.assertIn(DISTRIBUTION_COMMIT, evidence["certificateEvidence"])
        self.assertIs(
            facts["productionBuildExcludesTestUnlocks"]["finalReleaseRecheckRequired"],
            False,
        )
        for field, name in (
            ("checksumManifestUrl", "SHA256SUMS"),
            ("releaseManifestUrl", "release-manifest.json"),
            ("provenanceUrl", "provenance.json"),
        ):
            self.assertEqual(facts[field], ASSET_BASE + name)
            bundle_field = field.removesuffix("Url") + "BundleUrl"
            self.assertEqual(facts[bundle_field], ASSET_BASE + name + ".sigstore.json")
        self.assertEqual(
            {edition["id"] for edition in facts["editions"]},
            {"free", "free-with-ads", "supporter", "pro"},
        )
        self.assertEqual(
            [edition["artifactName"] for edition in facts["editions"]],
            contract["confirmedReleasePlan"]["expectedArtifactNames"],
        )
        for edition in facts["editions"]:
            size, digest = ZIP_FACTS[edition["id"]]
            self.assertEqual(edition["sizeBytes"], size)
            self.assertEqual(edition["sha256"], digest)
            self.assertEqual(edition["artifactUrl"], ASSET_BASE + edition["artifactName"])
            self.assertEqual(
                edition["sigstoreBundleUrl"], edition["artifactUrl"] + ".sigstore.json"
            )
            self.assertEqual(
                edition["exeSigstoreBundleUrl"],
                edition["artifactUrl"].removesuffix(".zip")
                + "-PixelBridge.exe.sigstore.json",
            )
            self.assertTrue(edition["availability"].startswith("public-production-release"))
            if edition["id"] in CHECKOUT_URLS:
                self.assertEqual(
                    edition["approvedCheckoutUrl"], CHECKOUT_URLS[edition["id"]]
                )
                self.assertIsNone(edition["approvedPriceAndCurrency"])
                self.assertIn("Public production GitHub release ZIP", edition["deliveryMethod"])
                self.assertEqual(edition["priceDisplay"], "See current price on Gumroad")
                self.assertIs(edition["oneTimePurchase"], True)

    def test_public_routes_and_navigation_are_wired_without_draft_links(self):
        workflow = (ROOT / ".github" / "workflows" / "pages.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("actions/upload-pages-artifact@v3", workflow)
        self.assertIn("pull_request:", workflow)
        self.assertIn("python -m unittest scripts.test_pixelbridge_site", workflow)
        self.assertIn("github.event_name != 'pull_request'", workflow)
        self.assertTrue((PRODUCT / "index.html").is_file())
        for relative in ("index.html", "projects", "links", "about", "support"):
            page = ROOT / relative
            if page.is_dir():
                page /= "index.html"
            parser = ProductParser()
            parser.feed(page.read_text(encoding="utf-8"))
            self.assertIn("/pixelbridge/", parser.links, str(page))
        for page in ROOT.rglob("*.html"):
            if ".git" in page.parts or ".github" in page.relative_to(ROOT).parts:
                continue
            text = page.read_text(encoding="utf-8").lower()
            self.assertNotIn("/.github/drafts/", text, str(page))
            if "<h2>products</h2>" in text:
                self.assertIn('href="/pixelbridge/"', text, str(page))
        self.assertIn(
            "https://quasarli.github.io/pixelbridge/",
            (ROOT / "sitemap.xml").read_text(encoding="utf-8"),
        )
        text = (PRODUCT / "index.html").read_text(encoding="utf-8")
        self.assertIn('rel="canonical" href="https://quasarli.github.io/pixelbridge/"', text)
        self.assertIn("https://quasarli.github.io/assets/banner-pixelbridge.png", text)
        self.assertNotIn("noindex", text)
        self.assertNotIn("Unpublished", text)

    def test_product_links_use_only_approved_routes_without_placeholders(self):
        contract = json.loads(RELEASE_RECORD.read_text(encoding="utf-8"))
        facts = contract["releaseFacts"]
        release_links = {
            facts[field] for field in (
                "releaseUrl", "releaseNotesUrl", "checksumManifestUrl",
                "checksumManifestBundleUrl", "releaseManifestUrl",
                "releaseManifestBundleUrl", "provenanceUrl", "provenanceBundleUrl",
                "signingWorkflowUrl", "signingRunUrl"
            )
        }
        release_links.add(facts["verificationInstructions"]["url"])
        for edition in facts["editions"]:
            release_links.update(
                edition[field] for field in (
                    "artifactUrl", "sigstoreBundleUrl", "exeSigstoreBundleUrl"
                )
            )
        for page in PRODUCT.glob("*.html"):
            parser = ProductParser()
            parser.feed(page.read_text(encoding="utf-8"))
            self.assertIsNone(parser.robots, page.name)
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
                                "https://quasarli.github.io/pixelbridge/",
                                "https://github.com/QuasarLI/PixelBridge-Distribution",
                                *CHECKOUT_URLS.values(),
                                *PROFILE_DOC_URLS,
                                *release_links,
                                "https://docs.sigstore.dev/cosign/system_config/installation/",
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
                        target_parser = ProductParser()
                        target_parser.feed(target.read_text(encoding="utf-8"))
                        self.assertIn(parsed.fragment, target_parser.ids)

    def test_product_presents_all_editions_and_verification_boundaries(self):
        text = (PRODUCT / "index.html").read_text(encoding="utf-8")
        parser = ProductParser()
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
            "independent post-publication checks verified all 18 final assets",
            "11 independently verified GitHub OIDC-backed Sigstore bundles",
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
        for page in PRODUCT.glob("*.html"):
            parser = ProductParser()
            parser.feed(page.read_text(encoding="utf-8"))
            self.assertNotIn("https://github.com/QuasarLI/PixelBridge", parser.links)

    def test_download_cards_match_exact_public_release_facts(self):
        contract = json.loads(RELEASE_RECORD.read_text(encoding="utf-8"))
        parser = ProductParser()
        parser.feed((PRODUCT / "index.html").read_text(encoding="utf-8"))
        self.assertEqual(set(parser.downloads), set(ZIP_FACTS))
        for edition in contract["releaseFacts"]["editions"]:
            card = parser.downloads[edition["id"]]
            text = " ".join(card["text"])
            self.assertEqual(
                set(card["links"]),
                {
                    edition["artifactUrl"], edition["sigstoreBundleUrl"],
                    edition["exeSigstoreBundleUrl"],
                },
            )
            self.assertIn(edition["artifactName"], text)
            self.assertIn(f"{edition['sizeBytes']:,} bytes", text)
            self.assertIn(edition["sha256"], text)
        asset_links = {link for link in parser.links if link.startswith(ASSET_BASE)}
        self.assertEqual(len(asset_links), 18)
        self.assertTrue(all("LOCAL-TEST" not in link for link in parser.links))

    def test_verification_instructions_pin_identity_and_fail_on_errors(self):
        parser = ProductParser()
        text = (PRODUCT / "index.html").read_text(encoding="utf-8")
        parser.feed(text)
        self.assertEqual(len(parser.code_blocks), 2)
        commands = "\n".join(parser.code_blocks)
        for value in (
            SIGNING_IDENTITY, OIDC_ISSUER, "$ErrorActionPreference = 'Stop'",
            "--certificate-identity $identity", "--certificate-oidc-issuer $issuer",
            "release-manifest.json", "provenance.json", "SHA256SUMS",
            "$LASTEXITCODE -ne 0", "$file.Length -ne $entry[0].size_bytes",
            "$hash -cne $entry[0].sha256",
            "PixelBridge-v1.2.0-Free-win-x64-PixelBridge.exe.sigstore.json",
        ):
            self.assertIn(value, commands)
        self.assertNotIn("--insecure", commands)
        self.assertNotIn("--ignore", commands)
        self.assertNotIn("No signed release exists", text)

    def test_checkout_and_profile_links_are_present_without_hardcoded_prices(self):
        text = (PRODUCT / "index.html").read_text(encoding="utf-8")
        parser = ProductParser()
        parser.feed(text)
        self.assertTrue(set(CHECKOUT_URLS.values()) <= set(parser.links))
        self.assertTrue(PROFILE_DOC_URLS <= set(parser.links))
        self.assertNotRegex(text, r"[$\u00a3\u20ac]\s*\d")
        contract = json.loads(RELEASE_RECORD.read_text(encoding="utf-8"))
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
        contract = json.loads(RELEASE_RECORD.read_text(encoding="utf-8"))
        assets = contract["releaseFacts"]["approvedBrandingAssets"]
        self.assertEqual(len(assets), 2)
        for asset in assets:
            with self.subTest(asset=asset["path"]):
                path = ROOT / asset["path"]
                self.assertTrue(path.is_relative_to(ROOT / "assets"))
                content = path.read_bytes()
                self.assertEqual(content[:8], b"\x89PNG\r\n\x1a\n")
                self.assertEqual(len(content), asset["sizeBytes"])
                self.assertEqual(hashlib.sha256(content).hexdigest(), asset["sha256"])
                self.assertEqual(
                    list(struct.unpack(">II", content[16:24])), asset["dimensions"]
                )


if __name__ == "__main__":
    unittest.main()
