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


def test_smart_quote_distinguishes_openai_from_local_assistance():
    source = SMART_QUOTES.read_text(encoding="utf-8")
    assert "draft.interpretation_source" in source
    assert "assisted_local" in source
    assert "IA OpenAI" in source
    assert "Modo assistido" in source


def test_smart_quote_never_enables_save_for_zero_or_stale_total():
    source = SMART_QUOTES.read_text(encoding="utf-8")
    assert "const invalidateEstimate" in source
    assert "lastEstimate = null" in source
    assert "saveButton.disabled = true" in source
    assert "Number(lastEstimate.suggested_total || 0) <= 0" in source
    assert "Number(draft.suggested_total || 0) > 0" in source


def test_smart_quote_busy_state_blocks_duplicate_button_actions():
    source = SMART_QUOTES.read_text(encoding="utf-8")
    assert "setButtonBusy" in source
    assert "aria-busy" in source
    assert "deleteButton.disabled = true" in source
