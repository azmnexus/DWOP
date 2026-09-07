"""DWOP-013: Immutable Audit Service & Activity Timeline Verification Suite.
Validates:
1. Triggering core actions (auth login, bulk import, onboarding run, access request)
2. Verifying all 4 events appear in GET /api/v1/audit/logs
3. Verifying correct actor_user_id and target_type mappings
4. Verifying reverse-chronological ordering (newest first)
5. Verifying query filtering (by action, target_type)
6. Verifying strict RBAC (Members blocked with 403 Forbidden)
"""
import os
import sys
import uuid
from datetime import date

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)
base_url = "/api/v1"


def main():
    print("=" * 80)
    print("DWOP-013: IMMUTABLE AUDIT SERVICE & TIMELINE VERIFICATION")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # STEP 1: Admin Login -> Emits 'auth.login_successful'
    # -------------------------------------------------------------------------
    print("\n[STEP 1] Admin Authentication -> Emits 'auth.login_successful'")
    login_res = client.post(
        f"{base_url}/auth/login",
        json={"email": "admin@azm-nexus.com", "password": "Admin123!"},
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    admin_data = login_res.json()
    admin_token = admin_data["access_token"]
    admin_id = admin_data["user_id"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print(f"  [PASS] Admin logged in. User ID: {admin_id}")

    # Also login a Member for RBAC security check
    member_login = client.post(
        f"{base_url}/auth/login",
        json={"email": "member@azm-nexus.com", "password": "Member123!"},
    )
    assert member_login.status_code == 200
    member_token = member_login.json()["access_token"]
    member_headers = {"Authorization": f"Bearer {member_token}"}

    # -------------------------------------------------------------------------
    # STEP 2: Atomic Bulk Import -> Emits 'professional.bulk_imported'
    # -------------------------------------------------------------------------
    print("\n[STEP 2] Atomic Bulk Import -> Emits 'professional.bulk_imported'")
    suffix = uuid.uuid4().hex[:6]
    cohort_payload = [
        {
            "first_name": "AuditDev1",
            "last_name": f"Test{suffix}",
            "email": f"audit.dev1.{suffix}@azm-nexus.com",
            "phone": "+1 555-0101",
            "status": "intake",
            "availability_status": "available",
            "skills": ["Python", "FastAPI"],
            "engagement": {
                "engagement_type": "employee",
                "start_date": str(date.today()),
                "contract_status": "active",
                "compensation_rate": "$100,000",
            },
        },
        {
            "first_name": "AuditDev2",
            "last_name": f"Test{suffix}",
            "email": f"audit.dev2.{suffix}@azm-nexus.com",
            "phone": "+1 555-0102",
            "status": "intake",
            "availability_status": "available",
            "skills": ["React", "TypeScript"],
            "engagement": {
                "engagement_type": "contractor",
                "start_date": str(date.today()),
                "contract_status": "active",
                "compensation_rate": "$90/hr",
            },
        },
    ]
    bulk_res = client.post(
        f"{base_url}/people/bulk-import",
        headers=admin_headers,
        json=cohort_payload,
    )
    assert bulk_res.status_code == 201, f"Bulk import failed: {bulk_res.text}"
    created_cohort = bulk_res.json()
    prof1_id = created_cohort[0]["id"]
    print(f"  [PASS] Bulk import created 2 professionals. Candidate 1 ID: {prof1_id}")

    # -------------------------------------------------------------------------
    # STEP 3: Instantiate Onboarding Run -> Emits 'onboarding_run.created'
    # -------------------------------------------------------------------------
    print("\n[STEP 3] Start Onboarding Run -> Emits 'onboarding_run.created'")
    templates_res = client.get(f"{base_url}/onboarding/templates", headers=admin_headers)
    assert templates_res.status_code == 200
    templates = templates_res.json()
    assert len(templates) > 0, "No onboarding templates found in tenant."
    template_id = templates[0]["id"]

    run_payload = {
        "professional_id": prof1_id,
        "template_id": template_id,
    }
    run_res = client.post(
        f"{base_url}/onboarding/runs",
        headers=admin_headers,
        json=run_payload,
    )
    assert run_res.status_code == 201, f"Onboarding run start failed: {run_res.text}"
    run_id = run_res.json()["id"]
    print(f"  [PASS] Onboarding run created. Run ID: {run_id}")

    # -------------------------------------------------------------------------
    # STEP 4: Submit Access Request -> Emits 'access_request.created'
    # -------------------------------------------------------------------------
    print("\n[STEP 4] Submit Access Request -> Emits 'access_request.created'")
    # Get seeded integration
    integrations_res = client.get(f"{base_url}/integrations/providers", headers=admin_headers)
    # If endpoint exists or query DB for integration
    # Let's lookup integration via access service or direct DB lookup
    from app.core.database import SessionLocal
    from app.models.access import Integration
    db = SessionLocal()
    try:
        gh_int = db.query(Integration).first()
        assert gh_int is not None, "Seeded integration not found in database."
        integration_id = str(gh_int.id)
    finally:
        db.close()

    access_payload = {
        "professional_id": prof1_id,
        "integration_id": integration_id,
        "access_type": "repository",
        "role_or_scope": "write",
    }
    access_res = client.post(
        f"{base_url}/access/requests",
        headers=admin_headers,
        json=access_payload,
    )
    assert access_res.status_code == 201, f"Access request creation failed: {access_res.text}"
    access_id = access_res.json()["id"]
    print(f"  [PASS] Access request created. Ticket ID: {access_id}")

    # -------------------------------------------------------------------------
    # STEP 5: Verify Audit Timeline API (GET /api/v1/audit/logs)
    # -------------------------------------------------------------------------
    print("\n[STEP 5] Reading Audit Timeline (GET /api/v1/audit/logs)")
    audit_res = client.get(
        f"{base_url}/audit/logs?limit=50",
        headers=admin_headers,
    )
    assert audit_res.status_code == 200, f"Audit query failed: {audit_res.text}"
    events = audit_res.json()
    print(f"  Total Timeline Events Retrieved: {len(events)}")
    assert len(events) >= 4, f"Expected at least 4 events, got {len(events)}"

    # Check that timestamps are in descending order
    timestamps = [e["timestamp"] for e in events]
    assert timestamps == sorted(timestamps, reverse=True), "Events are not in descending chronological order!"
    print("  [PASS] Timeline is sorted in reverse-chronological order (newest first).")

    # Verify 1: auth.login_successful
    login_events = [e for e in events if e["action"] == "auth.login_successful" and e["target_id"] == admin_id]
    assert len(login_events) >= 1, "Missing 'auth.login_successful' audit event for current admin!"
    login_event = login_events[0]
    assert login_event["actor_user_id"] == admin_id
    assert login_event["target_type"] == "User"
    print(f"  [PASS] Verified 'auth.login_successful': Actor={login_event['actor_user_id']}, TargetType={login_event['target_type']}")

    # Verify 2: professional.bulk_imported
    bulk_events = [e for e in events if e["action"] == "professional.bulk_imported" and e["target_id"] == prof1_id]
    assert len(bulk_events) >= 1, "Missing 'professional.bulk_imported' audit event for current cohort!"
    bulk_event = bulk_events[0]
    assert bulk_event["actor_user_id"] == admin_id
    assert bulk_event["target_type"] == "Professional"
    assert bulk_event["metadata"]["count"] == 2
    print(f"  [PASS] Verified 'professional.bulk_imported': Actor={bulk_event['actor_user_id']}, TargetType={bulk_event['target_type']}, CohortCount=2")

    # Verify 3: onboarding_run.created
    run_events = [e for e in events if e["action"] == "onboarding_run.created" and e["target_id"] == run_id]
    assert len(run_events) >= 1, "Missing 'onboarding_run.created' audit event for current run!"
    run_event = run_events[0]
    assert run_event["actor_user_id"] == admin_id
    assert run_event["target_type"] == "OnboardingRun"
    assert run_event["target_id"] == run_id
    print(f"  [PASS] Verified 'onboarding_run.created': Actor={run_event['actor_user_id']}, TargetType={run_event['target_type']}, TargetID={run_event['target_id']}")

    # Verify 4: access_request.created
    access_events = [e for e in events if e["action"] == "access_request.created" and e["target_id"] == access_id]
    assert len(access_events) >= 1, "Missing 'access_request.created' audit event for current request!"
    access_event = access_events[0]
    assert access_event["actor_user_id"] == admin_id
    assert access_event["target_type"] == "access_request"
    assert access_event["target_id"] == access_id
    print(f"  [PASS] Verified 'access_request.created': Actor={access_event['actor_user_id']}, TargetType={access_event['target_type']}, TargetID={access_event['target_id']}")

    # -------------------------------------------------------------------------
    # STEP 6: Filtered Queries & Export
    # -------------------------------------------------------------------------
    print("\n[STEP 6] Testing Audit Query Filtering & Export Endpoint")
    # Filter by target_type="OnboardingRun"
    filtered_run = client.get(
        f"{base_url}/audit/logs?target_type=OnboardingRun",
        headers=admin_headers,
    )
    assert filtered_run.status_code == 200
    for e in filtered_run.json():
        assert e["target_type"] == "OnboardingRun"
    print("  [PASS] Target type filter '?target_type=OnboardingRun' successfully scoped.")

    # Filter by action="professional.bulk_imported"
    filtered_bulk = client.get(
        f"{base_url}/audit/logs?action=professional.bulk_imported",
        headers=admin_headers,
    )
    assert filtered_bulk.status_code == 200
    for e in filtered_bulk.json():
        assert e["action"] == "professional.bulk_imported"
    print("  [PASS] Action filter '?action=professional.bulk_imported' successfully scoped.")

    # Export endpoint
    export_res = client.get(f"{base_url}/audit/export", headers=admin_headers)
    assert export_res.status_code == 200
    export_data = export_res.json()
    assert export_data["status"] == "export_ready"
    assert export_data["total_events"] >= 4
    print(f"  [PASS] Audit export endpoint confirmed operational (Total: {export_data['total_events']})")

    # -------------------------------------------------------------------------
    # STEP 7: Security Audit Check (RBAC: Member Access must return 403 Forbidden)
    # -------------------------------------------------------------------------
    print("\n[STEP 7] SECURITY AUDIT: Member Access to Global Audit Timeline")
    member_audit_res = client.get(
        f"{base_url}/audit/logs",
        headers=member_headers,
    )
    assert member_audit_res.status_code == 403, f"Expected 403 Forbidden, got {member_audit_res.status_code}"
    print(f"  [PASS] Standard member blocked with HTTP 403 Forbidden: '{member_audit_res.json()['detail']}'")

    print("\n" + "=" * 80)
    print("DWOP-013 VERIFICATION PASSED: AUDIT SERVICE & TIMELINE FULLY FUNCTIONAL")
    print("=" * 80)


if __name__ == "__main__":
    main()
