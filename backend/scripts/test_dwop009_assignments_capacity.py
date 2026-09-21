"""DWOP-009: Assignments & Capacity Engine Verification Suite.
Validates:
1. Multi-tenant project allocation with role and date tracking.
2. Dynamic availability status calculation (available -> partially_booked -> fully_booked).
3. Strict 100% capacity hard-stop ceiling enforcement across concurrent projects.
4. Assignment lifecycle updates and capacity release.
5. In-transaction atomic audit logging into the immutable audit timeline.
6. Role-Based Access Control (RBAC): Admin/Manager permitted, standard Member blocked with HTTP 403.
"""
import sys
import uuid
from datetime import date, timedelta
from fastapi.testclient import TestClient

# Ensure backend package can be imported
sys.path.insert(0, ".")

from app.main import app
from app.core.database import SessionLocal
from app.models.assignment import Assignment
from app.models.talent import Professional, AvailabilityStatus

client = TestClient(app)


def test_dwop009_capacity_engine():
    print("=" * 80)
    print("DWOP-009: ASSIGNMENTS & CAPACITY ENGINE VERIFICATION")
    print("=" * 80)

    # -------------------------------------------------------------------------
    # [STEP 1] Authenticate Users (Admin, Manager, Member)
    # -------------------------------------------------------------------------
    print("\n[STEP 1] Authenticating Test Actors (Admin, Manager, Member)...")
    admin_login = client.post("/api/v1/auth/login", data={"username": "admin@azm-nexus.com", "password": "Admin123!"})
    assert admin_login.status_code == 200, f"Admin login failed: {admin_login.text}"
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    print("  [PASS] Admin authenticated.")

    mgr_login = client.post("/api/v1/auth/login", data={"username": "atanda.david@azm-nexus.com", "password": "LeadAtanda2026!"})
    assert mgr_login.status_code == 200, f"Manager login failed: {mgr_login.text}"
    mgr_token = mgr_login.json()["access_token"]
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}
    print("  [PASS] Manager authenticated.")

    member_login = client.post("/api/v1/auth/login", data={"username": "member@azm-nexus.com", "password": "Member123!"})
    assert member_login.status_code == 200, f"Member login failed: {member_login.text}"
    member_token = member_login.json()["access_token"]
    member_headers = {"Authorization": f"Bearer {member_token}"}
    print("  [PASS] Member authenticated.")

    # -------------------------------------------------------------------------
    # [STEP 2] Fetch Professional (Jane Doe) & Verify Initial Baseline
    # -------------------------------------------------------------------------
    print("\n[STEP 2] Fetching Candidate Professional (Jane Doe)...")
    people_res = client.get("/api/v1/people", headers=admin_headers)
    assert people_res.status_code == 200
    people = people_res.json()
    jane = next((p for p in people if p["email"] == "jane.doe@azm-nexus.com"), None)
    assert jane is not None, "Jane Doe professional record not found in seed."
    jane_id = jane["id"]
    print(f"  [PASS] Jane Doe located: ID={jane_id}, Initial Status={jane['status']}")

    # Clean up any existing assignments for Jane Doe to start with fresh baseline
    db = SessionLocal()
    try:
        db.query(Assignment).filter(Assignment.professional_id == uuid.UUID(jane_id)).delete()
        prof_obj = db.query(Professional).filter(Professional.id == uuid.UUID(jane_id)).first()
        if prof_obj:
            prof_obj.availability_status = AvailabilityStatus.available
        db.commit()
    finally:
        db.close()

    # Verify baseline availability
    prof_cap = client.get(f"/api/v1/assignments/capacity/professionals/{jane_id}", headers=admin_headers)
    assert prof_cap.status_code == 200
    baseline_data = prof_cap.json()
    assert baseline_data["total_allocated_capacity_pct"] == 0, f"Expected 0% baseline, got {baseline_data['total_allocated_capacity_pct']}%"
    assert baseline_data["availability_status"] == "available"
    print("  [PASS] Jane Doe baseline capacity confirmed at 0% (Status: available).")

    # -------------------------------------------------------------------------
    # [STEP 3] Ensure Two Delivery Projects Exist for Concurrent Allocation
    # -------------------------------------------------------------------------
    print("\n[STEP 3] Ensuring Projects Exist for Concurrent Allocation...")
    projects_res = client.get("/api/v1/assignments/projects", headers=admin_headers)
    assert projects_res.status_code == 200
    projects = projects_res.json()
    proj1 = next((p for p in projects if p["code"] == "DWOP-CORE"), None)
    assert proj1 is not None, "Project DWOP-CORE not found."
    proj1_id = proj1["id"]

    proj2 = next((p for p in projects if p["code"] == "DWOP-MOB"), None)
    if not proj2:
        create_p2 = client.post(
            "/api/v1/assignments/projects",
            json={
                "name": "DWOP Mobile Workforce Experience",
                "code": "DWOP-MOB",
                "status": "active",
                "start_date": str(date.today()),
                "target_end_date": str(date.today() + timedelta(days=90)),
            },
            headers=admin_headers,
        )
        assert create_p2.status_code == 201
        proj2 = create_p2.json()
    proj2_id = proj2["id"]
    print(f"  [PASS] Project 1: DWOP-CORE ({proj1_id})")
    print(f"  [PASS] Project 2: DWOP-MOB ({proj2_id})")

    # -------------------------------------------------------------------------
    # [STEP 4] First Allocation: 50% Capacity -> partially_booked
    # -------------------------------------------------------------------------
    print("\n[STEP 4] Allocating 50% Capacity on Project 1 (Manager action)...")
    alloc1_payload = {
        "professional_id": jane_id,
        "project_id": proj1_id,
        "role_on_project": "Lead Backend Architect",
        "capacity_percentage": 50,
        "start_date": str(date.today()),
        "end_date": str(date.today() + timedelta(days=60)),
    }
    alloc1_res = client.post("/api/v1/assignments/allocate", json=alloc1_payload, headers=mgr_headers)
    assert alloc1_res.status_code == 201, f"Allocation 1 failed: {alloc1_res.text}"
    alloc1 = alloc1_res.json()
    alloc1_id = alloc1["id"]
    assert alloc1["capacity_percentage"] == 50
    assert alloc1["status"] == "active"
    assert alloc1["project_code"] == "DWOP-CORE"
    print(f"  [PASS] Allocation 1 created. ID={alloc1_id}, Capacity=50%")

    # Check Jane's availability updated to partially_booked
    jane_cap1 = client.get(f"/api/v1/assignments/capacity/professionals/{jane_id}", headers=mgr_headers).json()
    assert jane_cap1["total_allocated_capacity_pct"] == 50
    assert jane_cap1["remaining_capacity_pct"] == 50
    assert jane_cap1["availability_status"] == "partially_booked"
    print("  [PASS] Availability dynamically transitioned to 'partially_booked' (50% allocated, 50% remaining).")

    # -------------------------------------------------------------------------
    # [STEP 5] Second Allocation: Additional 50% -> fully_booked (100% Aggregate)
    # -------------------------------------------------------------------------
    print("\n[STEP 5] Allocating Concurrent 50% Capacity on Project 2 (Manager action)...")
    alloc2_payload = {
        "professional_id": jane_id,
        "project_id": proj2_id,
        "role_on_project": "Mobile Backend Sync Lead",
        "capacity_percentage": 50,
        "start_date": str(date.today()),
        "end_date": str(date.today() + timedelta(days=45)),
    }
    alloc2_res = client.post("/api/v1/assignments/allocate", json=alloc2_payload, headers=mgr_headers)
    assert alloc2_res.status_code == 201, f"Allocation 2 failed: {alloc2_res.text}"
    alloc2 = alloc2_res.json()
    alloc2_id = alloc2["id"]
    assert alloc2["capacity_percentage"] == 50
    assert alloc2["status"] == "active"
    print(f"  [PASS] Allocation 2 created. ID={alloc2_id}, Capacity=50%")

    # Check Jane's availability updated to fully_booked
    jane_cap2 = client.get(f"/api/v1/assignments/capacity/professionals/{jane_id}", headers=mgr_headers).json()
    assert jane_cap2["total_allocated_capacity_pct"] == 100
    assert jane_cap2["remaining_capacity_pct"] == 0
    assert jane_cap2["availability_status"] == "fully_booked"
    print("  [PASS] Availability dynamically transitioned to 'fully_booked' (100% aggregate allocation, 0% remaining).")

    # -------------------------------------------------------------------------
    # [STEP 6] CAPACITY HARD-STOP ENFORCEMENT (Over 100% Ceiling)
    # -------------------------------------------------------------------------
    print("\n[STEP 6] TESTING 100% CAPACITY HARD-STOP ENFORCEMENT...")
    excess_payload = {
        "professional_id": jane_id,
        "project_id": proj1_id,
        "role_on_project": "Platform Consultant",
        "capacity_percentage": 10,
        "start_date": str(date.today()),
    }
    excess_res = client.post("/api/v1/assignments/allocate", json=excess_payload, headers=mgr_headers)
    assert excess_res.status_code == 400, f"Expected HTTP 400 Bad Request, got {excess_res.status_code}: {excess_res.text}"
    err_detail = excess_res.json()["detail"]
    assert "Capacity limit exceeded" in err_detail
    assert "currently has 100% active allocation" in err_detail
    assert "exceeding the maximum allowed 100% threshold" in err_detail
    print(f"  [PASS] 100% Capacity Ceiling Enforced: HTTP 400 returned.")
    print(f"         Rejection Detail: \"{err_detail}\"")

    # -------------------------------------------------------------------------
    # [STEP 7] Platform-Wide Capacity Overview Inspection
    # -------------------------------------------------------------------------
    print("\n[STEP 7] Inspecting Tenant-Wide Capacity Overview...")
    overview_res = client.get("/api/v1/assignments/capacity", headers=admin_headers)
    assert overview_res.status_code == 200
    overview = overview_res.json()
    assert overview["fully_booked_headcount"] >= 1
    assert overview["total_active_allocations"] >= 2
    assert overview["average_utilization_pct"] > 0
    print(f"  [PASS] Overview Verified: Active Allocations={overview['total_active_allocations']}, "
          f"Fully Booked Headcount={overview['fully_booked_headcount']}, "
          f"Avg Utilization={overview['average_utilization_pct']}%")

    # -------------------------------------------------------------------------
    # [STEP 8] Assignment Lifecycle Update & Capacity Release
    # -------------------------------------------------------------------------
    print("\n[STEP 8] Updating Assignment Lifecycle: Completing Allocation 1...")
    update_res = client.patch(
        f"/api/v1/assignments/{alloc1_id}",
        json={"status": "completed"},
        headers=mgr_headers,
    )
    assert update_res.status_code == 200
    updated_alloc = update_res.json()
    assert updated_alloc["status"] == "completed"

    # Jane's capacity should drop back from 100% to 50%, transitioning from fully_booked to partially_booked
    jane_cap3 = client.get(f"/api/v1/assignments/capacity/professionals/{jane_id}", headers=mgr_headers).json()
    assert jane_cap3["total_allocated_capacity_pct"] == 50
    assert jane_cap3["remaining_capacity_pct"] == 50
    assert jane_cap3["availability_status"] == "partially_booked"
    print("  [PASS] Allocation 1 marked 'completed'. Jane Doe released back to 'partially_booked' (50% remaining).")

    # -------------------------------------------------------------------------
    # [STEP 9] Immutable Audit Ledger Verification (Atomic in Transaction)
    # -------------------------------------------------------------------------
    print("\n[STEP 9] Verifying Immutable Audit Events for Capacity Actions...")
    audit_res = client.get("/api/v1/audit/logs?target_type=Assignment", headers=admin_headers)
    assert audit_res.status_code == 200
    audit_events = audit_res.json()
    assert len(audit_events) >= 3, f"Expected at least 3 Assignment audit events, got {len(audit_events)}"

    actions = [e["action"] for e in audit_events]
    assert "assignment.allocated" in actions
    assert "assignment.updated" in actions

    allocated_event = next(e for e in audit_events if e["action"] == "assignment.allocated")
    assert allocated_event["metadata"]["capacity_percentage"] == 50
    assert allocated_event["metadata"]["professional_id"] == jane_id
    print(f"  [PASS] Verified 'assignment.allocated' audit event logged in transaction.")
    print(f"         Metadata: {allocated_event['metadata']}")

    updated_event = next(e for e in audit_events if e["action"] == "assignment.updated")
    assert updated_event["metadata"]["new_status"] == "completed"
    print(f"  [PASS] Verified 'assignment.updated' audit event logged in transaction.")
    print(f"         Metadata: {updated_event['metadata']}")

    # -------------------------------------------------------------------------
    # [STEP 10] Security Audit: Member RBAC Block
    # -------------------------------------------------------------------------
    print("\n[STEP 10] Testing RBAC: Standard Member Mutating Allocation...")
    member_attempt = client.post("/api/v1/assignments/allocate", json=alloc1_payload, headers=member_headers)
    assert member_attempt.status_code == 403, f"Expected HTTP 403 Forbidden, got {member_attempt.status_code}"
    print(f"  [PASS] Standard member blocked with HTTP 403: {member_attempt.json()['detail']}")

    print("\n" + "=" * 80)
    print("DWOP-009 VERIFICATION PASSED: ASSIGNMENTS & CAPACITY ENGINE FULLY FUNCTIONAL")
    print("=" * 80)


if __name__ == "__main__":
    test_dwop009_capacity_engine()
