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
import os
import tarfile
import time
import uuid
from json import JSONDecodeError
from pathlib import Path
from typing import Any

import ndjson
import requests


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
