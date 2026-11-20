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
        self.assertIn('/dashboard-assets/app.css', self.html)
        self.assertIn('/dashboard-assets/chart.js', self.html)
        self.assertIn('/dashboard-assets/app.js', self.html)
        for name in ("app.css", "chart.js", "app.js"):
            self.assertTrue((DASHBOARD / name).is_file(), name)

    def test_javascript_dom_id_references_exist(self) -> None:
        references = set(re.findall(r'\$\("([^"]+)"\)', self.js))
        self.assertFalse(references - self.ids, sorted(references - self.ids))

    def test_html_ids_are_unique_and_chart_script_loads_before_app(self) -> None:
        parser = _Ids()
        parser.feed(self.html)
        self.assertEqual(parser.duplicates, [])
        self.assertLess(self.html.index('src="/dashboard-assets/chart.js"'), self.html.index('src="/dashboard-assets/app.js"'))

    def test_complete_timeframe_set_is_present(self) -> None:
        expected = {"1m", "3m", "5m", "15m", "30m", "1h", "2h", "3h", "4h", "6h", "8h", "12h", "1D", "3D", "1W", "1M"}
        self.assertTrue(all(f'"{value}"' in self.js for value in expected))


    def test_spot_scanner_defaults_to_all_quote_assets(self) -> None:
        self.assertIn('value="" aria-label="Quote asset" placeholder="All quote assets (optional)"', self.html)
        self.assertIn('quoteFilter=($("spot-quote")?.value||"").trim().toUpperCase()', self.js)
        self.assertIn('path="/api/v1/markets/spot/scan"+(quoteFilter?', self.js)

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
        self.assertIn("requestSequence=++activeLoadSequence", self.chart_js)
        self.assertIn('status:"SUPERSEDED"', self.chart_js)
        self.assertIn("function invalidate(){activeLoadSequence++;if(activeLoadController)", self.chart_js)
        self.assertIn("activeLoadController.abort()", self.chart_js)
        self.assertIn("window.DashboardCharts.invalidate()", self.js)
        self.assertIn("invalidateChartView();", self.js)
        self.assertIn('if(requestSequence!==activeLoadSequence)return{status:"SUPERSEDED",market,symbol,requested_timeframe:tf}', self.chart_js)
        self.assertIn("activeEvidenceSequence=0", self.js)
        self.assertIn('if(requestSequence!==activeEvidenceSequence)return{status:"SUPERSEDED"}', self.js)

    def test_primary_coin_analysis_action_loads_candles(self) -> None:
        self.assertIn('$("load-coin-analysis").addEventListener("click",()=>withButton("load-coin-analysis",loadTechnical', self.js)

    def test_closed_mobile_sidebar_is_removed_from_keyboard_navigation(self) -> None:
        self.assertIn("function setSidebarOpen(open)", self.js)
        self.assertIn("sidebar.inert=mobile&&!open", self.js)
        self.assertIn('setSidebarOpen(false);', self.js)
        self.assertIn('window.addEventListener("resize"', self.js)
        self.assertIn('if(event.key==="Escape"){event.preventDefault();setSidebarOpen(false);return;}', self.js)

    def test_quality_and_backend_inputs_have_explicit_validation(self) -> None:
        self.assertIn('required maxlength="40" pattern="[A-Za-z0-9]{1,40}"', self.html)
        self.assertIn('type="number" min="1" max="2160" step="1" value="168" required', self.html)
        self.assertIn('type="url" placeholder="https://your-private-backend.example" required', self.html)
        self.assertIn('!/^[A-Z0-9]{1,40}$/.test(symbol)', self.js)
        self.assertIn('lookbackInput.setCustomValidity("Enter a whole number from 1 to 2160.")', self.js)
        self.assertIn('const localHttp=parsed.protocol==="http:"&&(parsed.hostname==="localhost"||parsed.hostname==="127.0.0.1"||parsed.hostname==="[::1]")', self.js)
        self.assertIn('parsed.protocol!=="https:"&&!localHttp', self.js)

    def test_dynamic_dashboard_status_regions_are_announced(self) -> None:
        for element_id in ("connection-label", "scan-state", "health-status", "chart-state", "technical-summary", "quality-state", "settings-status"):
            self.assertRegex(self.html, rf'<[^>]+id="{element_id}"[^>]*role="status" aria-live="polite" aria-atomic="true"')

    def test_scanner_tables_are_named_and_keyboard_scrollable(self) -> None:
        self.assertIn('role="region" aria-label="Spot market scan results" tabindex="0"', self.html)
        self.assertIn('role="region" aria-label="USDⓈ-M market scan results" tabindex="0"', self.html)
        self.assertIn('role="region" aria-label="COIN-M market scan results" tabindex="0"', self.html)
        self.assertEqual(self.html.count('<th scope="col">'), 16)
        self.assertIn('.table-scroll[role="region"]:focus-visible', self.css)

    def test_scanner_pagination_preserves_keyboard_focus_after_rerender(self) -> None:
        self.assertIn("function focusPagerControl(table,label)", self.js)
        self.assertIn('focusPagerControl(table,"Previous scanner page")', self.js)
        self.assertIn('focusPagerControl(table,"Next scanner page")', self.js)
        self.assertIn('prev.setAttribute("aria-controls",target)', self.js)
        self.assertIn('next.setAttribute("aria-controls",target)', self.js)

    def test_mobile_sidebar_state_stays_accessible_across_viewport_changes(self) -> None:
        self.assertIn('menu.setAttribute("aria-label",open&&mobile?"Close navigation":"Open navigation")', self.js)
        self.assertIn('sidebar.inert=mobile&&!open', self.js)
        self.assertIn('window.addEventListener("resize",()=>setSidebarOpen(false))', self.js)

    def test_navigation_moves_keyboard_focus_and_hides_decorative_glyphs(self) -> None:
        self.assertIn('target.setAttribute("tabindex","-1")', self.js)
        self.assertIn('target.focus({preventScroll:true})', self.js)
        self.assertRegex(self.html, r'<a class="nav-link[^"]*"[^>]*><span aria-hidden="true">')
        self.assertIn("input:focus-visible,select:focus-visible,textarea:focus-visible", self.css)
        self.assertIn(".page-view h1:focus{outline:none}", self.css)

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
        self.assertIn("const rsi=rsiSeries(values,rsiPeriod),minDeque=[],maxDeque=[]", stoch_body)
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
        self.assertIn("const text=v.trim()", self.chart_js)
        self.assertIn("!/", self.chart_js)
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
        self.assertIn('cache:"no-store"', self.js)
        self.assertIn("if(!Number.isFinite(timeout)||timeout<=0)", self.js)
        self.assertIn("const hasBody=body!==undefined", self.js)
        self.assertIn("if(response.ok&&data===null)", self.js)

    def test_no_order_or_withdrawal_execution_routes_are_exposed(self) -> None:
        for forbidden in ("/api/v1/orders", "/api/v1/order", "/api/v1/withdraw", "/api/v1/withdrawals"):
            self.assertNotIn(forbidden, self.html + self.js + self.chart_js)

    def test_backend_url_validation_is_visible_and_cleared_after_edit(self) -> None:
        self.assertIn("const rejectUrl=(message)=>{urlInput.setCustomValidity(message);urlInput.reportValidity();throw new Error(message);}", self.js)
        self.assertIn('$("backend-url").addEventListener("input",()=> $("backend-url").setCustomValidity(""))', self.js)
        self.assertIn('$("backend-url").setCustomValidity("")', self.js)
        self.assertIn('rejectUrl("Use HTTPS for remote backends.', self.js)
        self.assertIn('rejectUrl("Backend URL must include a host', self.js)


    def test_remote_backend_requires_https(self) -> None:
        self.assertIn("Use HTTPS for remote backends", self.js)
        self.assertIn('parsed.protocol==="http:"', self.js)
        self.assertIn('parsed.hostname==="localhost"', self.js)
        self.assertIn('parsed.hostname==="127.0.0.1"', self.js)
        self.assertIn('parsed.hostname==="[::1]"', self.js)
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
        self.assertIn("function invalidateScanRequests(){activeScanSequence++;if(activeScanController){activeScanController.abort();activeScanController=null;}}", self.js)
        self.assertIn('if(requestSequence!==activeScanSequence)return{status:"SUPERSEDED",market}', self.js)
        self.assertIn("const numericValue=value=>", self.js)
        self.assertIn("if(aMissing!==bMissing)return aMissing?1:-1", self.js)
        self.assertIn("if((an!==null)!==(bn!==null))return an!==null?-1:1", self.js)
        self.assertIn('scannerCollator.compare(String(a?.symbol??""),String(b?.symbol??""))', self.js)
        self.assertIn('th.addEventListener("keydown",event=>{if(event.key==="Enter"||event.key===" ")', self.js)
        self.assertIn('th.setAttribute("aria-label","Sort by "+keys[index])', self.js)
        self.assertIn('th.setAttribute("aria-keyshortcuts","Enter Space")', self.js)
        self.assertNotIn('th.setAttribute("role","button")', self.js)
        self.assertIn('info.setAttribute("aria-live","polite")', self.js)
        self.assertIn('prev.setAttribute("aria-label","Previous scanner page")', self.js)
        self.assertIn('next.setAttribute("aria-label","Next scanner page")', self.js)

    def test_spot_filter_uses_full_returned_dataset_before_pagination(self) -> None:
        self.assertIn('view.query=e.target.value.trim().toUpperCase()', self.js)
        self.assertIn("for(const item of view.rows)", self.js)
        self.assertIn("scannerSearchText(target,item,keys).includes(view.query)", self.js)
        self.assertIn("sortedRows.slice(view.page*view.pageSize", self.js)


    def test_health_and_market_evidence_ignore_superseded_responses(self) -> None:
        self.assertIn("let activeHealthSequence=0", self.js)
        self.assertIn("const requestSequence=activeHealthSequence", self.js)
        self.assertIn('if(requestSequence!==activeHealthSequence)return{status:"SUPERSEDED"}', self.js)
        self.assertIn("activeEvidenceSequence++;window.DashboardCharts.invalidate()", self.js)
        self.assertIn('catch(error){if(requestSequence!==activeEvidenceSequence)return{status:"SUPERSEDED"}', self.js)

    def test_spot_quote_filter_invalidates_pending_scan(self) -> None:
        self.assertIn('$("spot-quote").addEventListener("input",()=>{invalidateScanRequests();', self.js)
        self.assertIn('setText("spot-coverage","Quote filter changed · run a new Spot scan")', self.js)


    def test_scanner_cells_normalize_null_and_empty_values(self) -> None:
        helper = self.js.split("function scannerCellText(key,value)", 1)[1].split("function renderRows", 1)[0]
        self.assertIn('value===null||value===undefined||value===""', helper)
        self.assertIn('return"—"', helper)
        self.assertIn('return Number.isFinite(Number(value))?String(value):"Invalid number"', helper)


    def test_quality_report_ignores_superseded_requests(self) -> None:
        self.assertIn("let activeQualitySequence=0", self.js)
        self.assertIn("function invalidateQualityRequest(){activeQualitySequence++;if(activeQualityController)", self.js)
        self.assertIn('if(requestSequence!==activeQualitySequence)return{status:"SUPERSEDED"}', self.js)
        self.assertIn('["quality-market","quality-symbol","quality-interval","quality-lookback"]', self.js)
        self.assertIn('addEventListener("input",invalidate)', self.js)
        self.assertIn('setText("quality-state","Selection changed · run a new quality check")', self.js)
        self.assertIn("activeQualityController.abort()", self.js)

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
        scanner = self.js.split("function renderRows(target, rows, columns)", 1)[1].split("function syncAnalysisHeader()", 1)[0]
        self.assertIn("if(incomingRows!==view.rows){view.rows=incomingRows;view.page=0;view.sortedCache=null;", scanner)
        self.assertIn("scannerSearchTextCaches[target]=new WeakMap()", scanner)
        self.assertIn("if(aMissing!==bMissing)return aMissing?1:-1", scanner)
        self.assertIn("if((an!==null)!==(bn!==null))return an!==null?-1:1", scanner)
        self.assertIn("return cmp===0?0:cmp*direction", scanner)

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
        self.assertIn('menu.setAttribute("aria-expanded",String(Boolean(open&&mobile)))', self.js)
        self.assertIn('event.key==="Escape"', self.js)
        self.assertIn('if(!open&&mobile&&sidebar.contains(document.activeElement))menu.focus()', self.js)
        self.assertIn(".nav-link:focus-visible", self.css)

    def test_api_network_failures_are_distinguished_from_timeouts(self) -> None:
        self.assertIn('Request timed out.', self.js)
        self.assertIn('Network connection failed. Check your connection and backend availability.', self.js)
        self.assertIn('finally { window.clearTimeout(timer); externalSignal?.removeEventListener("abort",abortFromCaller); }', self.js)

    def test_scanner_sort_memoizes_numeric_keys_without_decorating_rows(self) -> None:
        self.assertIn("const scannerCollator = new Intl.Collator", self.js)
        self.assertIn("const numericCache=new WeakMap()", self.js)
        self.assertIn("const numericFor=item=>", self.js)
        self.assertIn("numericCache.set(item,numericValue(item?.[sortKey]))", self.js)
        self.assertIn("const an=numericFor(a),bn=numericFor(b)", self.js)
        self.assertNotIn("const sortable=filtered.map(item=>", self.js)
        self.assertNotIn("sortedRows=sortable.map(entry=>entry.item)", self.js)
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
        count_body = self.js.split("function extractCount", 1)[1].split("function metadataText", 1)[0]
        self.assertNotIn("Number.isFinite", count_body)


    def test_scanner_display_metadata_accepts_only_safe_primitives(self) -> None:
        self.assertIn('function metadataText(value,fallback="Not supplied",maxLength=160)', self.js)
        self.assertIn('textValue.length>maxLength?textValue.slice(0,maxLength-1)+"…":textValue', self.js)
        self.assertIn('metadataText(data.source,"Not supplied",120)', self.js)
        self.assertIn('metadataText(data.status,metadataText(data.scan_status,"Not supplied",80),80)', self.js)
        self.assertIn('typeof value==="string"&&value.trim()!==""', self.js)
        self.assertIn('typeof value==="number"&&Number.isFinite(value)', self.js)
        self.assertIn('return fallback;', self.js)
        self.assertIn('metadataText(data.status,metadataText(data.scan_status,"Returned",80),80)', self.js)
        self.assertIn('formatTimestamp(data.generated_at??data.timestamp??data.updated_at??"Not supplied")', self.js)
        self.assertIn('"Status: "+metadataText(data.status,metadataText(data.scan_status,"Not supplied",80),80)', self.js)

    def test_scanner_refresh_state_preserves_previous_results_on_failure(self) -> None:
        scan_body = self.js.split("async function scanMarket(market) {", 1)[1].split("function renderScannerMeta", 1)[0]
        self.assertIn('setText("scan-state","Refreshing · previous results retained")', scan_body)
        self.assertIn('setText("scan-state","Refresh failed · previous results retained")', scan_body)
        self.assertIn('setText("scan-state","Invalid response · previous results retained")', scan_body)
        self.assertLess(scan_body.index('setText("scan-state","Refreshing · previous results retained")'), scan_body.index("await api(path,{signal:controller.signal})"))
        self.assertLess(scan_body.index("await api(path,{signal:controller.signal})"), scan_body.index("renderScanSummary(data,market)"))

    def test_scanner_market_is_validated_before_request_state_changes(self) -> None:
        scan_body = self.js.split("async function scanMarket(market) {", 1)[1].split("function renderScannerMeta", 1)[0]
        validation = 'if(!["SPOT","USD_M","COIN_M"].includes(market))throw new Error("Unsupported scanner market selection.")'
        self.assertIn(validation, scan_body)
        self.assertLess(scan_body.index(validation), scan_body.index("invalidateScanRequests()"))

    def test_scanner_rejects_invalid_top_level_payload_before_rendering(self) -> None:
        validation = 'if(data===null||typeof data!=="object"||Array.isArray(data)){setText("scan-state","Invalid response · previous results retained");throw new Error("Scanner endpoint returned an invalid response shape.'
        scan_body = self.js.split("async function scanMarket(market) {", 1)[1].split("function renderScannerMeta", 1)[0]
        self.assertIn(validation, scan_body)
        self.assertIn("previous results were preserved.", scan_body)
        self.assertLess(scan_body.index(validation), scan_body.index("renderScanSummary(data,market)"))


    def test_scanner_rejects_non_object_response_rows_and_reports_count(self) -> None:
        self.assertIn('const rowKey=["symbols","markets","results","data"].find(key=>Array.isArray(data[key]))', self.js)
        self.assertIn("const responseRows=data[rowKey]", self.js)
        self.assertIn('responseRows.filter(item=>item!==null&&typeof item==="object"&&!Array.isArray(item))', self.js)
        self.assertIn("const rejectedRows=responseRows.length-rows.length", self.js)
        self.assertIn('"Rejected malformed rows: "+rejectedRows', self.js)
        self.assertIn("malformed rows were excluded", self.js)
        self.assertIn("if(responseRows.length>0&&rows.length===0)", self.js)


    def test_scanner_distinguishes_missing_result_array_from_empty_array(self) -> None:
        self.assertIn('const rowKey=["symbols","markets","results","data"].find(key=>Array.isArray(data[key]))', self.js)
        self.assertIn('if(rowKey===undefined)', self.js)
        self.assertIn('return{status:"INCOMPLETE_RESPONSE",market}', self.js)
        self.assertIn('const additionalRowKeys=["symbols","markets","results","data"].filter(key=>key!==rowKey&&Array.isArray(data[key]))', self.js)
        self.assertIn('"Additional array fields: "+(additionalRowKeys.length?additionalRowKeys.join(", "):"None")', self.js)
        self.assertIn("renderScannerMeta(market,data,rows,rejectedRows,rowKey,additionalRowKeys,quoteFilter)", self.js)
        scanner = self.js.split("async function scanMarket(market)", 1)[1].split("function scannerCountAliasConflicts", 1)[0]
        self.assertLess(scanner.index("if(rowKey===undefined)"), scanner.index("renderScanSummary(data,market)"))

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
        self.assertIn("view.query=e.target.value.trim().toUpperCase();view.page=0;", self.js)
        self.assertIn("scannerSearchText(target,item,keys).includes(view.query)", self.js)
        self.assertIn("cached.query===view.query", self.js)
        self.assertIn("view.sortedCache={rows:view.rows,query:view.query", self.js)

    def test_scanner_render_cancels_pending_debounce_before_immediate_render(self) -> None:
        scanner = self.js.split("function renderRows(target, rows, columns)", 1)[1].split("function syncAnalysisHeader()", 1)[0]
        self.assertIn("if(scannerSearchTimers[target]!==undefined){window.clearTimeout(scannerSearchTimers[target]);delete scannerSearchTimers[target];}", scanner)
        self.assertLess(scanner.index("window.clearTimeout(scannerSearchTimers[target])"), scanner.index("const body=$(target)"))
    def test_scanner_search_and_sort_caches_invalidate_together_on_new_response_rows(self) -> None:
        scanner = self.js.split("function renderRows(target, rows, columns)", 1)[1].split("function syncAnalysisHeader()", 1)[0]
        replacement = scanner.split("if(incomingRows!==view.rows){", 1)[1].split("}", 1)[0]
        self.assertIn("view.rows=incomingRows", replacement)
        self.assertIn("view.sortedCache=null", replacement)
        self.assertIn("scannerSearchTextCaches[target]=new WeakMap()", replacement)
        self.assertLess(replacement.index("view.rows=incomingRows"), replacement.index("view.sortedCache=null"))
        self.assertLess(replacement.index("view.sortedCache=null"), replacement.index("scannerSearchTextCaches[target]=new WeakMap()"))
    def test_scanner_search_text_is_weakly_cached_and_invalidated_with_rows(self) -> None:
        helper = self.js.split("function scannerSearchText", 1)[1].split("function scannerCellText", 1)[0]
        self.assertIn("const scannerSearchTextCaches = {}", self.js)
        self.assertIn("keys.map(key=>String(item?.[key]", helper)
        self.assertIn("if(!cache.has(item))", helper)
        self.assertIn("return cache.get(item)", helper)
        self.assertIn("scannerSearchTextCaches[target]=new WeakMap()", self.js)

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
        self.assertIn('if(requestSequence!==activeLoadSequence)return{status:"SUPERSEDED",market,symbol,requested_timeframe:tf}', self.chart_js)
        self.assertIn("chart invalidation actively aborts the in-flight API request", self.chart_test_js)

    def test_api_wrapper_composes_caller_cancellation_with_timeout(self) -> None:
        self.assertIn("signal:externalSignal", self.js)
        self.assertIn('externalSignal?.addEventListener("abort",abortFromCaller', self.js)
        self.assertIn('timedOut?"Request timed out.":externalSignal?.aborted?"Request cancelled.":"Request aborted."', self.js)
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
        self.assertLess(health_body.index('setText("health-status","Checking backend health · previous status retained")'), health_body.index('await api("/health",{signal:controller.signal})'))
        self.assertIn('setText("health-status","Unavailable")', health_body)

    def test_quality_refresh_and_spot_quote_change_explain_retained_results(self) -> None:
        quality_body = self.js.split("async function loadQuality() {", 1)[1].split("function connectSettings()", 1)[0]
        self.assertIn('" · previous report retained"', quality_body)
        quote_handler = self.js.split('$("spot-quote").addEventListener', 1)[1].split('[["spot-search"', 1)[0]
        self.assertIn('setText("scan-state","Spot quote filter changed · previous results retained; run a new scan")', quote_handler)
        self.assertIn("invalidateScanRequests()", quote_handler)

    def test_backend_credential_changes_abort_pending_analysis_requests(self) -> None:
        connect_body = self.js.split("function connectSettings() {", 1)[1].split("function bind()", 1)[0]
        clear_body = self.js.split('$("#clear-credentials")', 1)[-1] if '$("#clear-credentials")' in self.js else self.js.split('$("clear-credentials").addEventListener', 1)[1].split('$("default-market")', 1)[0]
        self.assertIn("cancelAnalysisRequests()", connect_body)
        self.assertIn("cancelAnalysisRequests()", clear_body)
        self.assertIn("if(activeMarketEvidenceController){activeMarketEvidenceController.abort();activeMarketEvidenceController=null;}", self.js)

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
        self.assertIn('setText("chart-state","Loading market evidence · previous chart and evidence retained")', evidence_body)
        self.assertIn('window.DashboardCharts.invalidate();', evidence_body)
        self.assertNotIn('invalidateChartView("Market evidence endpoint does not provide candle chart data.")', evidence_body)
        self.assertLess(evidence_body.index("await api(path,{signal:controller.signal})"), evidence_body.index('showJson("analysis-output",data)'))
        self.assertIn('showJson("analysis-output",data)', evidence_body)


    def test_market_evidence_failure_keeps_previous_payload_and_shows_bounded_error(self) -> None:
        self.assertIn('setText("chart-state","Evidence request failed · previous chart and evidence retained")', self.js)
        self.assertIn('setText("technical-summary","Request failed: "+metadataText(error?.message,"Unknown error",160))', self.js)
        self.assertIn('if(requestSequence!==activeEvidenceSequence)return{status:"SUPERSEDED"};setText("chart-state"', self.js)

    def test_quality_failure_keeps_previous_report_and_shows_bounded_error(self) -> None:
        self.assertIn('setText("quality-state","Load failed · previous report retained · "+metadataText(error?.message,"Unknown error",120))', self.js)
        self.assertIn('if(requestSequence!==activeQualitySequence)return{status:"SUPERSEDED"};setText("quality-state"', self.js)

    def test_health_connection_error_label_is_length_bounded(self) -> None:
        self.assertIn('setConnection(false,"Backend unavailable: "+metadataText(error?.message,"Request failed",160))', self.js)




    def test_backend_credential_changes_clear_all_connection_scoped_dashboard_data(self) -> None:
        clear_body = self.js.split("function clearConnectionScopedData(", 1)[1].split("function refreshDisplayedTimestamps()", 1)[0]
        for token in (
            "state.lastScan=null",
            "state.lastScanDetails=null",
            "state.lastHealth=null",
            "state.lastAnalysis=null",
            'setText("readiness-output",reason)',
            'setText("quality-output",reason)',
            'setText("analysis-output",reason)',
            'setText("technical-summary",reason)',
            "view.rows=[]",
            "renderRows(target,[],columns)",
            'chartHost.replaceChildren(document.createTextNode(reason))',
        ):
            self.assertIn(token, clear_body)
        connect_body = self.js.split("function connectSettings()", 1)[1].split("function bind()", 1)[0]
        self.assertIn('clearConnectionScopedData("Connection settings changed · previous backend data cleared")', connect_body)
        clear_handler = self.js.split('$("clear-credentials").addEventListener', 1)[1].split('$("default-market")', 1)[0]
        self.assertIn('clearConnectionScopedData("Backend credentials cleared · previous backend data removed")', clear_handler)

    def test_display_timezone_is_applied_to_cached_scan_timestamps(self) -> None:
        self.assertIn('timeZone:state.displayTimezone', self.js)
        self.assertIn("function scanTimestamp(data)", self.js)
        self.assertIn('["Updated",scanTimestamp(data)]', self.js)
        self.assertIn('setText("overview-updated",scanTimestamp(data))', self.js)
        self.assertIn('$("display-timezone").addEventListener("change"', self.js)
        refresh_body = self.js.split("function refreshDisplayedTimestamps()", 1)[1].split("function connectSettings()", 1)[0]
        self.assertIn("renderScanSummary(cached?.data??state.lastScan,cached?.market??state.market)", refresh_body)
        self.assertIn("renderScannerMeta(cached.market,cached.data,cached.rows,cached.rejectedRows,cached.rowKey,cached.additionalRowKeys,cached.quoteFilter)", refresh_body)

    def test_display_preferences_initialize_dashboard_market_and_timeframe(self) -> None:
        prefs = self.js.split("function applyDisplayPreferences()", 1)[1].split("function invalidateQualityRequest()", 1)[0]
        self.assertIn('state.displayTimezone=$("display-timezone").value', prefs)
        self.assertIn('state.market=$("default-market").value', prefs)
        self.assertIn('state.timeframe=$("default-timeframe").value', prefs)
        self.assertIn('$("global-market").value=state.market', prefs)
        self.assertIn('$("global-timeframe").value=state.timeframe', prefs)
        self.assertIn('b.dataset.market===state.market', prefs)
        self.assertIn('b.textContent===state.timeframe', prefs)
        self.assertIn("initTimeframes();applyDisplayPreferences();bind();", self.js)
        self.assertIn('$("default-market").addEventListener("change"', self.js)
        self.assertIn('$("default-timeframe").addEventListener("change"', self.js)



    def test_readiness_requests_are_aborted_and_ignored_after_backend_reconfiguration(self) -> None:
        readiness = self.js.split("async function loadReadiness(path)", 1)[1].split("function clearConnectionScopedData", 1)[0]
        self.assertIn("const requestSequence=++activeReadinessSequence", readiness)
        self.assertIn("activeReadinessController.abort()", readiness)
        self.assertIn("api(path,{signal:controller.signal})", readiness)
        self.assertIn('if(requestSequence!==activeReadinessSequence)return{status:"SUPERSEDED"}', readiness)
        connect_body = self.js.split("function connectSettings()", 1)[1].split("function bind()", 1)[0]
        self.assertIn("invalidateReadinessRequests()", connect_body)
        clear_handler = self.js.split('$("clear-credentials").addEventListener', 1)[1].split('$("display-timezone")', 1)[0]
        self.assertIn("invalidateReadinessRequests()", clear_handler)
        self.assertIn('()=>loadReadiness("/api/v1/research/preflight")', self.js)
        self.assertIn('()=>loadReadiness("/api/v1/research/phase-readiness")', self.js)



    def test_scanner_requests_are_aborted_when_superseded_or_credentials_change(self) -> None:
        self.assertIn("let activeScanController=null", self.js)
        invalidate = self.js.split("function invalidateScanRequests()", 1)[1].split("async function scanMarket", 1)[0]
        self.assertIn("activeScanSequence++", invalidate)
        self.assertIn("activeScanController.abort()", invalidate)
        scan = self.js.split("async function scanMarket(market)", 1)[1].split("function scannerCountAliasConflicts", 1)[0]
        self.assertIn("const controller=new AbortController()", scan)
        self.assertIn("api(path,{signal:controller.signal})", scan)
        self.assertIn("if(activeScanController===controller)activeScanController=null", scan)
        self.assertIn("invalidateScanRequests()", self.js.split("function connectSettings()", 1)[1].split("function bind()", 1)[0])

    def test_quality_requests_are_aborted_when_superseded_or_credentials_change(self) -> None:
        self.assertIn("let activeQualityController=null", self.js)
        invalidate = self.js.split("function invalidateQualityRequest()", 1)[1].split("async function loadQuality()", 1)[0]
        self.assertIn("activeQualitySequence++", invalidate)
        self.assertIn("activeQualityController.abort()", invalidate)
        quality = self.js.split("async function loadQuality()", 1)[1].split("function invalidateReadinessRequests()", 1)[0]
        self.assertIn("const controller=new AbortController()", quality)
        self.assertIn("{signal:controller.signal}", quality)
        self.assertIn("if(activeQualityController===controller)activeQualityController=null", quality)
        self.assertIn("invalidateQualityRequest()", self.js.split("function connectSettings()", 1)[1].split("function bind()", 1)[0])



    def test_api_timeout_and_caller_cancellation_are_classified_by_abort_cause(self) -> None:
        api = self.js.split("async function api(", 1)[1].split("async function withButton", 1)[0]
        self.assertIn("let timedOut=false", api)
        self.assertIn("timedOut=true;controller.abort()", api)
        self.assertIn('timedOut?"Request timed out.":externalSignal?.aborted?"Request cancelled.":"Request aborted."', api)
        self.assertIn('finally { window.clearTimeout(timer); externalSignal?.removeEventListener("abort",abortFromCaller); }', api)

    def test_health_requests_are_aborted_when_superseded_or_credentials_change(self) -> None:
        self.assertIn("let activeHealthController=null", self.js)
        invalidate = self.js.split("function invalidateHealthRequests()", 1)[1].split("async function loadHealth()", 1)[0]
        self.assertIn("activeHealthSequence++", invalidate)
        self.assertIn("activeHealthController.abort()", invalidate)
        health = self.js.split("async function loadHealth()", 1)[1].split("function invalidateScanRequests()", 1)[0]
        self.assertIn("api(\"/health\",{signal:controller.signal})", health)
        self.assertIn("if(activeHealthController===controller)activeHealthController=null", health)
        connect_body = self.js.split("function connectSettings()", 1)[1].split("function bind()", 1)[0]
        self.assertIn("invalidateHealthRequests()", connect_body)
        clear_handler = self.js.split('$(\"clear-credentials\").addEventListener', 1)[1].split('$(\"display-timezone\")', 1)[0]
        self.assertIn("invalidateHealthRequests()", clear_handler)


    def test_compact_viewport_layout_and_focus_styles_cover_controls(self) -> None:
        self.assertIn(".filter-row>*{min-width:0}", self.css)
        self.assertIn(".filter-row>label input,", self.css)
        self.assertIn(".filter-row>label select{width:100%;min-width:0}", self.css)
        self.assertIn("@media(max-width:360px)", self.css)
        self.assertIn(".table-pager button:focus-visible", self.css)
        self.assertIn(".text-btn:focus-visible", self.css)
        self.assertIn('role="region" aria-label="Spot market scan results" tabindex="0"', self.html)

    def test_market_evidence_preserves_previous_chart_until_valid_response(self) -> None:
        evidence = self.js.split("async function loadMarketEvidence()", 1)[1].split("async function loadTechnical()", 1)[0]
        self.assertIn('setText("chart-state","Loading market evidence · previous chart and evidence retained")', evidence)
        self.assertNotIn('setText("technical-summary","Loading evidence for the current selection.")', evidence)
        self.assertIn('if(data===null||typeof data!=="object"||Array.isArray(data))', evidence)
        self.assertIn('previous evidence was preserved.', evidence)
        self.assertLess(evidence.index('if(data===null||typeof data!=="object"||Array.isArray(data))'), evidence.index('chartHost.replaceChildren'))
        self.assertIn('Evidence request failed · previous chart and evidence retained', evidence)

    def test_incomplete_scanner_response_preserves_previous_rows_and_coverage(self) -> None:
        scanner = self.js.split("async function scanMarket(market)", 1)[1].split("function scannerCountAliasConflicts", 1)[0]
        incomplete = scanner.split("if(rowKey===undefined)", 1)[1].split("const additionalRowKeys", 1)[0]
        self.assertIn("previous results and coverage retained", incomplete)
        self.assertIn('return{status:"INCOMPLETE_RESPONSE",market}', incomplete)
        self.assertNotIn("renderRows(", incomplete)
        self.assertNotIn("renderScannerMeta(", incomplete)
        self.assertLess(scanner.index("if(rowKey===undefined)"), scanner.index("renderScanSummary(data,market)"))

    def test_scanner_rejects_all_malformed_rows_without_replacing_previous_results(self) -> None:
        scanner = self.js.split("async function scanMarket(market)", 1)[1].split("function scannerCountAliasConflicts", 1)[0]
        malformed = scanner.split("if(responseRows.length>0&&rows.length===0)", 1)[1].split("renderScanSummary(data)", 1)[0]
        self.assertIn("previous results and coverage were preserved", malformed)
        self.assertLess(scanner.index("if(responseRows.length>0&&rows.length===0)"), scanner.index("renderScanSummary(data,market)"))
        self.assertIn('Requested quote filter:', self.js.split("function renderScannerMeta", 1)[1].split("const details=", 1)[1].split("];", 1)[0])

    def test_scanner_market_and_quote_filter_provenance_survive_timezone_refresh(self) -> None:
        summary = self.js.split("function renderScanSummary(data,market=state.market)", 1)[1].split("function invalidateHealthRequests", 1)[0]
        self.assertIn('["Market",market]', summary)
        scan = self.js.split("async function scanMarket(market)", 1)[1].split("function scannerCountAliasConflicts", 1)[0]
        self.assertIn("let path,quoteFilter=null", scan)
        self.assertIn("state.lastScanDetails={market,data,rows,rejectedRows,rowKey,additionalRowKeys,quoteFilter}", scan)
        self.assertIn("renderScannerMeta(market,data,rows,rejectedRows,rowKey,additionalRowKeys,quoteFilter)", scan)
        meta = self.js.split("function renderScannerMeta", 1)[1].split("const tableViews", 1)[0]
        self.assertIn('metadataText(quoteFilter,"All quote assets",40)', meta)
        refresh = self.js.split("function refreshDisplayedTimestamps()", 1)[1].split("function connectSettings()", 1)[0]
        self.assertIn("renderScanSummary(cached?.data??state.lastScan,cached?.market??state.market)", refresh)
        self.assertIn("cached.additionalRowKeys,cached.quoteFilter", refresh)

    def test_scanner_invalid_numeric_values_remain_after_numeric_values_in_both_sort_directions(self) -> None:
        scanner = self.js.split("function renderRows(target, rows, columns)", 1)[1].split("function syncAnalysisHeader()", 1)[0]
        comparator = scanner.split("sortedRows.sort((a,b)=>", 1)[1].split("});", 1)[0]
        self.assertIn("if(aMissing!==bMissing)return aMissing?1:-1", comparator)
        self.assertIn("if((an!==null)!==(bn!==null))return an!==null?-1:1", comparator)
        self.assertLess(comparator.index("if((an!==null)!==(bn!==null))"), comparator.index("return cmp===0?0:cmp*direction"))
        self.assertIn("return cmp===0?0:cmp*direction", comparator)


    def test_scanner_reports_duplicate_symbols_without_dropping_rows(self) -> None:
        helper = self.js.split("function scannerDuplicateSymbolStats(rows)", 1)[1].split("function renderScannerMeta", 1)[0]
        self.assertIn('row?.symbol==="string"?row.symbol.trim().toUpperCase():""', helper)
        self.assertIn("counts.set(symbol,(counts.get(symbol)||0)+1)", helper)
        self.assertIn("duplicateRows+=count-1", helper)
        self.assertIn("const duplicateStats=scannerDuplicateSymbolStats(rows)", self.js)
        meta = self.js.split("function renderScannerMeta", 1)[1].split("const tableViews", 1)[0]
        self.assertIn('"Unique symbols: "+duplicateStats.uniqueSymbols', meta)
        self.assertIn('"Duplicate symbols: "+duplicateStats.duplicateSymbols', meta)
        self.assertIn('"Duplicate rows: "+duplicateStats.duplicateRows', meta)
        scan = self.js.split("async function scanMarket(market)", 1)[1].split("function scannerDuplicateSymbolStats", 1)[0]
        self.assertIn("renderRows(\"spot-rows\",rows,6)", scan)
        self.assertIn("renderRows(\"usdm-rows\",rows,5)", scan)
        self.assertIn("renderRows(\"coinm-rows\",rows,5)", scan)
        self.assertNotIn("new Map(", scan)


    def test_scanner_cells_render_malformed_market_values_as_explicit_placeholders(self) -> None:
        helper = self.js.split("function scannerCellText(key,value)", 1)[1].split("function renderRows", 1)[0]
        self.assertIn('value===null||value===undefined||value===""', helper)
        self.assertIn('Number.isFinite(Number(value))', helper)
        self.assertIn('if(typeof value!=="number"&&typeof value!=="string")return"Invalid number"', helper)
        self.assertIn('"Invalid number"', helper)
        self.assertIn('"Invalid value"', helper)
        self.assertIn('["last_price","quote_volume_24h","price_change_percent_24h"]', helper)
        rows = self.js.split("function renderRows(target, rows, columns)", 1)[1].split("function syncAnalysisHeader()", 1)[0]
        self.assertIn("td.textContent=scannerCellText(key,item?.[key])", rows)
        self.assertNotIn("String(item[key])", rows)


    def test_scanner_table_rows_are_batched_in_a_document_fragment(self) -> None:
        rows = self.js.split("function renderRows(target, rows, columns)", 1)[1].split("function syncAnalysisHeader()", 1)[0]
        self.assertIn("const rowFragment=document.createDocumentFragment()", rows)
        self.assertIn("rowFragment.append(tr)", rows)
        self.assertIn("body.append(rowFragment)", rows)
        self.assertNotIn("body.append(tr)", rows)


    def test_scanner_search_and_sort_cache_only_row_references(self) -> None:
        rows = self.js.split("function renderRows(target, rows, columns)", 1)[1].split("function syncAnalysisHeader()", 1)[0]
        self.assertIn("view.rows=incomingRows", rows)
        self.assertNotIn("incomingRows.slice()", rows)
        self.assertIn("for(const item of view.rows)", rows)
        self.assertIn("scannerSearchText(target,item,keys).includes(view.query)", rows)
        self.assertIn("const scannerSearchTextCaches = {}", self.js)
        self.assertIn("scannerSearchTextCaches[target]=new WeakMap()", rows)
        self.assertIn("sortedRows.push(item)", rows)
        self.assertIn("sortedRows.sort((a,b)=>", rows)
        self.assertIn("view.sortedCache={rows:view.rows,query:view.query,sortKey,direction,filteredCount,sortedRows}", rows)
        self.assertIn("sortedRows.slice(view.page*view.pageSize", rows)
        self.assertNotIn("sortable.push({item", rows)
        self.assertNotIn("sortedEntries", rows)
        self.assertNotIn("view.rows.filter(", rows)

    def test_scanner_search_text_cache_is_invalidated_when_rows_change(self) -> None:
        helper = self.js.split("function scannerSearchText(", 1)[1].split("function scannerCellText", 1)[0]
        self.assertIn("new WeakMap()", helper)
        self.assertIn("cache.has(item)", helper)
        self.assertIn("cache.set(item,keys.map", helper)
        rows = self.js.split("function renderRows(target, rows, columns)", 1)[1].split("function syncAnalysisHeader()", 1)[0]
        invalidation = rows.split("if(incomingRows!==view.rows)", 1)[1].split("const cached=", 1)[0]
        self.assertIn("view.sortedCache=null", invalidation)
        self.assertIn("scannerSearchTextCaches[target]=new WeakMap()", invalidation)
        self.assertIn("scannerSearchText(target,item,keys).includes(view.query)", rows)

    def test_scanner_search_rendering_is_debounced_and_cancelled_on_clear(self) -> None:
        self.assertIn("const scannerSearchTimers = {}", self.js)
        self.assertIn("window.clearTimeout(scannerSearchTimers[target])", self.js)
        self.assertIn("window.setTimeout(()=>", self.js)
        self.assertIn("},150);", self.js)
        clear = self.js.split("function clearConnectionScopedData", 1)[1].split("function refreshDisplayedTimestamps", 1)[0]
        self.assertIn("delete scannerSearchTimers[target]", clear)

if __name__ == "__main__":
    unittest.main()
