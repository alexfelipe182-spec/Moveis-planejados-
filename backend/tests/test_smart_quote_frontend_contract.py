from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SMART_QUOTES = ROOT / "frontend" / "smart-quotes.js"


def test_smart_quote_modal_does_not_build_formdata_from_div():
    source = SMART_QUOTES.read_text(encoding="utf-8")
    assert "new FormData(smartForm)" not in source
    assert "function numberValue(root, name)" in source
    assert "root?.querySelector?." in source


def test_smart_quote_actions_are_bound():
    source = SMART_QUOTES.read_text(encoding="utf-8")
    assert "[data-smart-interpret]" in source
    assert "[data-smart-analyze]" in source
    assert "[data-smart-save]" in source
    assert "addEventListener('click'" in source
