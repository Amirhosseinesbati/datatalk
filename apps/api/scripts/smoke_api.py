"""Smoke the installed API and worker against an already seeded demo database."""
import argparse
import time
import httpx


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    args = parser.parse_args()
    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        response = client.post("/api/auth/login", json={"email": "manager@northstar.example.com", "password": "DemoPass123!"})
        response.raise_for_status()
        conversation = client.post("/api/conversations")
        conversation.raise_for_status()
        conversation_id = conversation.json()["id"]
        queued = client.post(f"/api/conversations/{conversation_id}/analyses", json={"question": "Which channel's net revenue changed most last month?"})
        queued.raise_for_status()
        analysis_id = queued.json()["id"]
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            result = client.get(f"/api/analyses/{analysis_id}")
            result.raise_for_status()
            body = result.json()
            if body["status"] in {"completed", "clarification", "failed", "cancelled"}:
                print({"analysis_id": analysis_id, "status": body["status"], "stage": body["stage"], "result": body.get("result"), "error": body.get("error"), "events": body.get("events")})
                if body["status"] != "completed":
                    raise SystemExit(1)
                report = client.post("/api/reports", json={"analysis_id": analysis_id, "title": "Channel change"})
                report.raise_for_status()
                report_id = report.json()["id"]
                reopened = client.get(f"/api/reports/{report_id}")
                reopened.raise_for_status()
                exported = client.get(f"/api/reports/{report_id}/export.csv")
                exported.raise_for_status()
                print({"report_id": report_id, "current_version": reopened.json()["current_version"], "csv_bytes": len(exported.content)})
                return
            time.sleep(0.3)
        raise TimeoutError("analysis did not complete")


if __name__ == "__main__":
    main()
