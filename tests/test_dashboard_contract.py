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
        cls.chart_test_js = (ROOT / "tests" / "test_dashboard_chart.js").read_text(encoding="utf-8")
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
        self.assertIn("function invalidate(){activeLoadSequence++;if(activeLoadController)", self.chart_js)
        self.assertIn("activeLoadController.abort()", self.chart_js)
        self.assertIn("window.DashboardCharts.invalidate()", self.js)
        self.assertIn("invalidateChartView();", self.js)
        self.assertIn("catch(error){if(requestSequence!==activeLoadSequence)return{status:\"SUPERSEDED\"", self.chart_js)
        self.assertIn("activeEvidenceSequence=0", self.js)
        self.assertIn("if(requestSequence!==activeEvidenceSequence)return{status:\"SUPERSEDED\"}", self.js)

    def test_primary_coin_analysis_action_loads_candles(self) -> None:
        self.assertIn('$("load-coin-analysis").addEventListener("click",()=>withButton("load-coin-analysis",loadTechnical', self.js)

    def test_navigation_cancels_stale_analysis_and_market_evidence_requests(self) -> None:
        self.assertIn("if(known!==\"coin-analysis\")cancelAnalysisRequests()", self.js)
        self.assertIn("function cancelAnalysisRequests()", self.js)
        self.assertIn("activeMarketEvidenceController.abort()", self.js)
        self.assertIn('api(path,{signal:controller.signal})', self.js)
        self.assertIn("if(activeMarketEvidenceController){activeMarketEvidenceController.abort();activeMarketEvidenceController=null;}", self.js)

    def test_chart_render_test_doubles_support_document_fragments(self) -> None:
        self.assertGreaterEqual(self.chart_test_js.count("createDocumentFragment"), 2)
        self.assertIn("createDocumentFragment:()=>makeElement", self.chart_test_js)

    def test_chart_svg_nodes_are_batched_and_bollinger_inputs_are_guarded(self) -> None:
        render_body = self.chart_js.split("function render(c)", 1)[1].split("\\nfunction invalidate", 1)[0]
        bollinger_body = self.chart_js.split("function bollingerSeries(", 1)[1].split("\\nfunction adxSegment", 1)[0]
        self.assertIn("document.createDocumentFragment()", render_body)
        self.assertIn("svgContent.append(e)", render_body)
        self.assertIn("svg.append(svgContent)", render_body)
        self.assertIn("if(!Array.isArray(values))return{upper:[],middle:[],lower:[]}", bollinger_body)
        self.assertIn("Bollinger bands safely reject non-array input", self.chart_test_js)

    def test_ema_and_finite_mean_use_scaled_convex_blending(self) -> None:
        self.assertIn("function finiteBlend(previous,current,weight)", self.chart_js)
        self.assertIn("previous/scale*(1-weight)+current/scale*weight", self.chart_js)
        self.assertIn("value=finiteBlend(value,values[i],k)", self.chart_js)
        self.assertIn("EMA and incremental means remain finite for repeated values", self.chart_test_js)

    def test_wilder_smoothing_uses_overflow_safe_convex_updates(self) -> None:
        self.assertIn("g=g*((n-1)/n)+Math.max(d,0)/n", self.chart_js)
        self.assertIn("averageGain=averageGain*((n-1)/n)+gain/n", self.chart_js)
        self.assertIn("value=value*((n-1)/n)+tr/n", self.chart_js)
        self.assertIn("Wilder RSI and ATR smoothing remain finite for very large", self.chart_test_js)

    def test_atr_breaks_wilder_state_on_structurally_invalid_ohlc(self) -> None:
        atr_body = self.chart_js.split("function atrSeries(", 1)[1].split("\\nfunction macdComponents", 1)[0]
        self.assertIn("cur.high>=Math.max(cur.low,cur.close)", atr_body)
        self.assertIn("prev.high>=Math.max(prev.low,prev.close)", atr_body)
        self.assertIn("ATR rejects malformed current and previous OHLC candles", self.chart_test_js)

    def test_adx_breaks_segments_on_structurally_invalid_ohlc(self) -> None:
        adx_body = self.chart_js.split("function adxSeries(", 1)[1].split("\\nfunction stochRsiSeries", 1)[0]
        self.assertIn("candle.high>=Math.max(candle.low,candle.close)", adx_body)
        self.assertIn("candle.low<=Math.min(candle.high,candle.close)", adx_body)
        self.assertIn("ADX treats structurally invalid OHLC bounds as a segment break", self.chart_test_js)

    def test_stochastic_rsi_uses_linear_rolling_extrema_and_smoothing(self) -> None:
        stoch_body = self.chart_js.split("function stochRsiSeries(", 1)[1].split("\\nfunction drawLinePanel", 1)[0]
        self.assertIn("const minDeque=[],maxDeque=[]", stoch_body)
        self.assertIn("minDeque[minHead]<=i-stochPeriod", stoch_body)
        self.assertIn("maxDeque[maxHead]<=i-stochPeriod", stoch_body)
        self.assertIn("kSum+=raw[i]", stoch_body)
        self.assertIn("dSum+=k[i]", stoch_body)
        self.assertNotIn("rsi.slice(i-stochPeriod+1,i+1)", stoch_body)
        self.assertIn("optimized Stochastic RSI matches a straightforward rolling-window reference", self.chart_test_js)
        self.assertIn("Stochastic RSI rolling extrema and smoothing restart cleanly after missing observations", self.chart_test_js)

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

    def test_scanner_new_dataset_resets_pagination_and_keeps_missing_values_last(self) -> None:
        self.assertIn("if(incomingRows!==view.rows){view.rows=incomingRows.slice();view.page=0;view.sortedCache=null;}", self.js)
        missing_guard = self.js.split("sortable.sort((a,b)=>", 1)[1].split(";filteredCount=filtered.length", 1)[0]
        self.assertIn("if(a.missing!==b.missing)return a.missing?1:-1", missing_guard)
        self.assertIn("cmp*view.direction", missing_guard)

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
        self.assertIn('finally { window.clearTimeout(timer); externalSignal?.removeEventListener("abort",abortFromCaller); }', self.js)

    def test_scanner_sort_precomputes_values_and_reuses_collator(self) -> None:
        self.assertIn("const scannerCollator = new Intl.Collator", self.js)
        self.assertIn("const sortable=filtered.map(item=>", self.js)
        self.assertIn("numeric:numericValue(value)", self.js)
        self.assertIn("sortable.sort((a,b)=>", self.js)
        self.assertIn("const sortedRows=sortable.map(entry=>entry.item)", self.js)
        self.assertNotIn('localeCompare(String(b?.symbol', self.js)

    def test_scanner_numeric_sort_rejects_coercible_non_primitive_values(self) -> None:
        self.assertIn('if(typeof value==="number")return Number.isFinite(value)?value:null', self.js)
        self.assertIn('if(typeof value!=="string"||value.trim()==="")return null', self.js)
        self.assertIn("const parsed=Number(value);return Number.isFinite(parsed)?parsed:null", self.js)

    def test_backend_error_details_are_sanitized_and_bounded(self) -> None:
        self.assertIn(r'detail.replace(/[\x00-\x1f\x7f]/g," ").replace(/\s+/g," ").trim().slice(0,300)', self.js)
        self.assertIn('Backend request failed (HTTP "+response.status+")', self.js)
        self.assertNotIn('throw new Error(typeof detail==="string"?detail:json(detail))', self.js)

    def test_scanner_count_metadata_accepts_only_nonnegative_numeric_primitives(self) -> None:
        self.assertIn('typeof value!=="number" && typeof value!=="string"', self.js)
        self.assertIn('typeof value==="string" && value.trim()===""', self.js)
        self.assertIn('Number.isSafeInteger(parsed)&&parsed>=0', self.js)
        self.assertNotIn('Number.isFinite(Number(value))', self.js)

    def test_scanner_display_metadata_accepts_only_safe_primitives(self) -> None:
        self.assertIn('function metadataText(value,fallback="Not supplied")', self.js)
        self.assertIn("maxLength=160", self.js)
        self.assertIn('textValue.length>maxLength?textValue.slice(0,maxLength-1)+"…":textValue', self.js)
        self.assertIn('metadataText(data.source,"Backend response",120)', self.js)
        self.assertIn('metadataText(data.status,metadataText(data.scan_status,"Returned",80),80)', self.js)
        self.assertIn('typeof value==="string"&&value.trim()!==""', self.js)
        self.assertIn('typeof value==="number"&&Number.isFinite(value)', self.js)
        self.assertIn('return fallback;', self.js)
        self.assertIn('metadataText(data.status,metadataText(data.scan_status,"Returned"))', self.js)
        self.assertIn('metadataText(data.source,"Backend response")', self.js)
        self.assertIn('metadataText(data.generated_at,metadataText(data.timestamp,metadataText(data.updated_at)))', self.js)
        self.assertIn('"Status: "+metadataText(data.status,metadataText(data.scan_status))', self.js)

    def test_scanner_refresh_state_preserves_previous_results_on_failure(self) -> None:
        scan_body = self.js.split("async function scanMarket(market) {", 1)[1].split("function renderScannerMeta", 1)[0]
        self.assertIn('setText("scan-state","Refreshing · previous results retained")', scan_body)
        self.assertIn('setText("scan-state","Refresh failed · previous results retained")', scan_body)
        self.assertIn('setText("scan-state","Invalid response · previous results retained")', scan_body)
        self.assertLess(scan_body.index('setText("scan-state","Refreshing · previous results retained")'), scan_body.index("await api(path)"))
        self.assertLess(scan_body.index("await api(path)"), scan_body.index("renderScanSummary(data)"))

    def test_scanner_market_is_validated_before_request_state_changes(self) -> None:
        scan_body = self.js.split("async function scanMarket(market) {", 1)[1].split("function renderScannerMeta", 1)[0]
        validation = 'if(!["SPOT","USD_M","COIN_M"].includes(market))throw new Error("Unsupported scanner market selection.")'
        self.assertIn(validation, scan_body)
        self.assertLess(scan_body.index(validation), scan_body.index("const requestSequence=++activeScanSequence"))

    def test_scanner_rejects_invalid_top_level_payload_before_rendering(self) -> None:
        validation = 'if(data===null||typeof data!=="object"||Array.isArray(data))throw new Error("Scanner endpoint returned an invalid response shape.'
        scan_body = self.js.split("async function scanMarket(market) {", 1)[1].split("function renderScannerMeta", 1)[0]
        self.assertIn(validation, scan_body)
        self.assertIn("previous results were preserved.", scan_body)
        self.assertLess(scan_body.index(validation), scan_body.index("renderScanSummary(data)"))

    def test_scanner_rejects_non_object_response_rows_and_reports_count(self) -> None:
        self.assertIn('const rowKey=["symbols","markets","results","data"].find(key=>Array.isArray(data[key]))', self.js)
        self.assertIn('const responseRows=hasRowsArray?data[rowKey]:[]', self.js)
        self.assertIn('responseRows.filter(item=>item!==null&&typeof item==="object"&&!Array.isArray(item))', self.js)
        self.assertIn("const rejectedRows=responseRows.length-rows.length", self.js)
        self.assertIn('"Rejected malformed rows: "+rejectedRows', self.js)
        self.assertIn("malformed rows were excluded", self.js)

    def test_scanner_distinguishes_missing_result_array_from_empty_array(self) -> None:
        self.assertIn("const hasRowsArray=rowKey!==undefined", self.js)
        self.assertIn('const rowKey=["symbols","markets","results","data"].find(key=>Array.isArray(data[key]))', self.js)
        self.assertIn('const additionalRowKeys=["symbols","markets","results","data"].filter(key=>key!==rowKey&&Array.isArray(data[key]))', self.js)
        self.assertIn('"Additional array fields: "+(additionalRowKeys.length?additionalRowKeys.join(", "):"None")', self.js)
        self.assertIn("renderScannerMeta(market,data,rows,rejectedRows,rowKey,additionalRowKeys)", self.js)
        self.assertIn('"Result field: "+(rowKey||"Not supplied")', self.js)
        self.assertIn("No recognized result array was supplied.", self.js)
        self.assertIn('!hasRowsArray||rejectedRows?"info":"success"', self.js)
        scan_body = self.js.split("async function scanMarket(market) {", 1)[1].split("function renderScannerMeta", 1)[0]
        self.assertIn("if(hasRowsArray){", scan_body)
        self.assertIn('else setText("scan-state","Incomplete response · previous results retained")', scan_body)
        self.assertLess(scan_body.index("const hasRowsArray=rowKey!==undefined"), scan_body.index("if(hasRowsArray)renderScanSummary(data)"))
        self.assertLess(scan_body.index("if(hasRowsArray)renderScanSummary(data)"), scan_body.index("if(hasRowsArray){"))
        self.assertLess(scan_body.index("if(hasRowsArray){"), scan_body.index('renderRows("spot-rows",rows,6)'))
        self.assertLess(scan_body.index("if(hasRowsArray){"), scan_body.index('renderRows("usdm-rows",rows,5)'))
        self.assertLess(scan_body.index("if(hasRowsArray){"), scan_body.index('renderRows("coinm-rows",rows,5)'))

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

    def test_chart_requests_abort_superseded_transports_and_keep_sequence_guard(self) -> None:
        self.assertIn("let activeLoadSequence=0,activeLoadController=null", self.chart_js)
        self.assertIn("if(activeLoadController)activeLoadController.abort()", self.chart_js)
        self.assertIn("function invalidate(){activeLoadSequence++;if(activeLoadController)", self.chart_js)
        self.assertIn("{signal:controller.signal}", self.chart_js)
        self.assertIn("if(requestSequence!==activeLoadSequence)return{status:\\"SUPERSEDED\\"", self.chart_js)
        self.assertIn("chart invalidation actively aborts the in-flight API request", self.chart_test_js)

    def test_api_wrapper_composes_caller_cancellation_with_timeout(self) -> None:
        self.assertIn("signal:externalSignal", self.js)
        self.assertIn('externalSignal?.addEventListener("abort",abortFromCaller', self.js)
        self.assertIn('externalSignal?.aborted?"Request cancelled.":"Request timed out."', self.js)
        self.assertIn('externalSignal?.removeEventListener("abort",abortFromCaller)', self.js)

    def test_chart_requests_ignore_superseded_responses_and_failures(self) -> None:
        self.assertIn('let activeLoadSequence=0', self.chart_js)
        self.assertIn('function invalidate(){activeLoadSequence++;if(activeLoadController)', self.chart_js)
        self.assertIn('if(requestSequence!==activeLoadSequence)return{status:"SUPERSEDED"', self.chart_js)
        self.assertIn('catch(error){if(requestSequence!==activeLoadSequence)return{status:"SUPERSEDED"', self.chart_js)


    def test_dashboard_stylesheet_has_no_escaped_newline_tokens(self) -> None:
        self.assertNotIn(chr(92) + "n", self.css)
        self.assertIn(chr(10) + ".chart-caption{", self.css)
        self.assertIn(chr(10) + ".indicator-pane{", self.css)


    def test_three_hour_aggregation_requires_exact_hourly_close_times(self) -> None:
        aggregation_body = self.chart_js.split("function aggregate3h(rows){", 1)[1].split("\\nfunction ema", 1)[0]
        self.assertIn("x.closeTime!==x.time+3599999", aggregation_body)
        self.assertIn("invalidCloseTime[1].closeTime += 1", self.chart_test_js)
        self.assertIn("aggregate3h(invalidCloseTime).length, 0", self.chart_test_js)

    def test_indicator_reference_fixtures_cover_ema_rsi_and_atr(self) -> None:
        self.assertIn("EMA seeds with the initial SMA", self.chart_test_js)
        self.assertIn("Wilder RSI and ATR match hand-calculated", self.chart_test_js)
        self.assertIn("assert.deepEqual(result.slice(2),[2,3,4])", self.chart_test_js)
        self.assertIn("assert.equal(atr[3],4.5)", self.chart_test_js)

    def test_chart_large_dataset_regression_fixtures_are_present(self) -> None:
        self.assertIn('parse handles a large reversed candle batch', self.chart_test_js)
        self.assertIn('Array.from({length:10000}', self.chart_test_js)
        self.assertIn('3h aggregation scales across many complete buckets', self.chart_test_js)
        self.assertIn('assert.equal(aggregated.length, 1000)', self.chart_test_js)
        self.assertIn('assert.equal(gapAggregated.length, 999)', self.chart_test_js)

    def test_health_endpoint_rejects_non_object_json_responses(self) -> None:
        health_body = self.js.split("async function loadHealth() {", 1)[1].split("function invalidateScanRequests()", 1)[0]
        self.assertIn('if(result===null||typeof result!=="object"||Array.isArray(result))throw new Error("Health endpoint returned an invalid response shape.', health_body)
        self.assertLess(health_body.index("invalid response shape"), health_body.index("state.lastHealth=result"))

    def test_quality_endpoint_rejects_non_object_json_and_preserves_previous_report(self) -> None:
        quality_body = self.js.split("async function loadQuality() {", 1)[1].split("function connectSettings()", 1)[0]
        self.assertIn('if(data===null||typeof data!=="object"||Array.isArray(data))', quality_body)
        self.assertIn('setText("quality-state","Invalid response · previous report retained")', quality_body)
        self.assertLess(quality_body.index("invalid response shape"), quality_body.index('showJson("quality-output",data)'))

    def test_backend_reconfiguration_resets_stale_connection_and_data_statuses(self) -> None:
        connect_body = self.js.split("function connectSettings() {", 1)[1].split("function bind()", 1)[0]
        self.assertIn('setText("health-status","Not checked · test the new connection")', connect_body)
        self.assertIn('setConnection(false,"Connection settings changed · test connection")', connect_body)
        self.assertIn('setText("scan-state","Connection settings changed · run a new scan")', connect_body)
        self.assertIn('setText("quality-state","Connection settings changed · run a new quality check")', connect_body)
        clear_body = self.js.split('$("clear-credentials").addEventListener', 1)[1].split('$("default-market")', 1)[0]
        self.assertIn('setText("health-status","Not checked · backend credentials cleared")', clear_body)
        self.assertIn('setText("quality-state","Backend credentials cleared · quality check unavailable")', clear_body)

    def test_market_selection_invalidation_does_not_leave_scan_loading_state(self) -> None:
        market_tabs = self.js.split('document.querySelectorAll(".market-tab").forEach', 1)[1].split('$("run-market-scan")', 1)[0]
        default_market = self.js.split('$("default-market").addEventListener', 1)[1].split('$("default-timeframe")', 1)[0]
        self.assertIn('setText("scan-state","Market selection changed · run a new scan")', market_tabs)
        self.assertIn('setText("scan-state","Market selection changed · run a new scan")', default_market)

    def test_health_refresh_exposes_retained_previous_status(self) -> None:
        health_body = self.js.split("async function loadHealth() {", 1)[1].split("function invalidateScanRequests()", 1)[0]
        self.assertIn('setText("health-status","Checking backend health · previous status retained")', health_body)
        self.assertLess(health_body.index('setText("health-status","Checking backend health · previous status retained")'), health_body.index('await api("/health")'))
        self.assertIn('setText("health-status","Unavailable")', health_body)

    def test_quality_refresh_and_spot_quote_change_explain_retained_results(self) -> None:
        quality_body = self.js.split("async function loadQuality() {", 1)[1].split("function connectSettings()", 1)[0]
        self.assertIn('" · previous report retained"', quality_body)
        quote_handler = self.js.split('$("spot-quote").addEventListener', 1)[1].split('[["spot-search"', 1)[0]
        self.assertIn('setText("scan-state","Spot quote filter changed · previous results retained; run a new scan")', quote_handler)
        self.assertIn("invalidateScanRequests()", quote_handler)

    def test_connection_test_does_not_report_success_for_superseded_health(self) -> None:
        handler = self.js.split('$("test-connection").addEventListener', 1)[1].split('$("clear-credentials").addEventListener', 1)[0]
        self.assertIn("const result=await loadHealth()", handler)
        self.assertIn('if(result?.status==="SUPERSEDED")return result', handler)
        self.assertLess(handler.index('if(result?.status==="SUPERSEDED")return result'), handler.index('setText("settings-status","Backend health endpoint responded successfully.")'))

    def test_overview_refresh_attempts_health_and_scanner_independently(self) -> None:
        refresh_body = self.js.split('$("refresh-page").addEventListener', 1)[1].split('$("global-market").addEventListener', 1)[0]
        self.assertIn("Promise.allSettled([loadHealth(),scanMarket(state.market)])", refresh_body)
        self.assertIn('result.status==="rejected"', refresh_body)
        self.assertIn('metadataText(result.reason?.message,"Request failed",120)', refresh_body)
        self.assertIn('Overview refresh partially failed: ', refresh_body)

    def test_technical_chart_request_preserves_previous_view_on_refresh_and_failure(self) -> None:
        technical_body = self.js.split("async function loadTechnical() {", 1)[1].split("function initTimeframes()", 1)[0]
        self.assertIn('setText("chart-state","Loading candles · previous chart retained")', technical_body)
        self.assertIn('setText("chart-state","Chart request failed · previous chart retained")', technical_body)
        self.assertIn('metadataText(error?.message,"Unknown error",160)', technical_body)
        self.assertLess(technical_body.index("await window.DashboardCharts.load"), technical_body.index('state.lastAnalysis=data'))
        self.assertIn('if(requestSequence!==activeEvidenceSequence||data?.status==="SUPERSEDED")return{status:"SUPERSEDED"}', technical_body)

    def test_recent_metadata_and_evidence_contracts_are_discoverable_before_main_guard(self) -> None:
        source = Path(__file__).read_text(encoding="utf-8")
        main_guard = source.index("if " + '__name__ == "__main__":')
        for method in (
            "test_health_and_quality_status_metadata_is_bounded_and_type_safe",
            "test_market_evidence_summary_metadata_is_bounded_and_type_safe",
            "test_market_evidence_refresh_preserves_previous_payload_until_success",
            "test_market_evidence_failure_keeps_previous_payload_and_shows_bounded_error",
            "test_quality_failure_keeps_previous_report_and_shows_bounded_error",
            "test_health_connection_error_label_is_length_bounded",
        ):
            self.assertLess(source.index(f"    def {method}"), main_guard, method)


    def test_health_and_quality_status_metadata_is_bounded_and_type_safe(self) -> None:
        self.assertIn('metadataText(result.status,"Healthy response",80)', self.js)
        self.assertIn('metadataText(data.status,"Report received",80)', self.js)
        self.assertIn('function metadataText(value,fallback="Not supplied",maxLength=160)', self.js)

    def test_market_evidence_summary_metadata_is_bounded_and_type_safe(self) -> None:
        self.assertIn('metadataText(data.summary,metadataText(data.status,"Market evidence returned. Inspect evidence payload.",120),120)', self.js)

    def test_scanner_count_alias_conflicts_are_reported_without_merging(self) -> None:
        self.assertIn("function scannerCountAliasConflicts(data,countNames)", self.js)
        self.assertIn('const distinct=new Set(supplied.map(entry=>entry.value))', self.js)
        self.assertIn('distinct.size>1?[label+": "+supplied.map', self.js)
        self.assertIn('"Count alias conflicts: "+(scannerCountAliasConflicts(data,countNames).join("; ")||"None detected")', self.js)
        self.assertIn('extractCount(data,countNames.eligible)', self.js)

    def test_scanner_coverage_identifies_source_and_timestamp_alias_provenance(self) -> None:
        self.assertIn("function metadataFieldName(data,names)", self.js)
        self.assertIn('metadataFieldName(data,["source"])', self.js)
        self.assertIn('metadataFieldName(data,["generated_at","timestamp","updated_at"])', self.js)
        self.assertIn('"Timestamp field: "+', self.js)
        self.assertIn('"Source field: "+', self.js)

    def test_scanner_coverage_identifies_status_alias_provenance(self) -> None:
        self.assertIn('metadataFieldName(data,["status","scan_status"])', self.js)
        self.assertIn('"Status field: "+', self.js)

    def test_market_evidence_refresh_preserves_previous_payload_until_success(self) -> None:
        evidence_body = self.js.split("async function loadMarketEvidence() {", 1)[1].split("async function loadTechnical()", 1)[0]
        self.assertIn('setText("chart-state","Loading market evidence · previous evidence retained")', evidence_body)
        self.assertIn('window.DashboardCharts.invalidate();', evidence_body)
        self.assertNotIn('invalidateChartView("Market evidence endpoint does not provide candle chart data.")', evidence_body)
        self.assertLess(evidence_body.index("await api(path)"), evidence_body.index('showJson("analysis-output",data)'))
        self.assertIn('showJson("analysis-output",data)', evidence_body)

    def test_market_evidence_failure_keeps_previous_payload_and_shows_bounded_error(self) -> None:
        self.assertIn('setText("chart-state","Evidence request failed · previous evidence retained")', self.js)
        self.assertIn('setText("technical-summary","Request failed: "+metadataText(error?.message,"Unknown error",160))', self.js)
        self.assertIn('if(requestSequence!==activeEvidenceSequence)return{status:"SUPERSEDED"};setText("chart-state"', self.js)

    def test_quality_failure_keeps_previous_report_and_shows_bounded_error(self) -> None:
        self.assertIn('setText("quality-state","Load failed · previous report retained · "+metadataText(error?.message,"Unknown error",120))', self.js)
        self.assertIn('if(requestSequence!==activeQualitySequence)return{status:"SUPERSEDED"};setText("quality-state"', self.js)

    def test_health_connection_error_label_is_length_bounded(self) -> None:
        self.assertIn('setConnection(false,"Backend unavailable: "+metadataText(error?.message,"Request failed",160))', self.js)


if __name__ == "__main__":
    unittest.main()
