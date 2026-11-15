from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"


def test_quality_page_uses_current_spa_controls_and_output_region():
    html = (DASHBOARD / "index.html").read_text(encoding="utf-8")
    for identifier in (
        'id="quality-market"',
        'id="quality-symbol"',
        'id="quality-interval"',
        'id="quality-lookback"',
        'id="load-quality"',
        'id="quality-state"',
        'id="quality-output"',
    ):
        assert identifier in html


def test_quality_request_uses_verified_route_and_shared_api_client():
    app = (DASHBOARD / "app.js").read_text(encoding="utf-8")
    assert 'api("/api/v1/quality/market-data/"+encodeURIComponent(market)+"/"+encodeURIComponent(symbol)+"?"+q' in app
    assert 'new URLSearchParams({interval,lookback_hours:String(lookback)})' in app
    assert 'credentials:"omit"' in app
    assert 'cache:"no-store"' in app


def test_quality_inputs_validate_symbol_interval_and_lookback_bounds():
    app = (DASHBOARD / "app.js").read_text(encoding="utf-8")
    assert 'if(!/^[A-Z0-9]{1,40}$/.test(symbol))' in app
    assert 'if(!Number.isInteger(lookback)||lookback<1||lookback>2160)' in app
    assert 'lookbackInput.setCustomValidity("Enter a whole number from 1 to 2160.")' in app
    assert '["quality-market","quality-symbol","quality-interval","quality-lookback"]' in app


def test_quality_response_is_rendered_as_text_json_without_persistent_credentials():
    app = (DASHBOARD / "app.js").read_text(encoding="utf-8")
    html = (DASHBOARD / "index.html").read_text(encoding="utf-8")
    assert 'showJson("quality-output",data)' in app
    assert 'setText("quality-state",metadataText(data.status,"Report received",80))' in app
    assert "localStorage" not in app
    assert "sessionStorage" not in app
    assert 'id="quality-output"' in html
