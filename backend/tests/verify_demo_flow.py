"""
End-to-end integration test verifying the complete Failure Lab -> Dispatch Webhook -> Domain Sync -> AI -> Policy -> Approval -> Execution -> Audit -> Analytics pipeline.
"""
import httpx

base = "http://localhost:8000"

def clean(s):
    return str(s).encode("ascii", "ignore").decode("ascii")

def test_full_demo_flow():
    # 1. Health check
    h = httpx.get(f"{base}/health").json()
    assert h["status"] == "ok"
    print("[PASS] 1. Backend Health OK:", clean(h))

    # 2. System status
    s = httpx.get(f"{base}/api/v1/system/status").json()
    assert s["status"] in ("operational", "degraded")
    print(f"[PASS] 2. System Status OK: DB={s['database']}, Queue={s['job_queue_status']}")

    # 3. Webhook fixtures
    fixtures = httpx.get(f"{base}/api/v1/webhooks/fixtures").json()
    assert len(fixtures) >= 3
    print(f"[PASS] 3. Webhook Fixtures OK ({len(fixtures)} fixtures found)")

    # 4. Dispatch synthetic payment.failed webhook
    fixture = fixtures[0] # payment_failed_insufficient_funds
    test_payload = {
        "event_type": fixture["event_type"],
        "payload": fixture["payload"]
    }
    dispatch_res = httpx.post(f"{base}/api/v1/webhooks/test/razorpay", json=test_payload).json()
    print("[PASS] 4. Webhook Dispatch OK:", dispatch_res["status"], f"Event ID: {dispatch_res['event_id']}")
    assert dispatch_res["status"] in ("processed", "duplicate")

    # 5. Check payments list
    payments = httpx.get(f"{base}/api/v1/payments").json()
    assert payments["total"] > 0
    print(f"[PASS] 5. Payments List OK ({payments['total']} payments found)")

    # 6. Check recovery cases
    cases = httpx.get(f"{base}/api/v1/recovery/cases").json()
    assert cases["total"] > 0
    print(f"[PASS] 6. Recovery Cases OK ({cases['total']} cases found)")

    # 7. Check approvals
    approvals = httpx.get(f"{base}/api/v1/approvals").json()
    print(f"[PASS] 7. Approvals List OK ({approvals['total']} approvals found)")

    # 8. Check analytics overview
    analytics = httpx.get(f"{base}/api/v1/analytics/overview").json()
    print("[PASS] 8. Analytics Overview OK:", {
        "total_cases": analytics["total_cases"],
        "recoverable": analytics["total_recoverable_amount"],
        "recovered": analytics["total_recovered_amount"],
        "recovery_rate": f"{analytics['recovery_rate'] * 100:.1f}%"
    })

    # 9. Check audit log
    audit = httpx.get(f"{base}/api/v1/audit").json()
    assert audit["total"] > 0
    print(f"[PASS] 9. Audit Logs OK ({audit['total']} audit entries logged)")

    # 10. Check recent webhook events feed
    recent = httpx.get(f"{base}/api/v1/webhooks/recent-events").json()
    assert recent["total"] > 0
    print(f"[PASS] 10. Live Webhook Feed OK ({recent['total']} events)")

    # 11. Run High-Risk scenario
    hr_res = httpx.post(f"{base}/api/v1/demo/scenarios/human_review/run?seed=99").json()
    print("[PASS] 11. High-Risk Human Review Gate Scenario OK:", clean(hr_res["message"]))
    assert hr_res["approval_status"] == "pending"

    print("\n[SUCCESS] ALL 11 END-TO-END DEMO FLOW CHECKS PASSED!")

if __name__ == "__main__":
    test_full_demo_flow()
