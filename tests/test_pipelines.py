"""
Pipeline tests — generic, parametrized over tests/fixtures/.

Convention:
    tests/fixtures/<pipeline-name>/<case>.json          -- input event(s)
    tests/fixtures/<pipeline-name>/<case>.expected.json -- (optional) expected output

For each fixture:
1. Save the input as a Cribl sample.
2. Run it through the named pipeline (within this pack's namespace).
3. If <case>.expected.json exists, partial-match-assert each output event has
   the expected fields and values. Extra fields in actual output are allowed.
4. If <case>.expected.json is absent, smoke-test only: assert non-empty output.

This file is GENERIC — copied verbatim from the template into every pack repo.
Pack-specific behavior is expressed entirely through fixture data.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def _discover_cases() -> list:
    if not FIXTURES.exists():
        return []
    cases = []
    for pipeline_dir in sorted(p for p in FIXTURES.iterdir() if p.is_dir()):
        pipeline = pipeline_dir.name
        for inp in sorted(pipeline_dir.glob("*.json")):
            if inp.stem.endswith(".expected") or inp.name.endswith(".expected.json"):
                continue
            exp = inp.with_name(inp.stem + ".expected.json")
            cases.append(
                pytest.param(
                    pipeline,
                    inp,
                    exp if exp.exists() else None,
                    id=f"{pipeline}/{inp.stem}",
                )
            )
    return cases


CASES = _discover_cases()


def _load_events(path: Path) -> list[dict]:
    raw = json.loads(path.read_text())
    return raw if isinstance(raw, list) else [raw]


def _assert_partial_match(actual: list[dict], expected: list[dict], context: str) -> None:
    assert len(actual) == len(expected), (
        f"{context}: pipeline produced {len(actual)} events, expected {len(expected)}"
    )
    for i, (act, exp) in enumerate(zip(actual, expected)):
        for key, exp_val in exp.items():
            assert key in act, (
                f"{context} event {i}: expected key '{key}' missing from output"
            )
            assert act[key] == exp_val, (
                f"{context} event {i}, key '{key}': "
                f"expected {exp_val!r}, got {act[key]!r}"
            )


@pytest.mark.skipif(
    not CASES,
    reason="No fixtures found in tests/fixtures/<pipeline>/",
)
@pytest.mark.parametrize("pipeline,input_file,expected_file", CASES)
def test_pipeline_processes_sample(
    cribl,
    pack_id: str,
    pipeline: str,
    input_file: Path,
    expected_file: Path | None,
) -> None:
    events = _load_events(input_file)
    sample_id = cribl.save_sample(input_file.stem, events)
    try:
        result = cribl.run_pipeline(pipeline, sample_id, pack=pack_id)

        assert result, (
            f"Pipeline '{pipeline}' produced no output for {input_file.name}. "
            "Check the pipeline's filter/drop conditions."
        )

        if expected_file is None:
            return  # Smoke-test only

        expected = _load_events(expected_file)
        _assert_partial_match(result, expected, context=input_file.name)
    finally:
        cribl.delete_sample(sample_id)
