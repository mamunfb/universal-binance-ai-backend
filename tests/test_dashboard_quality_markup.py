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


def test_dashboard_has_one_html_escape_helper_and_guards_numeric_rendering():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert html.count("const escapeHtml=") == 1
    assert "const safeFixed=" in html
    assert "const safeIsoTimestamp=" in html
    assert "escapeHtml(safeIsoTimestamp(x.analyzed_at_ms))" in html


def test_dashboard_validates_price_path_data_before_safe_svg_rendering():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "Price-path response contains invalid candle or reference-price values" in html
    assert "values.every(v=>Number.isFinite(v)&&v>0)" in html
    assert "setSafeHtml($('pricePath')" in html
    assert "safeFixed(r.actual_market_change_percent,3)" in html


def test_dashboard_uses_guarded_formatter_for_all_api_numeric_fields():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    script = html.split("<script>", 1)[1].split("</script>", 1)[0]
    assert script.count(".toFixed(") == 1
    assert "safeFixed((g.early||{}).positive_fraction*100,1)" in script
    assert "safeFixed((t.post_transition||{}).positive_fraction*100,1)" in script


def test_dashboard_guards_unexpected_api_response_shapes():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "const isRecord=value=>value!==null&&typeof value==='object'&&!Array.isArray(value)" in html
    assert "Analysis API returned an unexpected response shape" in html
    assert "Quality API returned an unexpected response shape" in html
    assert "Performance API returned an unexpected response shape" in html
    assert "(Array.isArray(latest.evidence)?latest.evidence:[]).filter(isRecord)" in html


def test_dashboard_uses_nonnegative_safe_integer_formatter_for_counts():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "Number.isSafeInteger(n)&&n>=0?String(n):'—'" in html
    assert "safeCount(h.sample_size)" in html
    assert "safeCount(row.non_overlapping_directional_sample_size)" in html
    assert "safeCount(cm.true_positive??0)" in html


def test_dashboard_guards_nested_performance_report_objects_and_arrays():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "isRecord(h.signal_quality)?h.signal_quality:{}" in html
    assert "Object.entries(isRecord(h.signal_quality_by_regime)?h.signal_quality_by_regime:{})" in html
    assert "Object.entries(isRecord(groups)?groups:{}).filter(([,g])=>isRecord(g))" in html
    assert "Object.entries(isRecord(horizon.rankings)?horizon.rankings:{}).filter(([,ranking])=>isRecord(ranking))" in html
    assert "(Array.isArray(ranking.ranked)?ranking.ranked:[]).filter(isRecord)" in html


def test_dashboard_escapes_all_remaining_dynamic_performance_labels_and_counts():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "safeCount(ranking.minimum_sample_size)" in html
    assert "safeCount(f.test_matured_outcome_count)" in html
    assert "safeCount(x.non_overlapping_directional_sample_size)" in html
    assert "escapeHtml(x.horizon)" in html
    assert "escapeHtml(x.bias)" in html
    assert "Array.isArray(w.folds)?w.folds:[]" in html
    assert "Array.isArray(q.flags)?q.flags:[]" in html


def test_dashboard_svg_reference_label_uses_safe_max_and_numeric_formatting():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "safeFixed(Math.max(12,ry-6),2)" in html
    assert "Math.maxsafeFixed" not in html


def test_dashboard_handles_non_json_api_responses_without_masking_http_status():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "API returned a non-JSON response (HTTP '+r.status+')" in html


def test_dashboard_filters_malformed_history_and_collector_entries():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "(Array.isArray(r.snapshots)?r.snapshots:[]).filter(isRecord).map(x=>" in html
    assert "(Array.isArray(x.last_results)?x.last_results:[]).filter(isRecord)" in html


def test_dashboard_guards_nested_regime_transition_api_data():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "isRecord(h.regime_bias_breakdown)&&isRecord(h.regime_bias_breakdown.market_regime)" in html
    assert "isRecord(x.regime_transition_analysis)&&isRecord(x.regime_transition_analysis.dimensions)" in html
    assert "(Array.isArray(d.transitions)?d.transitions:[]).filter(isRecord)" in html


def test_dashboard_validates_snapshot_save_response_shape():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "Snapshot API returned an unexpected response shape" in html
