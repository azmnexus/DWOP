"""DWOP-012 safe GitHub mock POC: success plus failure/fallback."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.integrations import get_provider_adapter


async def main() -> None:
    tenant_id = "dwop-poc-tenant"

    success_adapter = get_provider_adapter("github", tenant_id, {})
    success = await success_adapter.provision_access("poc-success@example.test", "write")
    assert success["provider"] == "github"
    assert success["mode"] == "sandbox_mock"
    assert success["status"] == "provisioned"
    assert success["external_reference"]
    print("[PASS] GitHub mock POC successful path -> provisioned")

    failure_adapter = get_provider_adapter(
        "github", tenant_id, {"simulate_failure": True}
    )
    failure = await failure_adapter.provision_access("poc-failure@example.test", "read")
    assert failure["provider"] == "github"
    assert failure["mode"] == "sandbox_mock"
    assert failure["status"] == "failed"
    assert failure["external_reference"] is None
    assert failure["error"]
    print("[PASS] GitHub mock POC failure path -> explicit failure, no access granted")

    health = await success_adapter.get_status()
    assert health["network_io"] is False
    print("[PASS] POC is explicitly sandbox-only with no network I/O")

    print("DWOP-012 VERIFICATION PASSED")


if __name__ == "__main__":
    asyncio.run(main())
