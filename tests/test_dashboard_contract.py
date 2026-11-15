from __future__ import annotations

import re
import unittest
from html.parser import HTMLParser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"


class _Ids(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if key == "id" and value:
                self.ids.add(value)


class DashboardContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = (DASHBOARD / "index.html").read_text(encoding="utf-8")
        cls.js = (DASHBOARD / "app.js").read_text(encoding="utf-8")
        cls.chart_js = (DASHBOARD / "chart.js").read_text(encoding="utf-8")
        cls.css = (DASHBOARD / "app.css").read_text(encoding="utf-8")
        parser = _Ids()
        parser.feed(cls.html)
        cls.ids = parser.ids

    def test_local_assets_are_present_and_referenced(self) -> None:
        self.assertIn('./app.css', self.html)
        self.assertIn('./chart.js', self.html)
        self.assertIn('./app.js', self.html)
        for name in ("app.css", "chart.js", "app.js"):
            self.assertTrue((DASHBOARD / name).is_file(), name)

    def test_javascript_dom_id_references_exist(self) -> None:
        references = set(re.findall(r'\$\("([^"]+)"\)', self.js))
        self.assertFalse(references - self.ids, sorted(references - self.ids))

    def test_complete_timeframe_set_is_present(self) -> None:
        expected = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "3h", "4h", "6h", "8h", "12h", "1D", "3D", "1W", "1M"}
        self.assertTrue(all(f'"{value}"' in self.js for value in expected))

    def test_spot_scanner_defaults_to_all_quote_assets(self) -> None:
        self.assertIn('value="" aria-label="Quote asset" placeholder="All quote assets (optional)"', self.html)
        self.assertIn('path="/api/v1/markets/spot/scan"+(quote?', self.js)

    def test_custom_three_hour_aggregation_requires_complete_aligned_bars(self) -> None:
        self.assertIn("function aggregate3h", self.chart_js)
        self.assertIn("a.length!==3", self.chart_js)
        self.assertIn("start+3600000", self.chart_js)
        self.assertIn("start+7200000", self.chart_js)

    def test_credentials_are_not_persisted_in_browser_storage(self) -> None:
        for forbidden in ("localStorage", "sessionStorage", "document.cookie"):
            self.assertNotIn(forbidden, self.js)
        self.assertIn('credentials:"omit"', self.js)

    def test_no_order_or_withdrawal_execution_routes_are_exposed(self) -> None:
        for forbidden in ("/api/v1/orders", "/api/v1/order", "/api/v1/withdraw", "/api/v1/withdrawals"):
            self.assertNotIn(forbidden, self.html + self.js + self.chart_js)

    def test_remote_backend_requires_https(self) -> None:
        self.assertIn("Use HTTPS for remote backends", self.js)
        self.assertIn("http://localhost", self.js)

    def test_market_scanners_support_sorting_and_bounded_pagination(self) -> None:
        self.assertIn("const tableViews = {}", self.js)
        self.assertIn("pageSize:100", self.js)
        self.assertIn('setAttribute("aria-sort"', self.js)
        self.assertIn('textContent="Previous"', self.js)
        self.assertIn('textContent="Next"', self.js)
        self.assertIn("matching / ", self.js)

    def test_spot_filter_uses_full_returned_dataset_before_pagination(self) -> None:
        self.assertIn('view.query=e.target.value.trim().toUpperCase()', self.js)
        self.assertIn("view.rows.filter", self.js)
        self.assertIn("filtered.slice(view.page*view.pageSize", self.js)

    def test_dark_dense_terminal_shell_exists(self) -> None:
        self.assertIn('class="sidebar"', self.html)
        self.assertIn('class="metric-grid"', self.html)
        self.assertIn('class="chart-placeholder"', self.html)
        self.assertIn("--surface:", self.css)
        self.assertIn("--sidebar:264px", self.css)


if __name__ == "__main__":
    unittest.main()
