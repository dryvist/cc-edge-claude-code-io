"""
Route tests — generic, validates route.yml structure and references.

This file is GENERIC — copied verbatim from the template into every pack repo.
Validates:
- route.yml exists
- every route declares a pipeline
- every referenced pipeline has a default/pipelines/<name>/conf.yml
- every route uses 'output: __group' (vct-cribl-pack-validator rule)
- no route filter is statically falsy (would never match)
- (dynamic) for each route with an auto-resolvable filter, a synthetic event
  matching that filter triggers the named pipeline and isn't dropped
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest
import yaml

from cribl_client import _parse_simple_filter

PACK_ROOT = Path(__file__).parent.parent
ROUTE_YML = PACK_ROOT / "default" / "pipelines" / "route.yml"
PIPELINES_DIR = PACK_ROOT / "default" / "pipelines"


def _load_routes() -> dict:
    with open(ROUTE_YML) as fh:
        return yaml.safe_load(fh)


def _routes_for_param() -> list:
    """Parametrize one entry per non-disabled route, keyed by route id."""
    if not ROUTE_YML.exists():
        return []
    config = yaml.safe_load(ROUTE_YML.read_text()) or {}
    return [
        pytest.param(route, id=route.get("id", f"route-{i}"))
        for i, route in enumerate(config.get("routes", []))
        if not route.get("disabled")
    ]


ROUTES = _routes_for_param()


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


@pytest.mark.skipif(
    not ROUTES,
    reason="No routes declared in default/pipelines/route.yml",
)
@pytest.mark.parametrize("route", ROUTES)
def test_route_flow_executes_pipeline(cribl, pack_id: str, route: dict) -> None:
    """Fabricate a matching event, route it, and assert the pipeline executed.

    Skips routes whose filter the local matcher cannot resolve — those need
    integration-level testing rather than this unit-level synthetic-event flow.
    """
    parsed = _parse_simple_filter(route.get("filter", ""))
    if parsed is None:
        pytest.skip(
            f"Route '{route.get('id')}' filter '{route.get('filter')!r}' "
            "is not auto-resolvable by the local matcher (expected `<field>=='<value>'`)."
        )
    assert parsed is not None  # for type narrowing — pytest.skip raised above
    field, value = parsed
    event = {
        field: value,
        "_raw": "{}",
        "_time": time.time(),
    }
    sample_id = cribl.save_sample(f"route-flow-{route.get('id')}", [event])
    try:
        result = cribl.run_route_flow(sample_id, [event], pack=pack_id)
        assert result["route"].get("id") == route.get("id"), (
            f"Expected route '{route.get('id')}' to match the synthetic event, "
            f"but route '{result['route'].get('id')}' matched first."
        )
        assert result["events"], (
            f"Pipeline '{result['pipeline']}' produced no output for the "
            f"synthetic event matching route '{route.get('id')}' "
            "— check the pipeline for unconditional Drop functions."
        )
    finally:
        cribl.delete_sample(sample_id)
