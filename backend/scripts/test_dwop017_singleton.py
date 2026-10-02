"""DWOP-017: Scoped Singleton Pattern verification suite."""

from concurrent.futures import ThreadPoolExecutor
import os
import sys
from threading import Barrier
from typing import Any

from sqlalchemy import text

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.config import get_settings, settings
from app.core.database import SessionLocal
from app.integrations import (
    AdapterResult,
    BaseProviderAdapter,
    GitHubMockAdapter,
    ProviderAdapterFactory,
    SlackMockAdapter,
)


class ConcurrentRegistryAdapter(BaseProviderAdapter):
    """Minimal adapter used only to exercise concurrent registry access."""

    async def provision_access(self, user_context: Any, **kwargs: Any) -> AdapterResult:
        return AdapterResult(success=True, status="provisioned", provider="concurrent")

    async def revoke_access(self, external_id: str, **kwargs: Any) -> AdapterResult:
        return AdapterResult(success=True, status="revoked", provider="concurrent")

    async def get_status(self) -> AdapterResult:
        return AdapterResult(success=True, status="healthy", provider="concurrent")


def test_settings_are_process_scoped() -> None:
    assert get_settings() is get_settings()
    assert settings is get_settings()
    print("[PASS] Settings provider is process-scoped and legacy export is compatible")


def test_builtin_provider_registrations() -> None:
    assert ProviderAdapterFactory.is_supported("github") is True
    assert ProviderAdapterFactory.is_supported("slack") is True
    assert isinstance(ProviderAdapterFactory.create_adapter("github", "tenant-github", {}), GitHubMockAdapter)
    assert isinstance(ProviderAdapterFactory.create_adapter("slack", "tenant-slack", {}), SlackMockAdapter)
    print("[PASS] GitHub and Slack mock registrations remain available")


def test_registry_concurrency() -> None:
    provider_names = [f"concurrent-p07-{index}" for index in range(16)]
    barrier = Barrier(len(provider_names))

    def register_and_lookup(provider: str) -> bool:
        barrier.wait()
        ProviderAdapterFactory.register_provider(provider, ConcurrentRegistryAdapter)
        adapter = ProviderAdapterFactory.create_adapter(provider, "tenant-concurrent", {})
        return ProviderAdapterFactory.is_supported(provider) and isinstance(adapter, ConcurrentRegistryAdapter)

    with ThreadPoolExecutor(max_workers=len(provider_names)) as executor:
        assert all(executor.map(register_and_lookup, provider_names))
    print("[PASS] Provider registry registrations and lookups are concurrency-safe")


def test_adapter_instances_remain_tenant_scoped() -> None:
    tenant_a_first = ProviderAdapterFactory.create_adapter("github", "tenant-a", {"token": "tenant-a-token"})
    tenant_a_second = ProviderAdapterFactory.create_adapter("github", "tenant-a", {"token": "tenant-a-token"})
    tenant_b = ProviderAdapterFactory.create_adapter("github", "tenant-b", {"token": "tenant-b-token"})

    assert tenant_a_first is not tenant_a_second
    assert tenant_a_first is not tenant_b
    assert tenant_a_first.tenant_id == "tenant-a"
    assert tenant_b.tenant_id == "tenant-b"
    tenant_a_first.credentials["request_marker"] = "tenant-a-only"
    assert "request_marker" not in tenant_a_second.credentials
    assert "request_marker" not in tenant_b.credentials
    print("[PASS] Adapter instances and credentials remain isolated by construction scope")


def test_database_sessions_remain_request_scoped() -> None:
    first_session = SessionLocal()
    second_session = SessionLocal()
    try:
        assert first_session is not second_session
        first_session.close()
        assert second_session.execute(text("SELECT 1")).scalar_one() == 1
        next_request_session = SessionLocal()
        try:
            assert next_request_session is not first_session
            assert next_request_session is not second_session
        finally:
            next_request_session.close()
    finally:
        first_session.close()
        second_session.close()
    print("[PASS] Database sessions are new per request and never singleton instances")


def main() -> None:
    print("=" * 80)
    print("DWOP-017: SCOPED SINGLETON PATTERN VERIFICATION")
    print("=" * 80)
    test_settings_are_process_scoped()
    test_builtin_provider_registrations()
    test_registry_concurrency()
    test_adapter_instances_remain_tenant_scoped()
    test_database_sessions_remain_request_scoped()
    print("=" * 80)
    print("DWOP-017 VERIFICATION PASSED (5/5 scoped singleton suites green)")
    print("=" * 80)


if __name__ == "__main__":
    main()
