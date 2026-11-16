from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = ROOT / "dashboard"
URL = "http://127.0.0.1:8765/"


@pytest.fixture(scope="module")
def dashboard_server():
    process = subprocess.Popen(
        [sys.executable, "-m", "http.server", "8765", "--bind", "127.0.0.1", "--directory", str(DASHBOARD)],
        cwd=ROOT,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", 8765), timeout=0.5):
                    break
            except OSError:
                if process.poll() is not None:
                    raise RuntimeError("Dashboard static server exited before becoming ready")
                time.sleep(0.2)
        else:
            raise TimeoutError("Dashboard static server did not become ready")
        yield
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_dashboard_loads_without_browser_runtime_errors(dashboard_server):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1280, "height": 900})
        page_errors: list[str] = []
        page.on("pageerror", lambda error: page_errors.append(str(error)))
        response = page.goto(URL, wait_until="networkidle")
        assert response is not None and response.status == 200
        assert page.title() == "Universal Binance AI — Market Intelligence"
        assert page.locator("main.main-area").count() == 1
        assert page_errors == []
        browser.close()


@pytest.mark.parametrize("width", [360, 390, 768, 1280])
def test_dashboard_has_no_horizontal_viewport_overflow(dashboard_server, width: int):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": width, "height": 900})
        page.goto(URL, wait_until="networkidle")
        dimensions = page.evaluate(
            "() => ({viewport: document.documentElement.clientWidth, content: document.documentElement.scrollWidth})"
        )
        assert dimensions["content"] <= dimensions["viewport"], (
            f"Horizontal overflow at {width}px: {dimensions}"
        )
        browser.close()


def test_mobile_navigation_supports_escape_and_focus_restore(dashboard_server):
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 390, "height": 844})
        page.goto(URL, wait_until="networkidle")
        menu = page.locator("#mobile-menu")
        sidebar = page.locator("#sidebar")
        menu.click()
        assert "open" in (sidebar.get_attribute("class") or "").split()
        assert menu.get_attribute("aria-expanded") == "true"
        page.keyboard.press("Escape")
        assert "open" not in (sidebar.get_attribute("class") or "").split()
        assert menu.get_attribute("aria-expanded") == "false"
        assert page.evaluate("document.activeElement.id") == "mobile-menu"
        browser.close()
