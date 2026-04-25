"""
Route tests — generic, validates route.yml structure and references.

This file is GENERIC — copied verbatim from the template into every pack repo.
Validates:
- route.yml exists
- every route declares a pipeline
- every referenced pipeline has a default/pipelines/<name>/conf.yml
- every route uses 'output: __group' (vct-cribl-pack-validator rule)
- no route filter is statically falsy (would never match)
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

PACK_ROOT = Path(__file__).parent.parent
ROUTE_YML = PACK_ROOT / "default" / "pipelines" / "route.yml"
PIPELINES_DIR = PACK_ROOT / "default" / "pipelines"


def _load_routes() -> dict:
    with open(ROUTE_YML) as fh:
        return yaml.safe_load(fh)


def test_route_yml_exists() -> None:
    assert ROUTE_YML.exists(), f"{ROUTE_YML} does not exist"


def test_routes_are_declared() -> None:
    config = _load_routes()
    assert config.get("routes"), f"{ROUTE_YML} declares no routes"


def test_routes_have_pipelines() -> None:
    config = _load_routes()
    for route in config["routes"]:
        assert route.get("pipeline"), (
            f"Route '{route.get('id', '<anonymous>')}' missing 'pipeline' field"
        )


def test_pipeline_files_exist_for_each_route() -> None:
    config = _load_routes()
    for route in config["routes"]:
        pipeline = route["pipeline"]
        conf = PIPELINES_DIR / pipeline / "conf.yml"
        assert conf.exists(), (
            f"Route '{route.get('id')}' references pipeline '{pipeline}' "
            f"but {conf} does not exist"
        )


def test_routes_use_group_output() -> None:
    """vct-cribl-pack-validator rule: routes should output to __group, not input_id."""
    config = _load_routes()
    bad = [
        r.get("id") for r in config["routes"]
        if r.get("output") != "__group"
    ]
    if bad:
        pytest.fail(
            f"Routes not using output: __group: {bad}. "
            "Per validator rule, routes should target __group "
            "so source renames don't break routing."
        )


def test_routes_filters_not_statically_falsy() -> None:
    config = _load_routes()
    for route in config["routes"]:
        f = route.get("filter")
        assert f is not None, f"Route '{route.get('id')}' has no filter"
        normalised = str(f).strip().lower()
        assert normalised not in ("false", "0", '""', "''"), (
            f"Route '{route.get('id')}' has falsy filter '{f}' — would never match"
        )


def test_no_pipeline_named_main() -> None:
    """vct-cribl-pack-validator rule: no pipeline should be named 'main'."""
    config = _load_routes()
    for route in config["routes"]:
        assert route["pipeline"] != "main", (
            f"Route '{route.get('id')}' uses pipeline 'main'. "
            "Per validator rule, pipelines must have descriptive names."
        )
