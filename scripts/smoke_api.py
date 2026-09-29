"""Run the real demo API journey with stdlib HTTP and independent cookie jars."""

from __future__ import annotations

import argparse
import json
import os
import time
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener


class Client:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def call(self, method: str, path: str, body: dict | None = None) -> tuple[int, object]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        request = Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"} if data is not None else {},
        )
        try:
            with self.opener.open(request, timeout=15) as response:
                payload = response.read()
                content_type = response.headers.get("Content-Type", "")
                return response.status, json.loads(payload) if "json" in content_type else payload.decode("utf-8")
        except HTTPError as error:
            payload = error.read()
            try:
                detail: object = json.loads(payload)
            except ValueError:
                detail = payload.decode("utf-8", errors="replace")
            return error.code, detail

    def done(self, analysis_id: str, seconds: float = 30.0) -> dict:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            status, body = self.call("GET", f"/api/analyses/{analysis_id}")
            assert status == 200 and isinstance(body, dict), (status, body)
            if body["status"] in {"completed", "clarification", "failed", "cancelled"}:
                return body
            time.sleep(0.25)
        raise AssertionError(f"analysis {analysis_id} did not reach a terminal state in {seconds}s")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    password = os.environ.get("DATATALK_DEMO_PASSWORD", "DemoPass123!")

    northstar = Client(args.base_url)
    status, login = northstar.call("POST", "/api/auth/login", {"email": "manager@northstar.example.com", "password": password})
    assert status == 200, ("northstar login", status, login)
    status, catalog = northstar.call("GET", "/api/catalog")
    assert status == 200 and isinstance(catalog, dict) and catalog["metrics"], (status, catalog)
    status, conversation = northstar.call("POST", "/api/conversations")
    assert status == 201 and isinstance(conversation, dict), (status, conversation)
    status, queued = northstar.call("POST", f"/api/conversations/{conversation['id']}/analyses", {"question": "Which channel's net revenue changed most last month?"})
    assert status == 201 and isinstance(queued, dict) and queued["status"] == "queued", (status, queued)
    first = northstar.done(queued["id"])
    assert first["status"] == "completed" and first["result"]["rows"] and first["sql"], first
    assert first["evidence"] and first["events"], first

    status, followup = northstar.call("POST", f"/api/conversations/{conversation['id']}/analyses", {"question": "Break down by product for Direct Web"})
    assert status == 201 and isinstance(followup, dict), (status, followup)
    second = northstar.done(followup["id"])
    assert second["status"] == "completed" and second["plan"]["product"] is None, second

    status, saved = northstar.call("POST", "/api/reports", {"analysis_id": first["id"], "title": "Monthly channel change"})
    assert status == 201 and isinstance(saved, dict) and saved["current_version"] == 1, (status, saved)
    report_id = saved["id"]
    status, reopened = northstar.call("GET", f"/api/reports/{report_id}/versions/1")
    assert status == 200 and isinstance(reopened, dict) and reopened["result"] == first["result"], (status, reopened)
    status, csv_export = northstar.call("GET", f"/api/reports/{report_id}/export.csv")
    assert status == 200 and isinstance(csv_export, str) and csv_export.strip(), (status, csv_export)
    status, printable = northstar.call("GET", f"/api/reports/{report_id}/print")
    assert status == 200 and "Monthly channel change" in str(printable), (status, printable)

    status, refreshing = northstar.call("POST", f"/api/reports/{report_id}/refresh")
    assert status == 200 and isinstance(refreshing, dict) and refreshing["status"] == "queued", (status, refreshing)
    refreshed = northstar.done(refreshing["analysis_id"])
    assert refreshed["status"] == "completed", refreshed
    version_deadline = time.monotonic() + 10
    while True:
        status, report = northstar.call("GET", f"/api/reports/{report_id}")
        if status == 200 and isinstance(report, dict) and report["current_version"] == 2:
            break
        if time.monotonic() >= version_deadline:
            break
        time.sleep(0.25)
    assert status == 200 and isinstance(report, dict) and report["current_version"] == 2, (status, report)

    status, ambiguous = northstar.call("POST", f"/api/conversations/{conversation['id']}/analyses", {"question": "Who are our best customers?"})
    assert status == 201 and isinstance(ambiguous, dict), (status, ambiguous)
    clarification = northstar.done(ambiguous["id"])
    assert clarification["status"] == "clarification" and clarification["clarification"], clarification
    status, forbidden = northstar.call("POST", f"/api/conversations/{conversation['id']}/analyses", {"question": "DROP TABLE orders"})
    assert status == 201 and isinstance(forbidden, dict), (status, forbidden)
    rejected = northstar.done(forbidden["id"])
    assert rejected["status"] != "completed" and not rejected["sql"], rejected

    eastwind = Client(args.base_url)
    status, login = eastwind.call("POST", "/api/auth/login", {"email": "manager@eastwind.example.com", "password": password})
    assert status == 200, ("eastwind login", status, login)
    status, hidden = eastwind.call("GET", f"/api/reports/{report_id}")
    assert status == 404, ("cross-workspace report", status, hidden)

    viewer = Client(args.base_url)
    status, login = viewer.call("POST", "/api/auth/login", {"email": "viewer@northstar.example.com", "password": password})
    assert status == 200, ("viewer login", status, login)
    status, denied = viewer.call("POST", "/api/reports", {"analysis_id": first["id"], "title": "Viewer write"})
    assert status == 403, ("viewer save", status, denied)

    print(json.dumps({
        "status": "passed",
        "base_url": args.base_url,
        "first_analysis_id": first["id"],
        "first_rows": first["result"]["row_count"],
        "followup_analysis_id": second["id"],
        "report_id": report_id,
        "report_versions": report["current_version"],
        "checks": ["login", "catalog", "analysis", "followup", "report_version", "csv", "print", "refresh", "clarification", "forbidden_question", "workspace_boundary", "viewer_role"],
    }, indent=2))


if __name__ == "__main__":
    main()
