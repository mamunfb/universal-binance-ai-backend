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
