import sys
import json
from fastapi.testclient import TestClient

sys.path.insert(0, ".")

from app.main import app

client = TestClient(app)
base_url = "/api/v1"

print("=" * 75)
print("DWOP-004 AUTHENTICATION BASELINE & RBAC VERIFICATION SUITE")
print("=" * 75)

# TEST 1: Admin Login
print("\n[TEST 1] Admin Login (admin@azm-nexus.com / Admin123!)")
r = client.post(f"{base_url}/auth/login", json={"email": "admin@azm-nexus.com", "password": "Admin123!"})
print(f"HTTP Status: {r.status_code}")
assert r.status_code == 200, f"Admin login failed: {r.text}"
admin_data = r.json()
admin_token = admin_data.get("access_token")
print(f"Token Received: {admin_token[:30]}...")
print(f"Claims Returned: user_id={admin_data.get('user_id')}, role={admin_data.get('role')}")

# TEST 2: Admin Profile (/auth/me)
print("\n[TEST 2] Admin Profile (GET /auth/me with Admin Bearer Token)")
r = client.get(f"{base_url}/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
print(f"HTTP Status: {r.status_code}")
assert r.status_code == 200
print("Profile Response:\n" + json.dumps(r.json(), indent=2))

# TEST 3: Admin Creating Department (Should SUCCEED with 201 Created or exist)
print("\n[TEST 3] Admin Mutation (POST /departments/ with Admin Bearer Token)")
dept_name = "Cloud Infrastructure & Verification"
r = client.post(
    f"{base_url}/departments/",
    headers={"Authorization": f"Bearer {admin_token}"},
    json={"name": dept_name},
)
print(f"HTTP Status: {r.status_code}")
assert r.status_code in (201, 409)
if r.status_code == 201:
    print("Created Department Response:\n" + json.dumps(r.json(), indent=2))
else:
    print("Department already exists in tenant.")

# TEST 4: Member Login
print("\n[TEST 4] Member Login (member@azm-nexus.com / Member123!)")
r = client.post(f"{base_url}/auth/login", json={"email": "member@azm-nexus.com", "password": "Member123!"})
print(f"HTTP Status: {r.status_code}")
assert r.status_code == 200
member_data = r.json()
member_token = member_data.get("access_token")
print(f"Token Received: {member_token[:30]}...")
print(f"Claims Returned: user_id={member_data.get('user_id')}, role={member_data.get('role')}")

# TEST 5: Member Profile (/auth/me)
print("\n[TEST 5] Member Profile (GET /auth/me with Member Bearer Token)")
r = client.get(f"{base_url}/auth/me", headers={"Authorization": f"Bearer {member_token}"})
print(f"HTTP Status: {r.status_code}")
assert r.status_code == 200
print("Profile Response:\n" + json.dumps(r.json(), indent=2))

# TEST 6: Member Read Access (Should SUCCEED with 200 OK)
print("\n[TEST 6] Member Read Access (GET /departments/ with Member Bearer Token)")
r = client.get(f"{base_url}/departments/", headers={"Authorization": f"Bearer {member_token}"})
print(f"HTTP Status: {r.status_code}")
assert r.status_code == 200
print(f"Departments visible to Member: {[d['name'] for d in r.json()]}")

# TEST 7: CRITICAL SECURITY AUDIT TEST - Member Mutation Blocked with 403 Forbidden
print("\n[TEST 7] SECURITY AUDIT: Member Mutation Blocked (POST /departments/ with Member Bearer Token)")
r = client.post(
    f"{base_url}/departments/",
    headers={"Authorization": f"Bearer {member_token}"},
    json={"name": "Unauthorized Department Attempt"},
)
print(f"HTTP Status: {r.status_code}")
assert r.status_code == 403
print("Response Body:")
print(json.dumps(r.json(), indent=2))

# TEST 8: Invalid Password Handling
print("\n[TEST 8] Invalid Password Attempt (admin@azm-nexus.com / BadPassword)")
r = client.post(f"{base_url}/auth/login", json={"email": "admin@azm-nexus.com", "password": "BadPassword"})
print(f"HTTP Status (Expected 401): {r.status_code}")
assert r.status_code == 401
print("Response Body:\n" + json.dumps(r.json(), indent=2))

print("\n" + "=" * 75)
print("ALL DWOP-004 SECURITY & RBAC TESTS PASSED WITH 100% ACCURACY!")
print("=" * 75)
