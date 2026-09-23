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
    AdapterResult,
    BaseProviderAdapter,
    GitHubMockAdapter,
    InvalidAdapterConfigError,
    ProviderAdapterFactory,
    ProviderAuthenticationError,
    ProviderConnectionTimeoutError,
    ProviderIntegrationError,
    SlackMockAdapter,
    UnsupportedProviderError,
    get_provider_adapter,
    register_provider_adapter,
)




class AlternateMockAdapter(BaseProviderAdapter):
    """Test-only provider proving consumers can swap implementations."""

    async def provision_access(
        self,
        user_context: Any,
        role_or_scope: Any = None,
        **kwargs: Any,
    ) -> AdapterResult:
        return AdapterResult(
            success=True,
            status="provisioned",
            provider="alternate",
            external_id="alt-mock-001",
        )

    async def revoke_access(self, external_id: str, **kwargs: Any) -> AdapterResult:
        return AdapterResult(
            success=True,
            status="revoked",
            provider="alternate",
            external_id=str(external_id),
        )

    async def get_status(self) -> AdapterResult:
        return AdapterResult(success=True, status="healthy", provider="alternate")



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
    assert repeated.external_reference == success.external_reference
    revoke_res = await fresh_adapter.revoke_access("engineer@azm-nexus.com")
    assert isinstance(revoke_res, AdapterResult)
    assert revoke_res.success is True
    assert revoke_res.status == "revoked"
    assert bool(revoke_res) is True  # Deprecated boolean protocol
    print("[PASS] Provisioning is idempotent and revocation works across adapter instances")

    # Tenant isolation: identical identities in another tenant are independent.
    tenant_b_adapter = get_provider_adapter("github", tenant_b, {})
    tenant_b_access = await tenant_b_adapter.provision_access("engineer@azm-nexus.com", "read")
    assert tenant_b_access.metadata["tenant_id"] == tenant_b
    assert tenant_b_access.external_reference != success.external_reference
    assert (await get_provider_adapter("github", tenant_a, {}).revoke_access("engineer@azm-nexus.com")).success is False
    assert (await get_provider_adapter("github", tenant_b, {}).revoke_access("engineer@azm-nexus.com")).success is True
    print("[PASS] GitHub mock state is isolated by tenant")

    failing_adapter = get_provider_adapter("github", tenant_a, {"simulate_failure": True})
    failure = await failing_adapter.provision_access("blocked@azm-nexus.com", "read")
    assert isinstance(failure, AdapterResult)
    assert failure.success is False
    assert failure.status == "failed"
    assert failure.provider == "github"
    assert failure.error == "Simulated GitHub provisioning failure."
    print("[PASS] GitHub mock controlled failure/fallback path")

    register_provider_adapter("alternate", AlternateMockAdapter)
    swapped = get_provider_adapter("alternate", tenant_a, {})
    swapped_result = await swapped.provision_access("engineer@azm-nexus.com", "member")
    assert isinstance(swapped, BaseProviderAdapter)
    assert isinstance(swapped_result, AdapterResult)
    assert swapped_result.provider == "alternate"
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

    # Multi-provider conformance test: SlackMockAdapter
    assert ProviderAdapterFactory.is_supported("slack") is True
    slack_adapter = ProviderAdapterFactory.create_adapter("slack", tenant_a, {"workspace": "azm-ops"})
    assert isinstance(slack_adapter, SlackMockAdapter)
    slack_result = await slack_adapter.provision_access("lead@azm-nexus.com", "engineering-core")
    assert isinstance(slack_result, AdapterResult)
    assert slack_result.success is True
    assert slack_result.status == "provisioned"
    assert slack_result.provider == "slack"
    assert slack_result.external_reference.startswith("slack-user-")
    assert slack_result.metadata["channel"] == "engineering-core"

    # Deprecated mapping compatibility checks on AdapterResult
    assert slack_result["status"] == "provisioned"
    assert slack_result.get("provider") == "slack"
    assert bool(slack_result) is True
    assert slack_result.to_dict()["success"] is True

    # Multi-provider revocation
    slack_revoke = await slack_adapter.revoke_access("lead@azm-nexus.com")
    assert isinstance(slack_revoke, AdapterResult)
    assert slack_revoke.success is True
    assert slack_revoke.status == "revoked"
    print("[PASS] Multi-provider conformance verified (SlackMockAdapter & AdapterResult)")

    # Typed exceptions hierarchy verification
    assert issubclass(ProviderConnectionTimeoutError, ProviderIntegrationError)
    assert issubclass(ProviderAuthenticationError, ProviderIntegrationError)
    print("[PASS] Typed provider exceptions conform to ProviderIntegrationError hierarchy")

    # Directive Method Signatures: provision_access(user_context: dict) & revoke_access(external_id: str)
    ctx_res = await adapter.provision_access({
        "email": "directive.engineer@azm-nexus.com",
        "role": "admin",
        "user_id": "usr-001",
    })
    assert isinstance(ctx_res, AdapterResult)
    assert ctx_res.success is True
    assert ctx_res.status == "provisioned"
    assert ctx_res.external_id is not None
    assert ctx_res.external_reference == ctx_res.external_id
    assert ctx_res.error_message is None
    print("[PASS] Directive provision_access(user_context: dict) contract verified")

    # Directive Revocation by external_id handle
    ctx_revoke = await adapter.revoke_access(ctx_res.external_id)
    assert isinstance(ctx_revoke, AdapterResult)
    assert ctx_revoke.success is True
    assert ctx_revoke.status == "revoked"
    print("[PASS] Directive revoke_access(external_id: str) contract verified")

    # Directive Field Names: external_id and error_message + backward-compatible aliases
    field_test = AdapterResult(
        success=False,
        status="failed",
        provider="github",
        external_id="gh-ext-test-1",
        error_message="Test failure message",
    )
    assert field_test.external_id == "gh-ext-test-1"
    assert field_test.external_reference == "gh-ext-test-1"
    assert field_test.error_message == "Test failure message"
    assert field_test.error == "Test failure message"
    assert field_test["external_id"] == "gh-ext-test-1"
    assert field_test["external_reference"] == "gh-ext-test-1"
    assert field_test.get("error_message") == "Test failure message"
    assert field_test.get("error") == "Test failure message"
    print("[PASS] Directive primary fields (external_id, error_message) and legacy aliases verified")

    # Typed Exceptions: Active Fault Injection Verification
    timeout_adapter = get_provider_adapter("github", tenant_a, {"simulate_timeout": True})
    try:
        await timeout_adapter.provision_access({"email": "timeout.test@azm-nexus.com", "role": "write"})
    except ProviderConnectionTimeoutError as err:
        assert "timeout" in str(err).lower()
        print("[PASS] ProviderConnectionTimeoutError actively raised and caught")
    else:
        raise AssertionError("Expected ProviderConnectionTimeoutError was not raised.")

    auth_adapter = get_provider_adapter("github", tenant_a, {"simulate_auth_error": True})
    try:
        await auth_adapter.provision_access({"email": "auth.test@azm-nexus.com", "role": "write"})
    except ProviderAuthenticationError as err:
        assert "authentication" in str(err).lower() or "token" in str(err).lower()
        print("[PASS] ProviderAuthenticationError actively raised and caught")
    else:
        raise AssertionError("Expected ProviderAuthenticationError was not raised.")

    print("=" * 80)
    print("DWOP-011 VERIFICATION PASSED")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())

