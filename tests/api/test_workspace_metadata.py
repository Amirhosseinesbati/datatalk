"""Dataset identity and local origins must not depend on optimistic UI labels."""

from types import SimpleNamespace

import pytest
from datatalk.dataset_identity import dataset_kind


@pytest.mark.parametrize(
    ("workspace", "sources", "expected"),
    [
        ("ws-northstar", ["data/generated/fast"], "synthetic"),
        ("ws-eastwind", ["data/generated/full", "csv-import:example"], "mixed"),
        ("client", ["csv-import:first", "csv-import:second"], "imported"),
        ("client", ["future-connector"], "unknown"),
        ("client", ["future-connector", "csv-import:first"], "unknown"),
        ("ws-northstar", [], "unknown"),
        ("ws-northstar", ["future-connector"], "unknown"),
        ("ws-northstar", ["synthetic-seed:custom-fixture-directory"], "synthetic"),
    ],
)
def test_dataset_identity(workspace, sources, expected):
    assert dataset_kind(workspace, sources) == expected


def test_development_origin_keeps_cross_origin_policy(monkeypatch):
    from datatalk import main
    from fastapi.testclient import TestClient

    monkeypatch.setattr(
        main,
        "get_settings",
        lambda: SimpleNamespace(datatalk_mode="demo", datatalk_allowed_origins=""),
    )
    with TestClient(main.app) as client:
        # A missing route needs no DB connection; the middleware runs before routing.
        assert (
            client.post(
                "/api/missing", headers={"origin": "http://127.0.0.1:4314"}
            ).status_code
            == 404
        )
        assert (
            client.post(
                "/api/missing", headers={"origin": "https://untrusted.example"}
            ).status_code
            == 403
        )
        assert (
            client.post(
                "/api/missing", headers={"sec-fetch-site": "cross-site"}
            ).status_code
            == 403
        )
