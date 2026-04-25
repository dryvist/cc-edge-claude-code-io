"""
Shared pytest fixtures.

Session-scoped: connect to Cribl, build pack tarball from PACK_ROOT, install,
yield client to tests, then clean up.

Configurable via env vars (defaults match docker-compose.yml and CI service):
- CRIBL_HOST   (default: localhost)
- CRIBL_PORT   (default: 9000)
- CRIBL_USER   (default: admin)
- CRIBL_PASS   (default: admin)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from cribl_client import CriblClient

PACK_ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="session")
def pack_id() -> str:
    return json.loads((PACK_ROOT / "package.json").read_text())["name"]


@pytest.fixture(scope="session")
def cribl(pack_id: str):
    """Cribl client with the pack pre-installed for the duration of the session."""
    client = CriblClient(
        host=os.environ.get("CRIBL_HOST", "localhost"),
        port=int(os.environ.get("CRIBL_PORT", "9000")),
        username=os.environ.get("CRIBL_USER", "admin"),
        password=os.environ.get("CRIBL_PASS", "admin"),
    )
    client.wait_until_ready()

    tarball = client.create_pack_tarball(PACK_ROOT)
    client.install_pack(tarball, expected_id=pack_id)

    yield client

    try:
        client.delete_pack(pack_id)
    except Exception:
        pass
    try:
        client.delete_all_samples()
    except Exception:
        pass
