"""Purchasing edits must agree with the calculator and its exported report."""
import importlib.util
import json
from pathlib import Path
import pytest
from cansat_design.config import Config
from cansat_design.sourcing import parts_catalog

def test_catalog_uses_config_prices_and_covers_every_component():
    cfg = Config()
    cfg.components[0].cost_gbp = 7.25
    data = parts_catalog(cfg)
    flight = [r for r in data["rows"] if r["group"] == "Flight"]
    assert [r["name"] for r in flight] == [c.name for c in cfg.components]
    assert flight[0]["cost_gbp"] == 7.25
    assert all(r["links"] for r in data["rows"])
    assert len({r["id"] for r in data["rows"]}) == len(data["rows"])

def test_web_export_uses_edited_budgets(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("asteria_web_api", Path(__file__).parents[1] / "site/web_api.py")
    web = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(web)
    monkeypatch.setattr(web, "OUT", str(tmp_path))
    params = json.loads(web.defaults_json())
    params["components"][0]["qty"] = 2
    params["components"][0]["cost_gbp"] = 20
    params["ground"] = [{"name": "Ground test", "qty": 2, "cost_gbp": 12.5}]
    params["materials_cost_gbp"] = 21
    result = json.loads(web.run(json.dumps(params), with_sweeps=False))
    expected = sum(c["cost_gbp"] for c in params["components"]) + 21
    assert result["key"]["cost_gbp"] == pytest.approx(expected)
    assert result["key"]["ground_gbp"] == 12.5
    assert f"£{expected:.2f}" in result["summary"]
    assert result["streams"]
    assert "canopy_pattern.svg" in result["svgs"]
