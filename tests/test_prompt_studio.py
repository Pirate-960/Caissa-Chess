from pathlib import Path

from core.prompt_manager import PromptManager


def test_prompt_catalog_defaults():
    PromptManager.clear_prompt_overrides()
    catalog = PromptManager.get_prompt_catalog()
    assert "system_template" in catalog
    assert "user_prompt_prefix" in catalog
    assert "user_prompt_suffix" in catalog
    assert "CAISSA" in catalog["system_template"]


def test_prompt_overrides_and_clear():
    PromptManager.clear_prompt_overrides()
    PromptManager.set_prompt_overrides(
        system_template="Hello {era} {theme} {white_player} {black_player} {aggression_score} {chaos_score} {depth} {climax_end} {date} {era_guidelines} {theme_instruction} {aggression_description} {conclusion_objective} {expected_result}",
        user_prompt_prefix="PREFIX",
        user_prompt_suffix="SUFFIX",
    )
    catalog = PromptManager.get_prompt_catalog()
    assert catalog["user_prompt_prefix"] == "PREFIX"
    assert catalog["user_prompt_suffix"] == "SUFFIX"
    ok, _ = PromptManager.validate_system_template(catalog["system_template"])
    assert ok
    PromptManager.clear_prompt_overrides()
    catalog2 = PromptManager.get_prompt_catalog()
    assert catalog2["user_prompt_prefix"] == ""
    assert catalog2["user_prompt_suffix"] == ""


def test_prompt_profile_save_and_load(tmp_path: Path):
    PromptManager.clear_prompt_overrides()
    PromptManager.set_prompt_overrides(
        user_prompt_prefix="A",
        user_prompt_suffix="B",
    )
    saved = PromptManager.save_prompt_profile("x", root=tmp_path)
    assert saved.exists()
    PromptManager.clear_prompt_overrides()
    PromptManager.load_prompt_profile("x", root=tmp_path)
    catalog = PromptManager.get_prompt_catalog()
    assert catalog["user_prompt_prefix"] == "A"
    assert catalog["user_prompt_suffix"] == "B"


def test_prepared_templates_exist():
    names = PromptManager.list_prepared_templates()
    assert "balanced_default" in names
    assert "asset_tal_brilliancy" in names
    t = PromptManager.get_prepared_template("balanced_default")
    assert "system_template" in t


def test_profile_metadata_roundtrip(tmp_path: Path):
    PromptManager.clear_prompt_overrides()
    PromptManager.set_prompt_overrides(user_prompt_prefix="P", user_prompt_suffix="S")
    saved = PromptManager.save_prompt_profile(
        "meta_profile",
        root=tmp_path,
        author="tester",
        version="2.1.0",
        compatibility={"single": True, "match": True, "tournament": True},
    )
    assert saved.exists()
    meta = PromptManager.read_prompt_profile_metadata("meta_profile", root=tmp_path)
    assert meta["author"] == "tester"
    assert meta["version"] == "2.1.0"
    assert "checksum" in meta


def test_commentary_profile_state_and_lint_risk():
    PromptManager.clear_prompt_overrides()
    PromptManager.set_commentary_profile("educational", intensity=8)
    st = PromptManager.get_prompt_context_state()
    assert st["commentary_profile"] == "educational"
    assert st["commentary_intensity"] == "8"

    weak = "SHORT {era} {white_player}"
    report = PromptManager.lint_system_template(weak)
    assert "risk_score" in report
    assert report["risk_score"] > 0
    assert report["risk_level"] in ("low", "medium", "high")
