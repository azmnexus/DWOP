"""DWOP-011 Provider Adapter Framework verification.

Runs without a live API, database, GitHub token, or network connection.
"""
import asyncio
import os
import sys
from types import SimpleNamespace
from typing import Any, Dict

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.integrations import (
    BaseProviderAdapter,
    GitHubMockAdapter,
    InvalidAdapterConfigError,
    ProviderAdapterFactory,
    UnsupportedProviderError,
    get_provider_adapter,
    register_provider_adapter,
)




class AlternateMockAdapter(BaseProviderAdapter):
    """Test-only provider proving consumers can swap implementations."""

    async def provision_access(self, user_email: str, role_or_scope: str) -> Dict[str, Any]:
        return {"provider": "alternate", "status": "provisioned"}

    async def revoke_access(self, user_email: str) -> bool:
        return True

    async def get_status(self) -> Dict[str, Any]:
        return {"provider": "alternate", "health_status": "healthy"}


async def main() -> None:
    tenant_a = "tenant-demo-001"
    tenant_b = "tenant-demo-002"

    print("=" * 80)
    print("DWOP-011: PROVIDER ADAPTER FRAMEWORK VERIFICATION")
    print("=" * 80)

    assert ProviderAdapterFactory.is_supported("github") is True
    assert ProviderAdapterFactory.is_supported("unsupported") is False
    print("[PASS] Factory reports supported and unsupported providers safely")

    factory_adapter = ProviderAdapterFactory.create_adapter("github", tenant_a, {})
    assert isinstance(factory_adapter, GitHubMockAdapter)
    print("[PASS] Factory creates the GitHub sandbox adapter")

    integration = SimpleNamespace(
        provider="github",
        tenant_id=tenant_a,
        credentials_encrypted={},
        connection_status="connected",
    )
    integration_adapter = ProviderAdapterFactory.create_from_integration(integration)
    assert isinstance(integration_adapter, GitHubMockAdapter)
    assert integration_adapter.tenant_id == tenant_a
    print("[PASS] Factory binds an active Integration-like domain object to an adapter")

    disconnected_integration = SimpleNamespace(
        provider="github",
        tenant_id=tenant_a,
        credentials_encrypted={},
        connection_status="disconnected",
    )
    try:
        ProviderAdapterFactory.create_from_integration(disconnected_integration)
    except InvalidAdapterConfigError:
        pass
    else:
        raise AssertionError("Disconnected integrations must fail closed.")
    print("[PASS] Disconnected Integration-like objects fail closed")

    malformed_credentials_integration = SimpleNamespace(
        provider="github",
        tenant_id=tenant_a,
        credentials_encrypted=[],
        connection_status="connected",
    )
    try:
        ProviderAdapterFactory.create_from_integration(malformed_credentials_integration)
    except InvalidAdapterConfigError:
        pass
    else:
        raise AssertionError("Malformed integration credentials must fail closed.")
    print("[PASS] Malformed integration credentials fail closed")

    adapter = get_provider_adapter("github", tenant_a, {})
    assert isinstance(adapter, BaseProviderAdapter)
    assert isinstance(adapter, GitHubMockAdapter)

    success = await adapter.provision_access("Engineer@AZM-Nexus.com", "write")
    assert success["status"] == "provisioned"
    assert success["provider"] == "github"
    assert success["mode"] == "sandbox_mock"
    assert success["external_reference"]
    print("[PASS] GitHub mock successful provisioning path")

    health = await adapter.get_status()
    assert health["provider"] == "github"
    assert health["mode"] == "sandbox_mock"
    assert health["network_io"] is False
    print("[PASS] GitHub implementation is an explicit network-free sandbox mock")

    # Factory may construct fresh adapter objects across API requests. Mock state
    # must therefore remain visible within the same tenant during Sprint 0.
    fresh_adapter = get_provider_adapter("github", tenant_a, {})
    repeated = await fresh_adapter.provision_access("engineer@azm-nexus.com", "write")
    assert repeated["external_reference"] == success["external_reference"]
    assert await fresh_adapter.revoke_access("engineer@azm-nexus.com") is True
    print("[PASS] Provisioning is idempotent and revocation works across adapter instances")

    # Tenant isolation: identical identities in another tenant are independent.
    tenant_b_adapter = get_provider_adapter("github", tenant_b, {})
    tenant_b_access = await tenant_b_adapter.provision_access("engineer@azm-nexus.com", "read")
    assert tenant_b_access["tenant_id"] == tenant_b
    assert tenant_b_access["external_reference"] != success["external_reference"]
    assert await get_provider_adapter("github", tenant_a, {}).revoke_access("engineer@azm-nexus.com") is False
    assert await get_provider_adapter("github", tenant_b, {}).revoke_access("engineer@azm-nexus.com") is True
    print("[PASS] GitHub mock state is isolated by tenant")

    failing_adapter = get_provider_adapter("github", tenant_a, {"simulate_failure": True})
    failure = await failing_adapter.provision_access("blocked@azm-nexus.com", "read")
    assert failure["status"] == "failed"
    assert failure["provider"] == "github"
    assert failure["error"]
    print("[PASS] GitHub mock controlled failure/fallback path")

    register_provider_adapter("alternate", AlternateMockAdapter)
    swapped = get_provider_adapter("alternate", tenant_a, {})
    swapped_result = await swapped.provision_access("engineer@azm-nexus.com", "member")
    assert isinstance(swapped, BaseProviderAdapter)
    assert swapped_result["provider"] == "alternate"
    print("[PASS] Provider implementation can be swapped behind BaseProviderAdapter")

    try:
        ProviderAdapterFactory.create_adapter("unsupported", tenant_a, {})
    except UnsupportedProviderError as exc:
        assert isinstance(exc, ValueError)
        pass
    else:
        raise AssertionError("Unsupported provider should fail closed.")
    print("[PASS] Unknown providers fail closed with a ValueError-compatible domain error")

    compatibility_adapter = get_provider_adapter("github", tenant_a, {})
    assert isinstance(compatibility_adapter, GitHubMockAdapter)
    print("[PASS] Backwards-compatible get_provider_adapter still works")

    print("=" * 80)
    print("DWOP-011 VERIFICATION PASSED")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
