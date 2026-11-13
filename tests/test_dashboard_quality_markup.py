from pathlib import Path


def test_quality_dashboard_has_controls_and_local_api_route():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    for identifier in (
        'id="qualityLookback"', 'id="qualityRun"', 'id="qualityStatus"',
        'id="qualitySummary"', 'id="qualitySources"', 'id="qualityCollectors"',
        'id="qualityRaw"',
    ):
        assert identifier in html
    assert "/api/v1/quality/market-data/" in html
    assert "lookback_hours" in html
    assert "NOT_MEASURABLE" in html


def test_quality_dashboard_escapes_remote_text_and_uses_existing_auth():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "const escapeHtml=" in html
    assert "escapeHtml(name.replaceAll" in html
    assert "escapeHtml(x.note)" in html
    assert "await call('/api/v1/quality/market-data/'" in html
    assert "localStorage" not in html


def test_dashboard_renders_collector_job_runtime_details_safely():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "const renderCollector=(name,x)=>" in html
    assert "job.connected===true?'CONNECTED'" in html
    assert "job.synchronized===false?' · NOT SYNCED'" in html
    assert "escapeHtml(label)" in html
    assert "escapeHtml(error)" in html


def test_dashboard_shows_collector_last_cycle_results_and_errors():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "const results=Array.isArray(x.last_results)?x.last_results:[]" in html
    assert "Last collection cycle:" in html
    assert "escapeHtml(result.error_type)" in html
    assert "CONNECTED:'status-good'" in html
    assert "DISCONNECTED:'status-warn'" in html

def test_dashboard_displays_actual_source_period_when_reported():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "x.period?'<p><b>Stored period:</b> '+escapeHtml(x.period)" in html

def test_dashboard_displays_future_clock_skew_separately_from_age():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "Future clock skew (ms):" in html
    assert "x.future_skew_ms??'—'" in html


def test_dashboard_displays_regime_bias_confidence_and_overlap_metrics():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "Market-regime × bias reliability" in html
    assert "x.positive_fraction_ci_95_wilson.lower" in html
    assert "x.sample_size_status" in html
    assert "x.non_overlapping_directional_sample_size" in html
    assert "x.overlap_excluded_count" in html
    assert "30-sample flag is a caution threshold" in html


def test_dashboard_displays_regime_bias_alignment_breakdown():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "market_regime" in html and "Market regime" in html
    assert "regime_bias_alignment_breakdown" in html
    assert "x.positive_fraction_ci_95_wilson.lower" in html
    assert "escapeHtml(alignment)" in html

def test_dashboard_displays_alignment_breakdowns_for_all_regime_dimensions():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "market_regime'" in html
    assert "volatility_regime'" in html
    assert "structure_regime'" in html
    assert "Volatility regime" in html
    assert "Structure regime" in html
    assert "(h.regime_bias_alignment_breakdown||{})[dimension]||{}" in html

def test_dashboard_displays_sample_gated_horizon_comparison_rankings():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "Seven-horizon comparative rankings" in html
    assert "horizon_comparison" in html
    assert "ranking.ranked" in html
    assert "ranking.excluded" in html
    assert "historical descriptive comparisons" in html

def test_dashboard_displays_historical_regime_performance_leaderboard():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "Historical performance leaderboard" in html
    assert "historical_leaderboard" in html
    assert "ranking.ranked" in html
    assert "ranking.excluded" in html
    assert "Groups are ranked within each horizon and regime dimension" in html


def test_dashboard_displays_subgroup_reliability_assessment_diagnostics():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "Evidence assessment" in html
    assert "Wilson CI width" in html
    assert "Overlap gap" in html
    assert "Coverage complete" in html
    assert "reliability_assessment" in html
    assert "reliability_summary" in html
    assert "not a predictive reliability score" in html


def test_dashboard_displays_walk_forward_fold_consistency():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "Fold consistency:" in html
    assert "consistency_assessment" in html
    assert "eligible_fold_count" in html
    assert "insufficient_fold_count" in html
    assert "folds_with_interval_including_50_percent" in html or "positive_fraction_range" in html


def test_dashboard_displays_historical_vs_walk_forward_comparison():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "Historical versus walk-forward comparison" in html
    assert "historical_vs_walk_forward" in html
    assert "positive_fraction_difference_percentage_points" in html
    assert "nominal_confidence_intervals_overlap" in html
    assert "not a formal significance test" in html


def test_dashboard_displays_data_quality_and_selection_risk_warnings():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "Data quality &amp; selection-risk warnings" in html or "Data quality & selection-risk warnings" in html
    assert "data_quality_risk_assessment" in html
    assert "overfitting_assessment" in html
    assert "INCOMPLETE_FUTURE_CANDLE_COVERAGE" not in html or "q.flags" in html
    assert "no multiple-comparison correction is applied" in html
    assert "do not estimate overfitting probability" in html


def test_dashboard_displays_signal_quality_confusion_matrix_and_regime_breakdown():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "Signal quality validation" in html
    assert "signal_quality" in html
    assert "signal_quality_by_regime" in html
    assert "Confusion matrix" in html
    assert "true_positive" in html
    assert "false_positive" in html
    assert "true_negative" in html
    assert "false_negative" in html
    assert "do not include periods with no call" in html


def test_dashboard_displays_purged_holdout_and_regime_stability_tables():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "training_purged_overlap_count" in html
    assert "Holdout regime stability" in html
    assert "test_regime_stability" in html
    assert "coverage_complete_fraction" in html
    assert "Regime groups are based only on labels saved at signal time" in html


def test_dashboard_displays_chronological_regime_degradation_screen():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "Chronological degradation screen" in html
    assert "regime_transition_degradation" in html
    assert "degradation screen" in html
    assert "positive_fraction_change_percentage_points" in html
    assert "not a significance test" in html


def test_dashboard_displays_observed_regime_transitions_and_manual_adaptation_status():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "Observed regime transitions" in html
    assert "regime_transition_analysis" in html
    assert "signal_adaptation_status" in html
    assert "Pre-transition outcomes closing at or after the change are excluded" in html


def test_dashboard_sanitizes_all_api_derived_html_render_targets():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    for target in (
        "metrics", "evidence", "snapshots", "snapshotSelect", "pricePath",
        "qualitySummary", "qualitySources", "qualityCollectors", "outcomes",
    ):
        assert f"$('" + target + "').innerHTML=sanitizeHtml(" in html
    assert "const sanitizeHtml=markup=>" in html
    assert "document.createElement('template')" in html
    assert "const tags=new Set(" in html
    assert "const attrs=new Set(" in html
    assert "const styleProps=new Set(" in html
    assert "el.removeAttribute(attr.name)" in html
    assert "el.remove()" in html


def test_dashboard_sanitizer_does_not_allow_scriptable_elements_or_event_attributes():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    sanitizer = html.split("const sanitizeHtml=markup=>", 1)[1].split("\nconst renderCollector", 1)[0]
    assert "'script'" not in sanitizer
    assert "'iframe'" not in sanitizer
    assert "'img'" not in sanitizer
    assert "'onerror'" not in sanitizer
    assert "'onclick'" not in sanitizer
    assert "'href'" not in sanitizer
    assert "return template.innerHTML" in sanitizer


def test_dashboard_requires_https_for_remote_api_urls():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "parsed=new URL(raw)" in html
    assert "const host=parsed.hostname.toLowerCase()" in html
    assert "parsed.protocol!=='https:'&&!loopback" in html
    assert "host==='localhost'||host==='127.0.0.1'||host==='[::1]'" in html
    assert "authority.includes('@')||parsed.username||parsed.password||parsed.search||parsed.hash||raw.includes('?')||raw.includes('#')" in html
    assert "HTTPS is required for remote backend URLs" in html


def test_dashboard_backend_url_policy_executes_in_javascript_runtime():
    import subprocess
    import textwrap

    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    harness = textwrap.dedent(r"""
        const assert = require("node:assert/strict");
        const vm = require("node:vm");
        let source = "";
        process.stdin.setEncoding("utf8");
        process.stdin.on("data", chunk => source += chunk);
        process.stdin.on("end", () => {
          const match = source.match(/<script>([\s\S]*?)<\/script>/i);
          assert.ok(match, "dashboard script must exist");
          const elements = new Map();
          const document = {
            getElementById(id) {
              if (!elements.has(id)) elements.set(id, { value: "", innerHTML: "", textContent: "", onclick: null });
              return elements.get(id);
            }
          };
          const window = { location: { origin: "https://dashboard.example" } };
          const context = { document, window, URL, fetch: async () => { throw new Error("unexpected fetch"); } };
          vm.runInNewContext(match[1] + "\nglobalThis.__apiForTest = api;", context);
          const base = document.getElementById("base");
          const api = context.__apiForTest;
          const accepted = [
            ["", "https://dashboard.example"],
            ["https://api.example/v1", "https://api.example/v1"],
            ["HTTPS://API.EXAMPLE", "https://api.example"],
            ["https://api.example/@user", "https://api.example/@user"],
            ["http://localhost:8000", "http://localhost:8000"],
            ["http://127.0.0.1:8000", "http://127.0.0.1:8000"],
            ["http://127.1:8000", "http://127.0.0.1:8000"],
            ["http://[::1]:8000", "http://[::1]:8000"]
          ];
          for (const [input, expected] of accepted) {
            base.value = input;
            assert.equal(api(), expected, "expected URL to be accepted: " + input);
          }
          const rejected = [
            ["http://api.example", /HTTPS is required/],
            ["ftp://api.example", /must be HTTP\(S\)/],
            ["https://user:pass@api.example", /without credentials/],
            ["https://@api.example", /without credentials/],
            ["https://:@api.example", /without credentials/],
            ["https://api.example/path?token=x", /without credentials/],
            ["https://api.example/path?", /without credentials/],
            ["https://api.example/path#fragment", /without credentials/],
            ["https://api.example/path#", /without credentials/],
            ["not a URL", /absolute HTTP\(S\) URL/]
          ];
          for (const [input, error] of rejected) {
            base.value = input;
            assert.throws(() => api(), error, "expected URL to be rejected: " + input);
          }
        });
    """)
    result = subprocess.run(
        ["node", "-e", harness],
        input=html,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_dashboard_sanitizer_restricts_svg_paint_values():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    sanitizer = html.split("const sanitizeHtml=markup=>", 1)[1].split("\nconst renderCollector", 1)[0]
    assert "const paintAttrs=new Set(['fill','stroke'])" in sanitizer
    assert "paintAttrs.has(name)" in sanitizer
    assert "currentcolor|transparent" in sanitizer
    assert "url(" not in sanitizer


def test_dashboard_escapes_api_derived_text_before_allowlist_sanitization():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    for snippet in (
        "escapeHtml(x[1]??'—')",
        "escapeHtml(x.source)",
        "escapeHtml(x.direction||'NO DIRECTION')",
        "escapeHtml(x.status)",
        "escapeHtml(JSON.stringify(x.detail||{},null,2))",
        "escapeHtml(JSON.stringify(r,null,2))",
        "escapeHtml(x.snapshot_id)",
        "escapeHtml(x.bias)",
        "escapeHtml(r.symbol)",
        "escapeHtml(r.bias_vs_actual)",
        "escapeHtml(values[0])",
        "escapeHtml(values[values.length-1])",
        "escapeHtml(referencePrice)",
        "escapeHtml(h.label)",
    ):
        assert snippet in html
    assert "$('qualityRaw').textContent=JSON.stringify(r,null,2)" in html


def test_dashboard_escape_html_helper_runs_in_node_runtime():
    import subprocess
    import textwrap

    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    harness = textwrap.dedent(r"""
        const assert = require("node:assert/strict");
        const vm = require("node:vm");
        let source = "";
        process.stdin.setEncoding("utf8");
        process.stdin.on("data", chunk => source += chunk);
        process.stdin.on("end", () => {
          const match = source.match(/<script>([\s\S]*?)<\/script>/i);
          assert.ok(match, "dashboard inline script missing");
          const document = {
            getElementById() {
              return { value: "", innerHTML: "", textContent: "", onclick: null };
            }
          };
          const context = {
            document,
            window: { location: { origin: "https://dashboard.example" } },
            URL,
            URLSearchParams,
            fetch: async () => { throw new Error("unexpected fetch"); }
          };
          vm.runInNewContext(
            match[1] + "\nglobalThis.__escapeHtmlForTest = escapeHtml;",
            context
          );
          assert.equal(
            context.__escapeHtmlForTest(["<div class=", String.fromCharCode(34), "x", String.fromCharCode(34), ">&'", "</div>"].join("")),
            "&lt;div class=&quot;x&quot;&gt;&amp;&#39;&lt;/div&gt;"
          );
        });
    """)
    result = subprocess.run(
        ["node", "-e", harness],
        input=html,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr

def test_dashboard_performance_api_output_is_sanitized_before_rendering():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    performance_handler = next(
        line for line in html.splitlines() if "$('performance').onclick" in line
    )
    assert "$('outcomes').innerHTML=sanitizeHtml(" in performance_handler
    assert "+'</pre>')}catch(e){fail(e)}};" in performance_handler



def test_dashboard_performance_handler_renders_minimal_holdout_horizon_in_runtime():
    import subprocess
    import textwrap

    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    harness = textwrap.dedent(r"""
        const assert = require("node:assert/strict");
        const vm = require("node:vm");
        let source = "";
        process.stdin.setEncoding("utf8");
        process.stdin.on("data", chunk => source += chunk);
        process.stdin.on("end", () => {
          (async () => {
            const scriptStart = source.indexOf("<script>");
            const scriptEnd = source.lastIndexOf("</script>");
            assert.ok(scriptStart >= 0 && scriptEnd > scriptStart, "dashboard inline script missing");
            const script = source.slice(scriptStart + 8, scriptEnd);
            const elements = new Map();
            const document = {
              getElementById(id) {
                if (!elements.has(id)) elements.set(id, {
                  value: "", innerHTML: "", textContent: "", onclick: null
                });
                return elements.get(id);
              },
              createElement(name) {
                assert.equal(name, "template");
                let markup = "";
                return {
                  content: { children: [] },
                  set innerHTML(value) { markup = value; },
                  get innerHTML() { return markup; }
                };
              }
            };
            let fetchCalls = 0;
            const fetch = async () => {
              fetchCalls += 1;
              return {
              ok: true,
              status: 200,
              json: async () => ({ horizons: { one_hour: { label: "1h", out_of_sample: {} } } })
              };
            };
            const context = {
              document,
              window: { location: { origin: "https://dashboard.example" } },
              URL,
              URLSearchParams,
              fetch
            };
            vm.runInNewContext(script, context);
            document.getElementById("key").value = "test-api-key";
            await document.getElementById("performance").onclick();
            assert.equal(fetchCalls, 1, "performance handler should request the API response");
            assert.equal(
              document.getElementById("status").textContent.startsWith("Error:"),
              false,
              "performance rendering should not report a runtime error: " + document.getElementById("status").textContent
            );
          })().catch(error => { console.error(error); process.exitCode = 1; });
        });
    """)
    result = subprocess.run(
        ["node", "-e", harness],
        input=html,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_dashboard_performance_optional_metrics_handle_undefined_values():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    performance_handler = next(
        line for line in html.splitlines() if "$('performance').onclick" in line
    )
    # API JSON may omit optional fields entirely; null-only checks do not cover
    # JavaScript undefined and can still call toFixed() on a missing value.
    assert "===null" not in performance_handler

def test_dashboard_price_path_validates_api_candle_payload_before_chart_rendering():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    price_path_handler = next(
        line for line in html.splitlines() if "$('loadPath').onclick" in line
    )
    assert "Array.isArray(r.candles)" in price_path_handler
    assert "Number.isFinite(referencePrice)" in price_path_handler
    assert "Number.isFinite(actualChange)" in price_path_handler
    assert "values.some(v=>!Number.isFinite(v))" in price_path_handler
    assert "r.bias_aligned_change_percent==null?" in price_path_handler
    assert "invalid price-path payload" in price_path_handler


def test_dashboard_performance_handles_incomplete_wilson_interval_payload():
    import subprocess
    import textwrap

    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    harness = textwrap.dedent(r"""
        const assert = require("node:assert/strict");
        const vm = require("node:vm");
        let source = "";
        process.stdin.setEncoding("utf8");
        process.stdin.on("data", chunk => source += chunk);
        process.stdin.on("end", () => {
          (async () => {
            const start = source.indexOf("<script>");
            const end = source.lastIndexOf("</script>");
            const elements = new Map();
            const document = {
              getElementById(id) {
                if (!elements.has(id)) elements.set(id, {
                  value: "", innerHTML: "", textContent: "", onclick: null
                });
                return elements.get(id);
              },
              createElement(name) {
                assert.equal(name, "template");
                let markup = "";
                return {
                  content: { children: [] },
                  set innerHTML(value) { markup = value; },
                  get innerHTML() { return markup; }
                };
              }
            };
            const payload = {
              horizons: { one_hour: { label: "<img src=x onerror=alert(1)>", directional_positive_fraction: "invalid", mean_directional_return_percent: "invalid", mean_favorable_excursion_percent: "invalid", mean_adverse_excursion_percent: "invalid", signal_quality: { f1_score: "invalid", coverage_complete_fraction: "invalid", overlap_excluded_fraction_of_directional: "invalid", confusion_matrix: { true_positive: "<img src=x onerror=alert(2)>" } } } },
              historical_leaderboard: {
                dimensions: {
                  market_regime: {
                    one_hour: {
                      horizon: "1h",
                      reliability_summary: {},
                      rankings: {
                        positive_fraction: {
                          label: "Positive fraction",
                          minimum_sample_size: 1,
                          ranked: [{
                            rank: 1, regime: "TREND", bias: "BULLISH",
                            alignment: "ALIGNED", sample_size: 1, value: "invalid",
                            confidence_interval_95_wilson: { lower: "invalid", upper: "invalid" },
                            mean_directional_return_percent: "invalid",
                            non_overlapping_directional_sample_size: 1,
                            reliability_assessment: {}
                          }],
                          excluded: []
                        }
                      }
                    }
                  }
                }
              }
            };
            const context = {
              document,
              window: { location: { origin: "https://dashboard.example" } },
              URL, URLSearchParams,
              fetch: async () => ({ ok: true, status: 200, json: async () => payload })
            };
            vm.runInNewContext(source.slice(start + 8, end), context);
            document.getElementById("key").value = "test-api-key";
            await document.getElementById("performance").onclick();
            assert.equal(
              document.getElementById("status").textContent.startsWith("Error:"),
              false,
              "incomplete Wilson interval must render as unavailable, not crash: " +
                document.getElementById("status").textContent
            );
            assert.equal(
              document.getElementById("outcomes").innerHTML.includes("NaN%"),
              false,
              "malformed horizon percentages must render as unavailable"
            );
            assert.equal(
              document.getElementById("outcomes").innerHTML.includes("&lt;img src=x onerror=alert(2)&gt;"),
              true,
              "API-provided confusion-matrix counts must be HTML-escaped"
            );
            assert.equal(
              document.getElementById("outcomes").innerHTML.includes("&lt;img src=x onerror=alert(1)&gt;"),
              true,
              "API-provided horizon labels must be HTML-escaped"
            );
          })().catch(error => { console.error(error); process.exitCode = 1; });
        });
    """)
    result = subprocess.run(
        ["node", "-e", harness],
        input=html,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_dashboard_performance_leaderboard_validates_and_escapes_api_values():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    performance_handler = next(
        line for line in html.splitlines() if "$('performance').onclick" in line
    )
    assert "Number.isFinite(row.value)?(percentage?" in performance_handler
    assert "escapeHtml(row.rank)" in performance_handler
    assert performance_handler.count("escapeHtml(row.sample_size)") == 2
    assert "escapeHtml(row.non_overlapping_directional_sample_size)" in performance_handler

def test_dashboard_performance_percent_formatter_rejects_non_numeric_api_values():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    performance_handler = next(
        line for line in html.splitlines() if "$('performance').onclick" in line
    )
    assert "const pct=v=>typeof v!=='number'||!Number.isFinite(v)?'—':(v*100).toFixed(1)+'%';" in performance_handler
    assert "pct(q.f1_score)" in performance_handler
    assert "(q.f1_score*100).toFixed(1)" not in performance_handler
    assert "const pct=v=>v==null||v===undefined?'—':(v*100).toFixed(1)+'%';" not in performance_handler
    for expression in (
        "escapeHtml(h.sample_size)",
        "escapeHtml(ranking.minimum_sample_size)",
        "escapeHtml(w.initial_training_snapshot_count??0)",
        "escapeHtml(x.training_snapshot_count??0)",
    ):
        assert expression in performance_handler


def test_dashboard_performance_count_metrics_are_html_escaped():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    performance_handler = next(
        line for line in html.splitlines() if "$('performance').onclick" in line
    )
    expressions = (
        "h.coverage_complete_count??0", "h.sample_size??0",
        "q.prediction_sample_size??0", "q.scored_non_flat_sample_size??0",
        "q.flat_outcome_count??0", "cm.true_positive??0", "cm.false_positive??0",
        "cm.true_negative??0", "cm.false_negative??0", "g.prediction_sample_size??0",
        "x.true_positive??0", "x.false_positive??0", "x.true_negative??0",
        "x.false_negative??0", "q.total_outcome_count??0", "q.directional_sample_size??0",
        "q.overlap_excluded_count??0", "c.historical_directional_sample_size??0",
        "c.walk_forward_test_directional_sample_size??0",
        "w.non_overlapping_directional_sample_size??0", "w.overlap_excluded_count??0",
        "x.non_overlapping_directional_sample_size??0", "x.overlap_excluded_count??0",
        "x.training_purged_overlap_count??0", "g.sample_size??0",
        "g.directional_sample_size??0", "g.coverage_complete_count??0",
        "d.transition_count??0", "x.non_overlapping_directional_sample_size",
        "x.overlap_excluded_count", "x.coverage_complete_count", "x.sample_size",
        "x.directional_sample_size", "x.positive_count??0",
    )
    for expression in expressions:
        assert f"escapeHtml({expression})" in performance_handler
        assert f"+({expression})+" not in performance_handler
        assert f"+{expression}+" not in performance_handler


def test_dashboard_performance_fraction_metrics_use_strict_percentage_formatter():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    performance_handler = next(
        line for line in html.splitlines() if "$('performance').onclick" in line
    )
    expressions = (
        "h.directional_positive_fraction",
        "row.reliability_assessment.coverage_complete_fraction",
        "q.coverage_complete_fraction",
        "q.overlap_excluded_fraction_of_directional",
        "c.historical_positive_fraction", "c.walk_forward_positive_fraction",
        "w.test_directional_positive_fraction", "w.non_overlapping_positive_fraction",
        "f.test_directional_positive_fraction", "x.test_directional_positive_fraction",
        "x.non_overlapping_positive_fraction", "g.positive_fraction",
        "g.coverage_complete_fraction", "x.positive_fraction",
    )
    for expression in expressions:
        assert f"pct({expression})" in performance_handler
        assert f"({expression}*100).toFixed(1)+'%'" not in performance_handler


def test_dashboard_performance_confidence_intervals_and_regime_fractions_are_finite_checked():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    performance_handler = next(
        line for line in html.splitlines() if "$('performance').onclick" in line
    )
    assert "const ciPct=ci=>!ci||!Number.isFinite(ci.lower)||!Number.isFinite(ci.upper)?'—':pct(ci.lower)+'–'+pct(ci.upper);" in performance_handler
    for expression in (
        "w.test_directional_positive_fraction_ci_95_wilson",
        "f.test_directional_positive_fraction_ci_95_wilson",
        "x.test_directional_positive_fraction_ci_95_wilson",
        "g.positive_fraction_ci_95_wilson",
        "x.positive_fraction_ci_95_wilson",
    ):
        assert f"ciPct({expression})" in performance_handler
    for expression in (
        "(g.early||{}).positive_fraction", "(g.late||{}).positive_fraction",
        "(t.pre_transition||{}).positive_fraction",
        "(t.post_transition||{}).positive_fraction",
    ):
        assert f"pct({expression})" in performance_handler


def test_dashboard_performance_remaining_interval_and_pp_metrics_are_finite_checked():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    performance_handler = next(
        line for line in html.splitlines() if "$('performance').onclick" in line
    )
    assert "const pp=v=>typeof v!=='number'||!Number.isFinite(v)?'—':(v*100).toFixed(1)+' pp';" in performance_handler
    for expression in (
        "row.confidence_interval_95_wilson",
        "x.positive_fraction_ci_95_wilson",
    ):
        assert f"ciPct({expression})" in performance_handler
    for expression in (
        "row.reliability_assessment.positive_fraction_ci_95_wilson_width",
        "row.reliability_assessment.overlap_sensitivity_absolute_gap",
        "w.consistency_assessment.positive_fraction_range",
    ):
        assert f"pp({expression})" in performance_handler
