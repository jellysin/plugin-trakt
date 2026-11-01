"""Tests for tools/api_matrix.py on a small fixture document; the pinned live document is not fetched here."""

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
import api_matrix  # noqa: E402

SPEC = {
    "info": {"version": "2.0.0"},
    "paths": {
        "/users/settings": {"get": {"tags": ["users"], "summary": "Retrieve settings",
                                    "description": "#### 🔒 OAuth Required\nSee the `limits` object; Trakt VIP raises them."}},
        "/sync/history": {"post": {"tags": ["sync"], "summary": "Add items to watched history",
                                   "description": "#### 🔒 OAuth Required\n\n#### JSON POST Data\n"}},
        "/lists/{id}/items/{type}": {"get": {"tags": ["lists"], "summary": "Get items | sorted",
                                             "description": "#### 🔥 VIP Only 🔒 OAuth Required 📄 Pagination Optional ✨ Extended Info\n"}},
        "/movies/trending": {"get": {"tags": ["movies"], "summary": "Trending movies",
                                     "description": "#### 📄 Pagination ✨ Extended Info 🎚 Filters\n"},
                             "parameters": [{"name": "page"}]},
        "/users/{id}/lists": {"post": {"tags": ["users"], "summary": "Create list",
                                       "description": "#### 🔥 VIP Enhanced 🔒 OAuth Required\n"}},
    },
}
SOURCE = {"url": "https://example.invalid/openapi.json", "sha256": "0" * 64, "checked": "2026-11-01"}


class MarkerTests(unittest.TestCase):
    def test_vip_only_with_optional_pagination(self):
        found = api_matrix.markers(SPEC["paths"]["/lists/{id}/items/{type}"]["get"]["description"])
        self.assertEqual((found["vip"], found["auth"], found["pagination"], found["extended"]),
                         ("only", "required", "optional", "yes"))

    def test_vip_enhanced(self):
        self.assertEqual(api_matrix.markers("#### 🔥 VIP Enhanced 🔒 OAuth Required")["vip"], "enhanced")

    def test_vip_mentioned_in_prose_is_not_a_marker(self):
        found = api_matrix.markers(SPEC["paths"]["/users/settings"]["get"]["description"])
        self.assertEqual((found["vip"], found["auth"]), ("no", "required"))

    def test_description_without_marker_heading(self):
        self.assertEqual(api_matrix.markers("")["auth"], "none")
        self.assertEqual(api_matrix.markers("#### JSON POST Data")["auth"], "none")


class RenderTests(unittest.TestCase):
    def test_every_operation_has_one_row_and_non_operation_keys_are_skipped(self):
        rows = api_matrix.operations(SPEC)
        self.assertEqual(len(rows), 5)
        self.assertEqual([row["section"] for row in rows], ["lists", "movies", "sync", "users", "users"])

    def test_render_counts_sections_and_escapes_pipes(self):
        text = api_matrix.render(SPEC, SOURCE, {"POST /sync/history": "implemented"})
        self.assertIn("5 operations in 4 sections; 1 implemented.", text)
        self.assertIn("Get items \\| sorted", text)
        self.assertIn("| POST | `/sync/history` | Add items to watched history | required | no | no | no | implemented |", text)
        self.assertIn("| GET | `/movies/trending` | Trending movies | none | no | yes | yes | planned |", text)

    def test_unknown_operation_in_status_is_refused(self):
        with self.assertRaisesRegex(ValueError, "GET /sync/gone: not an operation"):
            api_matrix.render(SPEC, SOURCE, {"GET /sync/gone": "implemented"})

    def test_unknown_status_value_is_refused(self):
        with self.assertRaisesRegex(ValueError, "status 'done'"):
            api_matrix.render(SPEC, SOURCE, {"POST /sync/history": "done"})


class FetchTests(unittest.TestCase):
    def test_non_https_schemes_are_refused_before_connecting(self):
        with mock.patch("http.client.HTTPSConnection") as connection:
            for url in ("file:///etc/passwd", "http://developer.trakt.tv/openapi.json", "ftp://x/y", "https:///no-host"):
                with self.subTest(url=url), self.assertRaisesRegex(ValueError, "only https"):
                    api_matrix.fetch(dict(SOURCE, url=url))
            connection.assert_not_called()

    def test_non_200_answer_is_refused(self):
        with mock.patch("http.client.HTTPSConnection") as connection:
            connection.return_value.getresponse.return_value.status = 301
            with self.assertRaisesRegex(ValueError, "HTTP 301"):
                api_matrix.fetch(SOURCE)
            connection.return_value.close.assert_called_once()

    def test_oversized_document_is_refused(self):
        with mock.patch("http.client.HTTPSConnection") as connection:
            response = connection.return_value.getresponse.return_value
            response.status = 200
            response.read.return_value = b"x" * (api_matrix.MAX_SPEC_BYTES + 1)
            with self.assertRaisesRegex(ValueError, "larger than"):
                api_matrix.fetch(SOURCE)


class MainTests(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.spec = self.dir / "openapi.json"
        self.spec.write_bytes(json.dumps(SPEC).encode())
        source = dict(SOURCE, sha256=hashlib.sha256(self.spec.read_bytes()).hexdigest())
        (self.dir / "source.json").write_text(json.dumps(source), encoding="utf-8")
        self.patches = [mock.patch.object(api_matrix, "SOURCE", self.dir / "source.json"),
                        mock.patch.object(api_matrix, "STATUS", self.dir / "status.json"),
                        mock.patch.object(api_matrix, "MATRIX", self.dir / "matrix.md")]
        for patch in self.patches:
            patch.start()

    def tearDown(self):
        for patch in self.patches:
            patch.stop()

    def run_main(self, *args):
        with mock.patch("sys.stderr"):
            return api_matrix.main(["--spec", str(self.spec), *args])

    def test_write_then_check_passes(self):
        self.assertEqual(self.run_main(), 0)
        self.assertEqual(self.run_main("--check"), 0)

    def test_check_fails_on_stale_matrix(self):
        self.assertEqual(self.run_main(), 0)
        (self.dir / "matrix.md").write_text("hand edit\n", encoding="utf-8")
        self.assertEqual(self.run_main("--check"), 1)

    def test_check_fails_when_matrix_is_missing(self):
        self.assertEqual(self.run_main("--check"), 1)

    def test_changed_document_is_refused(self):
        self.spec.write_bytes(self.spec.read_bytes() + b" ")
        self.assertEqual(self.run_main(), 1)
        self.assertFalse((self.dir / "matrix.md").exists())

    def test_plain_http_source_is_refused(self):
        source = json.loads((self.dir / "source.json").read_text(encoding="utf-8"))
        (self.dir / "source.json").write_text(json.dumps(dict(source, url="http://example.invalid/x")), encoding="utf-8")
        self.assertEqual(self.run_main(), 2)


if __name__ == "__main__":
    unittest.main()
