"""Ad-hoc end-to-end smoke test against a running local server.

Not part of the pytest suite (no fixtures/mocking) - this hits a real running
uvicorn process over HTTP to sanity-check the full upload -> poll -> trace ->
feedback loop before a demo. Run manually:

    venv\\Scripts\\python.exe tests\\smoke_e2e.py
"""
from __future__ import annotations

import io
import json
import time
import urllib.request

from PIL import Image, ImageDraw

BASE = "http://localhost:8000"


def req(method: str, path: str, body: bytes | None = None, content_type: str | None = None) -> dict:
    r = urllib.request.Request(BASE + path, data=body, method=method)
    if content_type:
        r.add_header("Content-Type", content_type)
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read().decode())


def make_test_image() -> bytes:
    img = Image.new("RGB", (640, 480), color=(200, 200, 200))
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 590, 430], outline=(0, 0, 0), width=3)
    draw.text((80, 200), "TITO'S HANDMADE VODKA 750ML", fill=(0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def main() -> None:
    print("1. Health check...")
    health = req("GET", "/api/health")
    print("   ", health)
    assert health["status"] == "ok"

    print("2. List accounts...")
    accounts = req("GET", "/api/accounts")
    assert len(accounts) > 0, "expected seeded accounts"
    account_id = accounts[0]["id"]
    print(f"    using account {account_id} ({accounts[0]['store_name']})")

    print("3. Upload image...")
    image_bytes = make_test_image()
    boundary = "----smoke-test-boundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="account_id"\r\n\r\n{account_id}\r\n'
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="shelf.jpg"\r\n'
        f"Content-Type: image/jpeg\r\n\r\n"
    ).encode() + image_bytes + f"\r\n--{boundary}--\r\n".encode()
    audit = req("POST", "/api/audits", body=body, content_type=f"multipart/form-data; boundary={boundary}")
    audit_id = audit["id"]
    print(f"    created audit {audit_id}, status={audit['status']}")

    print("4. Poll until completed...")
    for i in range(30):
        audit = req("GET", f"/api/audits/{audit_id}")
        print(f"    [{i}] status={audit['status']} message={audit.get('status_message')}")
        if audit["status"] in ("completed", "failed"):
            break
        time.sleep(1)
    assert audit["status"] == "completed", f"pipeline did not complete: {audit}"

    audit_json = audit["audit_json"]
    products = audit_json["products_observed"]
    assert len(products) > 0, "expected at least one product observed"
    p0 = products[0]
    assert "confidence" in p0 and "factors" in p0["confidence"], "missing confidence breakdown"
    assert "evidence" in p0, "missing evidence list"
    print(f"    {len(products)} products observed; first has confidence factors: {p0['confidence']['factors']}")
    print(f"    evidence: {p0['evidence']}")

    print("5. Fetch trace...")
    trace = req("GET", f"/api/audits/{audit_id}/trace")
    assert trace.get("available") is True, "expected a recorded trace"
    assert "frame_quality_records" in trace, "missing frame_quality_records in trace"
    print(f"    frames_sampled={trace['frames_sampled']} frames_kept={trace['frames_kept']}")
    print(f"    frame_quality_records: {len(trace['frame_quality_records'])}")

    print("6. Submit feedback (confirm)...")
    feedback_body = json.dumps({
        "field": "products_observed[0].brand",
        "review_action": "confirm",
        "ai_value": str(p0["brand"]["value"]),
        "ai_confidence": p0["brand"]["confidence"],
    }).encode()
    feedback = req("POST", f"/api/audits/{audit_id}/feedback", body=feedback_body, content_type="application/json")
    print(f"    feedback created: {feedback['id']} action={feedback['review_action']}")

    print("7. List feedback...")
    feedback_list = req("GET", f"/api/audits/{audit_id}/feedback")
    assert len(feedback_list) == 1
    print(f"    {len(feedback_list)} feedback entries")

    print("\nALL SMOKE CHECKS PASSED")


if __name__ == "__main__":
    main()
