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


def test_dashboard_escapes_dynamic_api_content_in_html_renderers():
    html = (Path(__file__).resolve().parents[1] / "dashboard" / "index.html").read_text()
    assert "escapeHtml(x.source)" in html
    assert "escapeHtml(x.direction||'NO DIRECTION')" in html
    assert "escapeHtml(JSON.stringify(x.detail||{},null,2))" in html
    assert "escapeHtml(JSON.stringify(r,null,2))" in html
    assert "escapeHtml(x.snapshot_id.slice(0,10))" in html
    assert "escapeHtml(h.label)" in html
    assert "escapeHtml(x.horizon)" in html
    assert "escapeHtml(x.snapshot_id)" in html
