"""
Integration tests for RecoverAI REST API endpoints under /api/v1.

Covers:
- Payments API (POST, GET list, GET by ID, GET by rzp ID, PATCH status, error codes)
- Revenue API (POST, GET by ID, GET by payment ID, PATCH status, POST mark-at-risk)
- Recovery API (POST case, GET cases list, GET case by ID, PATCH state transition, POST action, PATCH action status)
- Audit API (GET audit logs with filtering)
- OpenAPI schema and Swagger /docs availability
"""


def test_payment_api_crud_and_validation(client):
    """Test payment creation, retrieval, status update, and validation errors."""
    # 1. Invalid amount (< 0) -> 422 Unprocessable Entity
    resp_invalid = client.post(
        "/api/v1/payments",
        json={
            "razorpay_payment_id": "pay_api_inv_001",
            "amount": -500,
            "currency": "INR",
        },
    )
    assert resp_invalid.status_code == 422

    # 2. Valid creation -> 201 Created
    resp_create = client.post(
        "/api/v1/payments",
        json={
            "razorpay_payment_id": "pay_api_001",
            "razorpay_order_id": "order_api_001",
            "amount": 79900,  # 799.00 INR
            "currency": "INR",
            "status": "failed",
            "method": "upi",
            "customer_email": "user@example.com",
            "customer_reference": "user_ref_001",
        },
    )
    assert resp_create.status_code == 201
    payment_data = resp_create.json()
    assert payment_data["id"] is not None
    assert payment_data["amount"] == 79900
    assert payment_data["status"] == "failed"
    payment_id = payment_data["id"]

    # 3. Duplicate razorpay_payment_id -> 409 Conflict
    resp_dup = client.post(
        "/api/v1/payments",
        json={
            "razorpay_payment_id": "pay_api_001",
            "amount": 79900,
        },
    )
    assert resp_dup.status_code == 409
    assert "already exists" in resp_dup.json()["detail"]

    # 4. Get by internal ID -> 200 OK
    resp_get = client.get(f"/api/v1/payments/{payment_id}")
    assert resp_get.status_code == 200
    assert resp_get.json()["razorpay_payment_id"] == "pay_api_001"

    # 5. Get by non-existent internal ID -> 404 Not Found
    assert client.get("/api/v1/payments/99999").status_code == 404

    # 6. Get by Razorpay payment ID -> 200 OK
    resp_rzp = client.get("/api/v1/payments/razorpay/pay_api_001")
    assert resp_rzp.status_code == 200
    assert resp_rzp.json()["id"] == payment_id

    # 7. Get by non-existent Razorpay ID -> 404 Not Found
    assert client.get("/api/v1/payments/razorpay/non_existent").status_code == 404

    # 8. List payments -> 200 OK
    resp_list = client.get("/api/v1/payments?status=failed")
    assert resp_list.status_code == 200
    list_data = resp_list.json()
    assert list_data["total"] >= 1
    assert any(p["id"] == payment_id for p in list_data["items"])

    # 9. Patch status -> 200 OK
    resp_patch = client.patch(
        f"/api/v1/payments/{payment_id}/status",
        json={"status": "captured"},
    )
    assert resp_patch.status_code == 200
    assert resp_patch.json()["status"] == "captured"


def test_revenue_api_lifecycle_and_conflicts(client):
    """Test revenue record endpoints and 1:1 constraints via API."""
    # Create payment first
    p_resp = client.post(
        "/api/v1/payments",
        json={
            "razorpay_payment_id": "pay_rev_api_001",
            "amount": 150000,
            "status": "failed",
        },
    )
    assert p_resp.status_code == 201
    payment_id = p_resp.json()["id"]

    # 1. Create revenue record -> 201 Created
    rev_resp = client.post(
        "/api/v1/revenue",
        json={
            "payment_id": payment_id,
            "status": "at_risk",
        },
    )
    assert rev_resp.status_code == 201
    rev_data = rev_resp.json()
    assert rev_data["payment_id"] == payment_id
    assert rev_data["gross_amount"] == 150000
    assert rev_data["recoverable_amount"] == 150000
    revenue_id = rev_data["id"]

    # 2. Duplicate revenue record for same payment -> 409 Conflict
    dup_resp = client.post(
        "/api/v1/revenue",
        json={"payment_id": payment_id},
    )
    assert dup_resp.status_code == 409

    # 3. Create for non-existent payment -> 404 Not Found
    assert client.post("/api/v1/revenue", json={"payment_id": 99999}).status_code == 404

    # 4. Get by revenue ID -> 200 OK
    assert client.get(f"/api/v1/revenue/{revenue_id}").status_code == 200

    # 5. Get by payment ID -> 200 OK
    assert client.get(f"/api/v1/revenue/payment/{payment_id}").status_code == 200

    # 6. Patch status -> 200 OK
    patch_resp = client.patch(
        f"/api/v1/revenue/{revenue_id}/status",
        json={"status": "recovered", "recoverable_amount": 0},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "recovered"
    assert patch_resp.json()["recoverable_amount"] == 0

    # 7. Post mark-at-risk -> 200 OK
    risk_resp = client.post(f"/api/v1/revenue/{revenue_id}/mark-at-risk")
    assert risk_resp.status_code == 200
    assert risk_resp.json()["status"] == "at_risk"
    assert risk_resp.json()["recoverable_amount"] == 150000


def test_recovery_api_case_and_actions(client):
    """Test recovery case management, state transitions, and actions."""
    # Setup payment and revenue
    p_resp = client.post(
        "/api/v1/payments",
        json={"razorpay_payment_id": "pay_rec_api_001", "amount": 250000},
    )
    payment_id = p_resp.json()["id"]
    r_resp = client.post(
        "/api/v1/revenue",
        json={"payment_id": payment_id, "status": "at_risk"},
    )
    revenue_id = r_resp.json()["id"]

    # 1. Create recovery case -> 201 Created
    case_resp = client.post(
        "/api/v1/recovery/cases",
        json={
            "revenue_record_id": revenue_id,
            "reason": "payment_failed_gateway_timeout",
            "priority": "urgent",
            "risk_status": "critical",
        },
    )
    assert case_resp.status_code == 201
    case_data = case_resp.json()
    assert case_data["current_state"] == "open"
    assert case_data["priority"] == "urgent"
    case_id = case_data["id"]

    # 2. List recovery cases -> 200 OK
    list_resp = client.get("/api/v1/recovery/cases?priority=urgent")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # 3. Valid state transition: open -> action_pending -> 200 OK
    patch_state_resp = client.patch(
        f"/api/v1/recovery/cases/{case_id}/state",
        json={"current_state": "action_pending"},
    )
    assert patch_state_resp.status_code == 200
    assert patch_state_resp.json()["current_state"] == "action_pending"

    # Close case
    client.patch(
        f"/api/v1/recovery/cases/{case_id}/state",
        json={"current_state": "closed"},
    )

    # 4. Invalid state transition: closed -> recovering -> 400 Bad Request
    invalid_trans_resp = client.patch(
        f"/api/v1/recovery/cases/{case_id}/state",
        json={"current_state": "recovering"},
    )
    assert invalid_trans_resp.status_code == 400
    assert "Cannot transition from 'closed' to 'recovering'" in invalid_trans_resp.json()["detail"]

    # 5. Create recovery action -> 201 Created
    action_resp = client.post(
        f"/api/v1/recovery/cases/{case_id}/actions",
        json={
            "action_type": "email_reminder",
            "channel": "email",
            "status": "scheduled",
        },
    )
    assert action_resp.status_code == 201
    action_data = action_resp.json()
    assert action_data["action_type"] == "email_reminder"
    action_id = action_data["id"]

    # 6. Update action status -> 200 OK
    update_act_resp = client.patch(
        f"/api/v1/recovery/actions/{action_id}/status",
        json={
            "status": "executed",
            "result": {"delivered": True, "message_id": "msg_001"},
        },
    )
    assert update_act_resp.status_code == 200
    assert update_act_resp.json()["status"] == "executed"
    assert update_act_resp.json()["result"]["delivered"] is True

    # 7. Get case by ID returns nested actions -> 200 OK
    get_case_resp = client.get(f"/api/v1/recovery/cases/{case_id}")
    assert get_case_resp.status_code == 200
    assert len(get_case_resp.json()["actions"]) == 1


def test_audit_api_and_swagger(client):
    """Test read-only audit log querying and Swagger OpenAPI documentation."""
    # Create an entity to trigger an audit log
    client.post(
        "/api/v1/payments",
        json={"razorpay_payment_id": "pay_audit_api_001", "amount": 3000},
    )

    # Query audit logs
    audit_resp = client.get("/api/v1/audit?entity_type=payment&action=payment_created")
    assert audit_resp.status_code == 200
    audit_data = audit_resp.json()
    assert audit_data["total"] >= 1
    assert all(a["entity_type"] == "payment" for a in audit_data["items"])

    # Verify OpenAPI documentation is accessible and contains new endpoints
    docs_resp = client.get("/docs")
    assert docs_resp.status_code == 200

    openapi_resp = client.get("/openapi.json")
    assert openapi_resp.status_code == 200
    paths = openapi_resp.json()["paths"]
    assert "/api/v1/payments" in paths
    assert "/api/v1/revenue" in paths
    assert "/api/v1/recovery/cases" in paths
    assert "/api/v1/audit" in paths
