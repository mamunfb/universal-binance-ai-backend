from __future__ import annotations

import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"


class DashboardMarkupAudit(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.ids: list[str] = []
        self.controls: list[tuple[str, dict[str, str], bool]] = []
        self.buttons: list[tuple[dict[str, str], str]] = []
        self.labels_for: set[str] = set()
        self._label_depth = 0
        self._button_stack: list[tuple[dict[str, str], list[str]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if values.get("id"):
            self.ids.append(values["id"])
        if tag == "label":
            self._label_depth += 1
            if values.get("for"):
                self.labels_for.add(values["for"])
        if tag in {"input", "select", "textarea"}:
            self.controls.append((tag, values, self._label_depth > 0))
        if tag == "button":
            self._button_stack.append((values, []))

    def handle_endtag(self, tag: str) -> None:
        if tag == "label" and self._label_depth:
            self._label_depth -= 1
        if tag == "button" and self._button_stack:
            attrs, text_parts = self._button_stack.pop()
            self.buttons.append((attrs, " ".join(" ".join(text_parts).split())))

    def handle_data(self, data: str) -> None:
        if self._button_stack:
            self._button_stack[-1][1].append(data)


class DashboardAccessibilityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = (DASHBOARD / "index.html").read_text(encoding="utf-8")
        cls.css = (DASHBOARD / "app.css").read_text(encoding="utf-8")
        cls.js = (DASHBOARD / "app.js").read_text(encoding="utf-8")
        cls.parser = DashboardMarkupAudit()
        cls.parser.feed(cls.html)
        cls.parser.close()

    def test_document_has_unique_ids_and_primary_landmarks(self) -> None:
        duplicates = [item for item, count in Counter(self.parser.ids).items() if count > 1]
        self.assertEqual(duplicates, [])
        self.assertEqual(self.html.count("<main "), 1)
        self.assertIn('<nav id="main-nav"', self.html)
        self.assertIn('<header class="topbar">', self.html)

    def test_every_static_form_control_has_an_accessible_label(self) -> None:
        unlabeled = []
        for tag, attrs, nested_in_label in self.parser.controls:
            labelled = (
                nested_in_label
                or attrs.get("id") in self.parser.labels_for
                or bool(attrs.get("aria-label"))
                or bool(attrs.get("aria-labelledby"))
            )
            if not labelled:
                unlabeled.append((tag, attrs.get("id", "<no-id>")))
        self.assertEqual(unlabeled, [])

    def test_every_static_button_has_an_accessible_name(self) -> None:
        unnamed = []
        for attrs, text in self.parser.buttons:
            named = bool(
                text
                or attrs.get("aria-label")
                or attrs.get("aria-labelledby")
                or attrs.get("title")
            )
            if not named:
                unnamed.append(attrs.get("id", "<no-id>"))
        self.assertEqual(unnamed, [])

    def test_mobile_sidebar_exposes_state_and_keyboard_exit(self) -> None:
        self.assertIn('aria-controls="sidebar" aria-expanded="false"', self.html)
        self.assertIn('sidebar.inert=mobile&&!open', self.js)
        self.assertIn('menu.setAttribute("aria-expanded",String(Boolean(open&&mobile)))', self.js)
        self.assertIn('if(event.key==="Escape"){event.preventDefault();setSidebarOpen(false);return;}', self.js)

    def test_responsive_breakpoints_and_reduced_motion_are_declared(self) -> None:
        for breakpoint in ("1100px", "760px", "480px", "360px"):
            self.assertIn(f"@media(max-width:{breakpoint})", self.css)
        self.assertIn("@media(prefers-reduced-motion:reduce)", self.css)
        self.assertIn("transition:none!important", self.css)

    def test_keyboard_focus_indicators_cover_navigation_and_form_controls(self) -> None:
        self.assertIn(".nav-link:focus-visible", self.css)
        self.assertIn("input:focus-visible,select:focus-visible,textarea:focus-visible", self.css)
        self.assertIn(".table-pager button:focus-visible", self.css)
        self.assertIn(".table-scroll[role=\"region\"]:focus-visible", self.css)


    def test_api_wrapper_has_explicit_timeout_abort_and_response_error_paths(self) -> None:
        api = self.js.split("async function api(path,", 1)[1].split("async function withButton", 1)[0]
        for expected in (
            "Number.isFinite(timeout)", "new AbortController()",
            "externalSignal?.addEventListener", "window.setTimeout",
            "response.text()", "JSON.parse(raw)", "non-JSON response",
            "empty JSON response", "Backend request failed (HTTP ",
            "Request timed out.", "Request cancelled.",
            "Network connection failed.", "window.clearTimeout(timer)",
            "removeEventListener",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, api)

    def test_backend_connection_rejects_insecure_remote_urls_and_embedded_credentials(self) -> None:
        connect = self.js.split("function connectSettings()", 1)[1].split("function bind()", 1)[0]
        self.assertIn('parsed.protocol!=="https:"&&!localHttp', connect)
        self.assertIn("parsed.username||parsed.password||parsed.search||parsed.hash", connect)
        self.assertIn('state.token=$("backend-token").value.trim()', connect)
        self.assertIn("clearConnectionScopedData", connect)

    def test_mobile_navigation_restores_focus_and_closes_on_escape(self) -> None:
        sidebar = self.js.split("function setSidebarOpen(open)", 1)[1].split("function navigate", 1)[0]
        self.assertIn("if(!open&&mobile&&sidebar.contains(document.activeElement))menu.focus()", sidebar)
        self.assertIn("if(open&&mobile)sidebar.querySelector(", sidebar)
        self.assertIn('[tabindex]:not([tabindex="-1"])', sidebar)
        self.assertIn('if(event.key==="Escape"){event.preventDefault();setSidebarOpen(false);return;}', self.js)
        self.assertIn("if(event.shiftKey&&(active===first||!sidebar.contains(active)))", self.js)
        self.assertIn("else if(!event.shiftKey&&(active===last||!sidebar.contains(active)))", self.js)


if __name__ == "__main__":
    unittest.main()
