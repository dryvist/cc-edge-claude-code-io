"""
Cribl management API client for pack testing.

Adapted from the criblpacks/cribl-palo-alto-networks pattern (Cribl's own pack
test pattern). Streamlined for parametrized fixture-based testing.

References:
- https://github.com/criblpacks/cribl-palo-alto-networks/blob/main/test/cribl_stream.py
- https://docs.cribl.io/api-reference/
"""

from __future__ import annotations

import io
import json
import os
import re
import tarfile
import time
import uuid
from json import JSONDecodeError
from pathlib import Path
from typing import Any

import ndjson
import requests
import yaml

# Locate the pack root (one level up from tests/) so client helpers can read
# package.json and route.yml without each caller passing the path in.
PACK_ROOT = Path(__file__).resolve().parent.parent

# Canonical Cribl filter shape we can auto-resolve: `<field>=='<value>'`.
# Anything more complex (boolean ops, function calls, regex) is out of scope
# for the local evaluator — callers should pytest.skip when this returns None.
_SIMPLE_FILTER_RE = re.compile(r"^\s*([A-Za-z_]\w*)\s*==\s*['\"](.*?)['\"]\s*$")


def _parse_simple_filter(expr: str) -> tuple[str, str] | None:
    """Parse `<field>=='<value>'` (or `=="value"`) into (field, value).

    Returns None for any expression we cannot statically resolve. Tests should
    pytest.skip when None is returned so complex filters don't block the suite.
    """
    match = _SIMPLE_FILTER_RE.match(expr or "")
    if not match:
        return None
    return match.group(1), match.group(2)


class CriblClient:
    """Thin wrapper around the Cribl management API for pack testing."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9000,
        username: str = "admin",
        password: str = "admin",
        scheme: str = "http",
    ) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.scheme = scheme
        self._token: str | None = None

    @property
    def base_url(self) -> str:
        return f"{self.scheme}://{self.host}:{self.port}/api/v1"

    @property
    def token(self) -> str:
        if self._token is None:
            self._token = self._login()
        return self._token

    def _login(self) -> str:
        response = requests.post(
            f"{self.base_url}/auth/login",
            json={"username": self.username, "password": self.password},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()["token"]

    def _call(
        self,
        method: str,
        endpoint: str,
        *,
        pack: str | None = None,
        payload: dict | None = None,
        data: bytes | None = None,
        params: dict | None = None,
        authenticated: bool = True,
    ) -> Any:
        prefix = f"/p/{pack}" if pack else ""
        url = f"{self.base_url}{prefix}{endpoint}"

        headers: dict[str, str] = {}
        if authenticated:
            headers["authorization"] = f"Bearer {self.token}"

        response = requests.request(
            method.upper(),
            url,
            headers=headers,
            params=params,
            data=data,
            json=payload,
            timeout=30,
        )

        try:
            return response.json()
        except JSONDecodeError:
            try:
                return response.json(cls=ndjson.Decoder)
            except Exception:
                return response.content

    # ---- Lifecycle ---------------------------------------------------------

    def wait_until_ready(self, timeout_seconds: int = 120) -> None:
        """Poll the health endpoint until Cribl is ready or we time out."""
        deadline = time.time() + timeout_seconds
        last_err: Exception | None = None
        while time.time() < deadline:
            try:
                response = requests.get(
                    f"{self.base_url}/health",
                    timeout=5,
                )
                if response.status_code == 200:
                    return
            except requests.RequestException as exc:
                last_err = exc
            time.sleep(2)
        raise TimeoutError(
            f"Cribl at {self.base_url} did not become ready in {timeout_seconds}s "
            f"(last error: {last_err})"
        )

    # ---- Pack management ---------------------------------------------------

    @staticmethod
    def create_pack_tarball(pack_root: Path) -> bytes:
        """Build an in-memory .crbl tarball from pack_root.

        Excludes test/dev directories that should not ship inside the pack.
        """
        excluded_basenames = {
            ".git",
            ".github",
            "tests",
            "test",
            "venv",
            ".venv",
            ".DS_Store",
            ".idea",
            ".pytest_cache",
            "__pycache__",
            ".direnv",
        }

        def filter_func(tarinfo: tarfile.TarInfo) -> tarfile.TarInfo | None:
            name = os.path.basename(tarinfo.name)
            if name in excluded_basenames:
                return None
            if name.endswith(".crbl"):
                return None
            tarinfo.uid = tarinfo.gid = 0
            tarinfo.uname = tarinfo.gname = "root"
            return tarinfo

        buffer = io.BytesIO()
        with tarfile.open(fileobj=buffer, mode="w:gz") as tar:
            tar.add(str(pack_root), arcname="", filter=filter_func)
        buffer.seek(0)
        return buffer.read()

    def install_pack(self, tarball: bytes, expected_id: str | None = None, timeout_seconds: int = 30) -> None:
        """Upload a .crbl tarball, install it, and (optionally) wait for it to appear.

        Cribl's pack install is asynchronous — the POST returns before the pack
        is fully registered. If expected_id is given, poll /packs until it
        appears (or raise TimeoutError). Without expected_id, returns
        immediately after the install POST and the caller is responsible for
        waiting if needed.
        """
        params = {
            "filename": f"{uuid.uuid4()}.crbl",
            "size": len(tarball),
        }
        upload = self._call("put", "/packs", params=params, data=tarball)
        if upload:
            self._call("post", "/packs", payload=upload)

        if expected_id is None:
            return

        deadline = time.time() + timeout_seconds
        installed: list[str | None] = []
        while time.time() < deadline:
            installed = [p.get("id") for p in self.list_packs()]
            if expected_id in installed:
                return
            time.sleep(0.5)
        raise TimeoutError(
            f"Pack '{expected_id}' did not appear in /packs after {timeout_seconds}s. "
            f"Currently installed: {installed}"
        )

    def delete_pack(self, pack_id: str) -> None:
        info = self._call("get", f"/packs/{pack_id}")
        if info:
            self._call("delete", f"/packs/{pack_id}", payload=info)

    def list_packs(self) -> list[dict]:
        response = self._call("get", "/packs")
        return response.get("items", []) if isinstance(response, dict) else []

    # ---- Sample lifecycle --------------------------------------------------

    def save_sample(self, name: str, events: list[dict]) -> str:
        """Save events as a named sample, returning the sample ID."""
        payload = {
            "sampleName": name,
            "context": {"events": events},
        }
        response = self._call("post", "/system/samples", payload=payload)
        return response["items"][0]["id"]

    def delete_sample(self, sample_id: str) -> None:
        info = self._call("get", f"/system/samples/{sample_id}")
        if isinstance(info, dict) and info.get("items"):
            self._call(
                "delete",
                f"/system/samples/{sample_id}",
                payload=info["items"][0],
            )

    def delete_all_samples(self) -> None:
        response = self._call("get", "/system/samples")
        if not isinstance(response, dict):
            return
        for sample in response.get("items", []):
            if "isTemplate" in sample:
                continue
            self._call(
                "delete",
                f"/system/samples/{sample['id']}",
                payload=sample,
            )

    # ---- Pipeline execution ------------------------------------------------

    def run_pipeline(
        self,
        pipeline: str,
        sample_id: str,
        pack: str | None = None,
        timeout_ms: int = 10000,
        memory_mb: int = 2048,
    ) -> list[dict]:
        """Execute a pipeline against a saved sample, returning processed events."""
        payload = {
            "mode": "pipe",
            "pipelineId": pipeline,
            "level": 3,
            "sampleId": sample_id,
            "dropped": True,
            "cpuProfile": False,
            "timeout": timeout_ms,
            "memory": memory_mb,
        }
        response = self._call("post", "/preview", pack=pack, payload=payload)
        if isinstance(response, dict):
            return response.get("items", [])
        return response or []

    # ---- Route flow + assertions ------------------------------------------

    def run_route_flow(
        self,
        sample_id: str,
        events: list[dict],
        pack: str | None = None,
    ) -> dict:
        """Match events against route.yml filters, then execute the matched pipeline.

        Cribl's `/preview` API has no `mode: "route"` — this is the local
        fallback. Loads `PACK_ROOT/default/pipelines/route.yml`, evaluates each
        non-disabled route's filter against the supplied events using the
        canonical `<field>=='<value>'` matcher, and on the first match calls
        `run_pipeline()` for that route's pipeline.

        Returns:
            {"route": <route dict>, "pipeline": <pipeline id>, "events": [...]}

        Raises:
            ValueError: if no route matches. The error lists any filters that
                were skipped because the local matcher doesn't support them, so
                the caller can decide whether to treat the situation as a
                pytest.skip vs a real failure.
        """
        route_yml = PACK_ROOT / "default" / "pipelines" / "route.yml"
        config = yaml.safe_load(route_yml.read_text())

        skipped_filters: list[str] = []
        for route in config.get("routes", []):
            if route.get("disabled"):
                continue
            parsed = _parse_simple_filter(route.get("filter", ""))
            if parsed is None:
                skipped_filters.append(route.get("filter", ""))
                continue
            field, expected_value = parsed
            if any(event.get(field) == expected_value for event in events):
                output = self.run_pipeline(route["pipeline"], sample_id, pack=pack)
                return {
                    "route": route,
                    "pipeline": route["pipeline"],
                    "events": output,
                }

        raise ValueError(
            "No matching route for given events. "
            f"Filters skipped (unparseable by local matcher): {skipped_filters}"
        )

    def assert_required_fields(
        self,
        events: list[dict],
        pack_type: str | None = None,
    ) -> None:
        """Assert every event has the canonical output fields for its pack type.

        Edge packs require `sourcetype` + `index` (Splunk-canonical routing
        fields). Stream packs require `host` + `source` + `_time`.

        When `pack_type` is None, infer it from `package.json` name prefix
        (`cc-edge-` -> edge, `cc-stream-` -> stream). Tests can override by
        passing pack_type explicitly.
        """
        if pack_type is None:
            pack_type = _detect_pack_type()
        if pack_type == "edge":
            required: tuple[str, ...] = ("sourcetype", "index")
        elif pack_type == "stream":
            required = ("host", "source", "_time")
        else:
            raise ValueError(
                f"Unknown pack_type {pack_type!r} (expected 'edge' or 'stream')"
            )

        violations: list[str] = []
        for i, event in enumerate(events):
            missing = [k for k in required if k not in event]
            if missing:
                violations.append(f"event {i}: missing {missing}")

        assert not violations, (
            f"{pack_type.title()} pack required fields {required} missing from "
            f"{len(violations)}/{len(events)} event(s):\n  "
            + "\n  ".join(violations)
        )

    # ---- Live capture ------------------------------------------------------
    #
    # Two-phase async API. start_capture() returns a capture id immediately;
    # read_capture() polls until the session reports complete. These primitives
    # exist to support future integration tests that publish into a live source
    # and assert routes fire — Phase A's unit tests don't exercise them.

    def start_capture(
        self,
        filter_expr: str,
        max_events: int = 100,
        timeout_ms: int = 30000,
    ) -> str:
        """Start an async capture matching `filter_expr`. Returns the capture id."""
        payload = {
            "filter": filter_expr,
            "maxEvents": max_events,
            "timeout": timeout_ms,
            "level": 0,
        }
        response = self._call("post", "/lib/captures", payload=payload)
        if not isinstance(response, dict) or "captureId" not in response:
            raise RuntimeError(f"Unexpected capture response: {response!r}")
        return response["captureId"]

    def read_capture(
        self,
        capture_id: str,
        poll_interval: float = 1.0,
        timeout_seconds: int = 60,
    ) -> list[dict]:
        """Poll the capture session until status=='complete', returning events."""
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            response = self._call("get", f"/lib/captures/{capture_id}/events")
            if isinstance(response, dict) and response.get("status") == "complete":
                return response.get("items", [])
            time.sleep(poll_interval)
        raise TimeoutError(
            f"Capture {capture_id} did not complete in {timeout_seconds}s"
        )


def _detect_pack_type() -> str:
    """Infer pack_type ('edge' or 'stream') from package.json name."""
    name = json.loads((PACK_ROOT / "package.json").read_text()).get("name", "")
    if name.startswith("cc-edge-"):
        return "edge"
    if name.startswith("cc-stream-"):
        return "stream"
    raise ValueError(
        f"Cannot detect pack_type from package.json name {name!r}; "
        "expected 'cc-edge-<source>-io' or 'cc-stream-<source>-io' prefix."
    )
