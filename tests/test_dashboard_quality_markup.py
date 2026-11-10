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
