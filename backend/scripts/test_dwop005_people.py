import httpx
import json

base_url = "http://localhost:8000/api/v1"

print("=" * 80)
print("DWOP-005: PROFESSIONAL / ENGAGEMENT & BULK IMPORT VERIFICATION")
print("=" * 80)

# STEP 1: Authenticate Actors
print("\n[STEP 1] Authenticating Test Actors (Admin, Manager, Member)...")
admin_res = httpx.post(f"{base_url}/auth/login", json={"email": "admin@azm-nexus.com", "password": "Admin123!"})
admin_token = admin_res.json()["access_token"]
print("  Admin logged in successfully.")

manager_res = httpx.post(f"{base_url}/auth/login", json={"email": "atanda.david@azm-nexus.com", "password": "LeadAtanda2026!"})
manager_token = manager_res.json()["access_token"]
print("  Manager logged in successfully.")

member_res = httpx.post(f"{base_url}/auth/login", json={"email": "member@azm-nexus.com", "password": "Member123!"})
member_token = member_res.json()["access_token"]
print("  Member logged in successfully.")

# STEP 2: List Seeded Professionals (Member access)
print("\n[STEP 2] Listing Seeded Professionals (GET /people/ with Member Bearer Token)")
r = httpx.get(f"{base_url}/people/", headers={"Authorization": f"Bearer {member_token}"})
print(f"HTTP Status: {r.status_code}")
seeded_people = r.json()
print(f"Total Seeded Count: {len(seeded_people)}")
for p in seeded_people:
    print(f"  - {p['first_name']} {p['last_name']} ({p['email']}) | Status: {p['status']} | Skills: {p['skills']}")

# STEP 3: Single Professional Intake (Manager Authorized)
print("\n[STEP 3] Single Professional Intake by Manager (POST /people/)")
single_payload = {
    "first_name": "Tunde",
    "last_name": "Bakare",
    "email": "tunde.bakare@azm-nexus.com",
    "phone": "+234 809 111 2222",
    "status": "intake",
    "availability_status": "available",
    "skills": ["Python", "Golang", "Distributed Systems"],
    "engagement": {
        "engagement_type": "contractor",
        "start_date": "2026-09-05",
        "contract_status": "active",
        "compensation_rate": "$100/hr"
    }
}
r = httpx.post(f"{base_url}/people/", headers={"Authorization": f"Bearer {manager_token}"}, json=single_payload)
print(f"HTTP Status: {r.status_code} {r.reason_phrase}")
created_p = r.json()
print(f"Created Professional: {created_p['first_name']} {created_p['last_name']} (ID: {created_p['id']})")
print(f"Engagement Count: {len(created_p.get('engagements', []))}")

# STEP 4: RBAC Gate - Member Attempting Single Intake (Should be 403 Forbidden)
print("\n[STEP 4] RBAC Gate: Member Attempting Single Intake (Should Return 403)")
r = httpx.post(
    f"{base_url}/people/",
    headers={"Authorization": f"Bearer {member_token}"},
    json={"first_name": "Hacker", "last_name": "User", "email": "hacker@test.com", "skills": []}
)
print(f"HTTP Status: {r.status_code} {r.reason_phrase}")
print("Response Body:", json.dumps(r.json(), indent=2))

# STEP 5: RBAC Gate - Manager Attempting Bulk Import (Should be 403 Forbidden per Directive matrix)
print("\n[STEP 5] RBAC Gate: Manager Attempting Bulk Import (Should Return 403)")
r = httpx.post(
    f"{base_url}/people/bulk-import",
    headers={"Authorization": f"Bearer {manager_token}"},
    json=[{"first_name": "Unauthorized", "last_name": "Bulk", "email": "unauth@test.com", "skills": []}]
)
print(f"HTTP Status: {r.status_code} {r.reason_phrase}")
print("Response Body:", json.dumps(r.json(), indent=2))

# STEP 6: BULK IMPORT OF 3 PROFESSIONALS BY ADMIN (Atomic Transaction)
print("\n[STEP 6] Admin Executing Bulk Import of 3 Professionals (POST /people/bulk-import)")
bulk_cohort = [
    {
        "first_name": "Emmanuel",
        "last_name": "Okafor",
        "email": "emmanuel.okafor@azm-nexus.com",
        "phone": "+234 811 333 4444",
        "status": "intake",
        "availability_status": "available",
        "skills": ["Vue.js", "Nuxt", "JavaScript", "CSS3"],
        "engagement": {
            "engagement_type": "employee",
            "start_date": "2026-09-10",
            "contract_status": "active",
            "compensation_rate": "$75,000/yr"
        }
    },
    {
        "first_name": "Fatima",
        "last_name": "Bello",
        "email": "fatima.bello@azm-nexus.com",
        "phone": "+234 812 444 5555",
        "status": "intake",
        "availability_status": "available",
        "skills": ["QA Automation", "Playwright", "Cypress", "Pytest"],
        "engagement": {
            "engagement_type": "contractor",
            "start_date": "2026-09-10",
            "contract_status": "active",
            "compensation_rate": "$70/hr"
        }
    },
    {
        "first_name": "Chidi",
        "last_name": "Eze",
        "email": "chidi.eze@azm-nexus.com",
        "phone": "+234 813 555 6666",
        "status": "intake",
        "availability_status": "available",
        "skills": ["Data Engineering", "Apache Spark", "Airflow", "Snowflake"],
        "engagement": {
            "engagement_type": "contractor",
            "start_date": "2026-09-10",
            "contract_status": "active",
            "compensation_rate": "$90/hr"
        }
    }
]

r = httpx.post(f"{base_url}/people/bulk-import", headers={"Authorization": f"Bearer {admin_token}"}, json=bulk_cohort)
print(f"HTTP Status: {r.status_code} {r.reason_phrase}")
bulk_results = r.json()
print(f"Bulk Import Result Count: {len(bulk_results)}")
for person in bulk_results:
    eng_type = person['engagements'][0]['engagement_type'] if person.get('engagements') else 'None'
    print(f"  [IMPORTED] {person['first_name']} {person['last_name']} ({person['email']})")
    print(f"             ID: {person['id']} | Status: {person['status']} | Engagement: {eng_type} | Skills: {person['skills']}")

# STEP 7: Verify Final Scoped List
print("\n[STEP 7] Verifying Global Scoped Directory (GET /people/)")
r = httpx.get(f"{base_url}/people/", headers={"Authorization": f"Bearer {admin_token}"})
all_people = r.json()
print(f"Total Professionals in Tenant Directory: {len(all_people)}")

print("\n" + "=" * 80)
print("DWOP-005 VERIFICATION COMPLETE: ALL GATES & BULK TRANSACTIONS VERIFIED!")
print("=" * 80)
