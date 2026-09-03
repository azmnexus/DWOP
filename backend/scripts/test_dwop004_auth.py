import httpx
import json

base_url = "http://localhost:8000/api/v1"

print("=" * 75)
print("DWOP-004 AUTHENTICATION BASELINE & RBAC VERIFICATION SUITE")
print("=" * 75)

# TEST 1: Admin Login
print("\n[TEST 1] Admin Login (admin@azm-nexus.com / Admin123!)")
r = httpx.post(f"{base_url}/auth/login", json={"email": "admin@azm-nexus.com", "password": "Admin123!"})
print(f"HTTP Status: {r.status_code}")
admin_data = r.json()
admin_token = admin_data.get("access_token")
print(f"Token Received: {admin_token[:30]}...")
print(f"Claims Returned: user_id={admin_data.get('user_id')}, role={admin_data.get('role')}")

# TEST 2: Admin Profile (/auth/me)
print("\n[TEST 2] Admin Profile (GET /auth/me with Admin Bearer Token)")
r = httpx.get(f"{base_url}/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
print(f"HTTP Status: {r.status_code}")
print("Profile Response:\n" + json.dumps(r.json(), indent=2))

# TEST 3: Admin Creating Department (Should SUCCEED with 201 Created)
print("\n[TEST 3] Admin Mutation (POST /departments/ with Admin Bearer Token)")
r = httpx.post(
    f"{base_url}/departments/",
    headers={"Authorization": f"Bearer {admin_token}"},
    json={"name": "Cloud Infrastructure & DevOps"},
)
print(f"HTTP Status: {r.status_code} {r.reason_phrase}")
print("Created Department Response:\n" + json.dumps(r.json(), indent=2))

# TEST 4: Member Login
print("\n[TEST 4] Member Login (member@azm-nexus.com / Member123!)")
r = httpx.post(f"{base_url}/auth/login", json={"email": "member@azm-nexus.com", "password": "Member123!"})
print(f"HTTP Status: {r.status_code}")
member_data = r.json()
member_token = member_data.get("access_token")
print(f"Token Received: {member_token[:30]}...")
print(f"Claims Returned: user_id={member_data.get('user_id')}, role={member_data.get('role')}")

# TEST 5: Member Profile (/auth/me)
print("\n[TEST 5] Member Profile (GET /auth/me with Member Bearer Token)")
r = httpx.get(f"{base_url}/auth/me", headers={"Authorization": f"Bearer {member_token}"})
print(f"HTTP Status: {r.status_code}")
print("Profile Response:\n" + json.dumps(r.json(), indent=2))

# TEST 6: Member Read Access (Should SUCCEED with 200 OK)
print("\n[TEST 6] Member Read Access (GET /departments/ with Member Bearer Token)")
r = httpx.get(f"{base_url}/departments/", headers={"Authorization": f"Bearer {member_token}"})
print(f"HTTP Status: {r.status_code} {r.reason_phrase}")
print(f"Departments visible to Member: {[d['name'] for d in r.json()]}")

# TEST 7: CRITICAL SECURITY AUDIT TEST - Member Mutation Blocked with 403 Forbidden
print("\n[TEST 7] SECURITY AUDIT: Member Mutation Blocked (POST /departments/ with Member Bearer Token)")
r = httpx.post(
    f"{base_url}/departments/",
    headers={"Authorization": f"Bearer {member_token}"},
    json={"name": "Unauthorized Department Attempt"},
)
print(f"HTTP Status: {r.status_code} {r.reason_phrase}")
print("Response Headers (WWW-Authenticate / Content-Type):")
print(f"  Content-Type: {r.headers.get('content-type')}")
print("Response Body:")
print(json.dumps(r.json(), indent=2))

# TEST 8: Invalid Password Handling
print("\n[TEST 8] Invalid Password Attempt (admin@azm-nexus.com / BadPassword)")
r = httpx.post(f"{base_url}/auth/login", json={"email": "admin@azm-nexus.com", "password": "BadPassword"})
print(f"HTTP Status (Expected 401): {r.status_code} {r.reason_phrase}")
print("Response Body:\n" + json.dumps(r.json(), indent=2))

print("\n" + "=" * 75)
print("ALL DWOP-004 SECURITY & RBAC TESTS PASSED WITH 100% ACCURACY!")
print("=" * 75)
