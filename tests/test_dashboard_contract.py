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
        self.duplicates: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for key, value in attrs:
            if key == "id" and value:
                if value in self.ids:
                    self.duplicates.append(value)
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

    def test_html_ids_are_unique_and_chart_script_loads_before_app(self) -> None:
        parser = _Ids()
        parser.feed(self.html)
        self.assertEqual(parser.duplicates, [])
        self.assertLess(self.html.index('src="./chart.js"'), self.html.index('src="./app.js"'))

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

    def test_chart_fixture_suite_covers_parsing_aggregation_and_indicators(self) -> None:
        chart_tests = ROOT / "tests" / "test_dashboard_chart.js"
        self.assertTrue(chart_tests.is_file())
        source = chart_tests.read_text(encoding="utf-8")
        for case in (
            "parse sorts valid OHLCV rows",
            "3h aggregation combines exactly three",
            "3h aggregation discards incomplete",
            "timeframe and market route mapping",
            "flat price RSI is neutral",
            "Bollinger bands are candle-aligned",
            "Wilder ADX and Stochastic RSI",
            "ADX reaches 100 on a steady one-directional trend",
            "Stochastic RSI applies the documented K and D smoothing",
            "Bollinger population deviation has a reproducible 20-candle reference",
            "insufficient history leaves long-period indicators unavailable",
        ):
            self.assertIn(case, source)

    def test_chart_discards_superseded_timeframe_responses(self) -> None:
        self.assertIn("let activeLoadSequence=0", self.chart_js)
        self.assertIn("const requestSequence=++activeLoadSequence", self.chart_js)
        self.assertIn('status:"SUPERSEDED"', self.chart_js)
        self.assertIn("function invalidate(){activeLoadSequence++;}", self.chart_js)
        self.assertIn("window.DashboardCharts.invalidate()", self.js)
        self.assertIn("invalidateChartView();", self.js)
        self.assertIn("catch(error){if(requestSequence!==activeLoadSequence)return{status:\"SUPERSEDED\"", self.chart_js)
        self.assertIn("activeEvidenceSequence=0", self.js)
        self.assertIn("if(requestSequence!==activeEvidenceSequence)return{status:\"SUPERSEDED\"}", self.js)

    def test_primary_coin_analysis_action_loads_candles(self) -> None:
        self.assertIn('$("load-coin-analysis").addEventListener("click",()=>withButton("load-coin-analysis",loadTechnical', self.js)

    def test_chart_exposes_separate_indicator_panes(self) -> None:
        for token in (
            'drawLinePanel("RSI (14) · Wilder"',
            'drawLinePanel("MACD line · EMA12 − EMA26"',
            'drawLinePanel("MACD signal · EMA9 of MACD"',
            'drawLinePanel("MACD histogram · line − signal"',
            'drawLinePanel("ATR (14) · Wilder"',
        ):
            self.assertIn(token, self.chart_js)
        for token in (
            "function bollingerSeries",
            "function adxSeries",
            "function stochRsiSeries",
            'drawLinePanel("ADX (14) · Wilder"',
            'drawLinePanel("Stochastic RSI · %K"',
            'drawLinePanel("Stochastic RSI · %D"',
        ):
            self.assertIn(token, self.chart_js)
        self.assertIn(".indicator-pane", self.css)

    def test_indicator_series_fixture_coverage_exists(self) -> None:
        source = (ROOT / "tests" / "test_dashboard_chart.js").read_text(encoding="utf-8")
        self.assertIn("indicator series align to candles", source)
        self.assertIn("macdComponents", source)

    def test_chart_parser_rejects_blank_numbers_and_duplicate_timestamps(self) -> None:
        self.assertIn('v.trim()===""', self.chart_js)
        self.assertIn("counts.get(candle.time)===1", self.chart_js)
        source = (ROOT / "tests" / "test_dashboard_chart.js").read_text(encoding="utf-8")
        self.assertIn("whitespace-only numeric fields and all duplicate candle timestamps", source)
        self.assertIn("flat candles produce neutral Stochastic RSI and zero ADX", source)

    def test_chart_parser_rejects_invalid_values_and_uses_wilder_atr(self) -> None:
        self.assertIn("Object.values(c).every(Number.isFinite)", self.chart_js)
        self.assertIn("c.volume>=0", self.chart_js)
        self.assertIn("function atrWilder", self.chart_js)
        self.assertIn("atr_14_wilder", self.chart_js)
        self.assertIn("if(g===0&&l===0)return 50", self.chart_js)

    def test_credentials_are_not_persisted_in_browser_storage(self) -> None:
        for forbidden in ("localStorage", "sessionStorage", "document.cookie"):
            self.assertNotIn(forbidden, self.js)
        self.assertIn('credentials:"omit"', self.js)
        self.assertIn("if(!Number.isFinite(timeout)||timeout<=0)", self.js)
        self.assertIn("const hasBody=body!==undefined", self.js)
        self.assertIn("if(response.ok&&data===null)", self.js)

    def test_no_order_or_withdrawal_execution_routes_are_exposed(self) -> None:
        for forbidden in ("/api/v1/orders", "/api/v1/order", "/api/v1/withdraw", "/api/v1/withdrawals"):
            self.assertNotIn(forbidden, self.html + self.js + self.chart_js)

    def test_remote_backend_requires_https(self) -> None:
        self.assertIn("Use HTTPS for remote backends", self.js)
        self.assertIn("http://localhost", self.js)
        self.assertIn("let parsed;try{parsed=new URL(url);}", self.js)
        self.assertIn("parsed.username||parsed.password||parsed.search||parsed.hash", self.js)

    def test_market_scanners_support_sorting_and_bounded_pagination(self) -> None:
        self.assertIn("const tableViews = {}", self.js)
        self.assertIn("pageSize:100", self.js)
        self.assertIn('setAttribute("aria-sort"', self.js)
        self.assertIn('textContent="Previous"', self.js)
        self.assertIn('textContent="Next"', self.js)
        self.assertIn("matching / ", self.js)
        self.assertIn("let activeScanSequence=0", self.js)
        self.assertIn("function invalidateScanRequests(){activeScanSequence++;}", self.js)
        self.assertIn("if(requestSequence!==activeScanSequence)return{status:\"SUPERSEDED\",market}", self.js)
        self.assertIn("const numericValue=v=>", self.js)
        self.assertIn("if(am!==bm)return am?1:-1", self.js)
        self.assertIn("else if((an!==null)!==(bn!==null))cmp=an!==null?-1:1", self.js)
        self.assertIn('String(a?.symbol??"").localeCompare(String(b?.symbol??""),undefined,{numeric:true,sensitivity:"base"})', self.js)
        self.assertIn('th.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" ")', self.js)
        self.assertIn('th.setAttribute("aria-label","Sort by "+keys[index])', self.js)
        self.assertIn('th.setAttribute("aria-keyshortcuts","Enter Space")', self.js)
        self.assertNotIn('th.setAttribute("role","button")', self.js)
        self.assertIn('info.setAttribute("aria-live","polite")', self.js)
        self.assertIn('prev.setAttribute("aria-label","Previous scanner page")', self.js)
        self.assertIn('next.setAttribute("aria-label","Next scanner page")', self.js)

    def test_spot_filter_uses_full_returned_dataset_before_pagination(self) -> None:
        self.assertIn('view.query=e.target.value.trim().toUpperCase()', self.js)
        self.assertIn("view.rows.filter", self.js)
        self.assertIn("sortedRows.slice(view.page*view.pageSize", self.js)

    def test_health_and_market_evidence_ignore_superseded_responses(self) -> None:
        self.assertIn("let activeHealthSequence=0", self.js)
        self.assertIn("const requestSequence=++activeHealthSequence", self.js)
        self.assertIn('if(requestSequence!==activeHealthSequence)return{status:"SUPERSEDED"}', self.js)
        self.assertIn("activeHealthSequence++;window.DashboardCharts.invalidate()", self.js)
        self.assertIn('catch(error){if(requestSequence!==activeEvidenceSequence)return{status:"SUPERSEDED"}', self.js)

    def test_spot_quote_filter_invalidates_pending_scan(self) -> None:
        self.assertIn('$("spot-quote").addEventListener("input",()=>{invalidateScanRequests();', self.js)
        self.assertIn('setText("spot-coverage","Quote filter changed · run a new Spot scan")', self.js)

    def test_scanner_cells_normalize_null_and_empty_values(self) -> None:
        self.assertIn('item?.[key]===undefined||item?.[key]===null||item?.[key]===""?"—"', self.js)

    def test_quality_report_ignores_superseded_requests(self) -> None:
        self.assertIn("let activeQualitySequence=0", self.js)
        self.assertIn("function invalidateQualityRequest(){activeQualitySequence++;}", self.js)
        self.assertIn('if(requestSequence!==activeQualitySequence)return{status:"SUPERSEDED"}', self.js)
        self.assertIn('["quality-market","quality-symbol","quality-interval","quality-lookback"]', self.js)
        self.assertIn('addEventListener("input",invalidate)', self.js)
        self.assertIn('setText("quality-state","Selection changed · run a new quality check")', self.js)
        self.assertIn("invalidateQualityRequest();activeEvidenceSequence++", self.js)

    def test_mobile_scanner_pagination_and_keyboard_focus_styles_exist(self) -> None:
        self.assertIn(".table-pager{flex-wrap:wrap}", self.css)
        self.assertIn("@media(max-width:480px){.table-pager", self.css)
        self.assertIn(".table-scroll th:focus-visible", self.css)
        self.assertIn(".table-pager button:disabled", self.css)

    def test_dark_dense_terminal_shell_exists(self) -> None:
        self.assertIn('class="sidebar"', self.html)
        self.assertIn('class="metric-grid"', self.html)
        self.assertIn('class="chart-placeholder"', self.html)
        self.assertIn("--surface:", self.css)
        self.assertIn("--sidebar:264px", self.css)


    def test_duplicate_candle_filter_is_reachable_after_parse(self) -> None:
        parse_body = self.chart_js.split("function parse(rows){", 1)[1].split("\nfunction aggregate3h", 1)[0]
        self.assertIn("const parsed=rows.filter", parse_body)
        self.assertIn("return parsed.filter(candle=>counts.get(candle.time)===1)", parse_body)
        self.assertLess(parse_body.index("const parsed="), parse_body.index("return parsed.filter"))

    def test_scanner_pagination_reuses_cached_filtered_and_sorted_rows(self) -> None:
        self.assertIn("view.sortedCache=null", self.js)
        self.assertIn("cached.rows===view.rows", self.js)
        self.assertIn("cached.query===view.query", self.js)
        self.assertIn("cached.sortKey===view.sortKey", self.js)
        self.assertIn("cached.direction===view.direction", self.js)
        self.assertIn("sortedRows=cached.sortedRows", self.js)
        self.assertIn("view.sortedCache={rows:view.rows", self.js)

    def test_navigation_marks_the_current_page_for_assistive_technology(self) -> None:
        self.assertIn('a.setAttribute("aria-current","page")', self.js)
        self.assertIn('a.removeAttribute("aria-current")', self.js)

    def test_mobile_navigation_exposes_state_and_supports_escape(self) -> None:
        self.assertIn('aria-controls="sidebar"', self.html)
        self.assertIn('aria-expanded="false"', self.html)
        self.assertIn('setAttribute("aria-expanded",String(open))', self.js)
        self.assertIn('event.key==="Escape"', self.js)
        self.assertIn('$("mobile-menu").focus()', self.js)
        self.assertIn(".nav-link:focus-visible", self.css)

    def test_api_network_failures_are_distinguished_from_timeouts(self) -> None:
        self.assertIn('Request timed out.', self.js)
        self.assertIn('Network connection failed. Check your connection and backend availability.', self.js)
        self.assertIn('finally { window.clearTimeout(timer); }', self.js)

    def test_scanner_sort_precomputes_values_and_reuses_collator(self) -> None:
        self.assertIn("const scannerCollator = new Intl.Collator", self.js)
        self.assertIn("const sortable=filtered.map(item=>", self.js)
        self.assertIn("numeric:numericValue(value)", self.js)
        self.assertIn("sortable.sort((a,b)=>", self.js)
        self.assertIn("const sortedRows=sortable.map(entry=>entry.item)", self.js)
        self.assertNotIn('localeCompare(String(b?.symbol', self.js)

    def test_backend_error_details_are_sanitized_and_bounded(self) -> None:
        self.assertIn(r'detail.replace(/[\x00-\x1f\x7f]/g," ").replace(/\s+/g," ").trim().slice(0,300)', self.js)
        self.assertIn('Backend request failed (HTTP "+response.status+")', self.js)
        self.assertNotIn('throw new Error(typeof detail==="string"?detail:json(detail))', self.js)

    def test_scanner_count_metadata_rejects_blank_boolean_and_negative_values(self) -> None:
        self.assertIn('value.trim()===""', self.js)
        self.assertIn('typeof value!=="boolean"', self.js)
        self.assertIn('Number(value)>=0', self.js)

    def test_spot_scanner_exposes_backend_reported_coverage(self) -> None:
        self.assertIn('id="spot-coverage"', self.html)
        self.assertIn('id="spot-count"', self.html)
        self.assertIn('setText(prefix+"-coverage",details.join(" · "))', self.js)

    def test_usdm_and_coinm_scanners_have_full_result_search_and_coverage(self) -> None:
        for market in ("usdm", "coinm"):
            self.assertIn(f'id="{market}-search"', self.html)
            self.assertIn(f'id="{market}-count"', self.html)
            self.assertIn(f'id="{market}-coverage"', self.html)
            self.assertIn(f'["{market}-search","{market}-rows",5]', self.js)
        self.assertIn("function renderScannerMeta", self.js)
        self.assertIn('"Failed: "+(extractCount(data,countNames.failed)', self.js)
        self.assertIn('"Returned rows: "+rows.length', self.js)


    def test_scanner_search_resets_page_and_cache_tracks_query(self) -> None:
        self.assertIn('view.query=e.target.value.trim().toUpperCase();view.page=0;renderRows(target,view.rows,columns)', self.js)
        self.assertIn('cached.query===view.query', self.js)
        self.assertIn('view.sortedCache={rows:view.rows,query:view.query', self.js)

    def test_api_requests_do_not_send_browser_credentials_or_cache_responses(self) -> None:
        self.assertIn('credentials:"omit"', self.js)
        self.assertIn('cache:"no-store"', self.js)
        self.assertIn('body:hasBody?JSON.stringify(body):undefined', self.js)
        self.assertIn('const hasBody=body!==undefined', self.js)

    def test_chart_requests_ignore_superseded_responses_and_failures(self) -> None:
        self.assertIn('let activeLoadSequence=0', self.chart_js)
        self.assertIn('function invalidate(){activeLoadSequence++;}', self.chart_js)
        self.assertIn('if(requestSequence!==activeLoadSequence)return{status:"SUPERSEDED"', self.chart_js)
        self.assertIn('catch(error){if(requestSequence!==activeLoadSequence)return{status:"SUPERSEDED"', self.chart_js)


    def test_dashboard_stylesheet_has_no_escaped_newline_tokens(self) -> None:
        self.assertNotIn(chr(92) + "n", self.css)
        self.assertIn(chr(10) + ".chart-caption{", self.css)
        self.assertIn(chr(10) + ".indicator-pane{", self.css)


    def test_chart_large_dataset_regression_fixtures_are_present(self) -> None:
        self.assertIn('parse handles a large reversed candle batch', self.chart_test_js)
        self.assertIn('Array.from({length:10000}', self.chart_test_js)
        self.assertIn('3h aggregation scales across many complete buckets', self.chart_test_js)
        self.assertIn('assert.equal(aggregated.length, 1000)', self.chart_test_js)
        self.assertIn('assert.equal(gapAggregated.length, 999)', self.chart_test_js)


if __name__ == "__main__":
    unittest.main()
