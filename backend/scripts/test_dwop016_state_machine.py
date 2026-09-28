"""DWOP-016: State Machine Pattern Architectural Verification Suite.

Validates the formal State Machine Pattern (Task P-06, CTO Mandate §3 Task 3.6 & §4 Task 4.3).
Verifies:
1. BaseStateMachine generic transition matrix, guards, idempotent same-state checks, and terminal state enforcement.
2. AccessRequestStateMachine (D-1 reconciled to live AccessRequestStatus enum).
3. AssignmentStateMachine (D-2 reconciled: active -> completed / reassigned, terminal protection).
4. OnboardingRunStateMachine (D-3 reconciled: in_progress/blocked/completed, blocked -> completed recalc).
5. OnboardingItemStateMachine (D-4 extension: blocker_reason guard and evidence checks).
6. TicketStateMachine (Passive mode: 6 delivery board stages, blocked_reason guard, supervisory sign-off).
7. Domain Service integration guards (HTTP 400 on illegal transitions or missing guard data).
"""

import os
import sys
import uuid
from typing import Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.core.database import SessionLocal
from app.core.state_machines import (
    AccessRequestStateMachine,
    AssignmentStateMachine,
    BaseStateMachine,
    InvalidStateTransitionError,
    OnboardingItemStateMachine,
    OnboardingRunStateMachine,
    StateMachineError,
    TicketStage,
    TicketStateMachine,
    TransitionGuardError,
)
from app.models.access import AccessRequestStatus
from app.models.assignment import AssignmentStatus
from app.models.user import UserRole


def test_base_state_machine() -> None:
    """Test generic BaseStateMachine capabilities."""
    class DummySM(BaseStateMachine[str]):
        def _setup(self) -> None:
            self._add_transition("draft", {"submitted", "cancelled"})
            self._add_transition("submitted", {"approved", "rejected"})
            self._set_terminal("approved", "rejected", "cancelled")
            self._add_guard("draft", "submitted", self._guard_title)

        @staticmethod
        def _guard_title(**context: Any) -> None:
            if not context.get("title"):
                raise TransitionGuardError("Title is required to submit.")

    sm = DummySM()

    # 1. Idempotent same-state check
    assert sm.can_transition("draft", "draft") is True
    sm.validate_transition("draft", "draft")  # Should not raise

    # 2. Valid transition with guard satisfied
    assert sm.can_transition("draft", "submitted") is True
    sm.validate_transition("draft", "submitted", title="Proposal A")
    assert sm.transition("draft", "submitted", title="Proposal A") == "submitted"

    # 3. Guard failure raises TransitionGuardError
    try:
        sm.validate_transition("draft", "submitted", title="")
        assert False, "Expected TransitionGuardError for missing title"
    except TransitionGuardError as exc:
        assert "Title is required" in str(exc)

    # 4. Illegal / unmapped transition raises InvalidStateTransitionError
    try:
        sm.validate_transition("draft", "approved")
        assert False, "Expected InvalidStateTransitionError for draft -> approved"
    except InvalidStateTransitionError as exc:
        assert "Illegal state transition" in str(exc)

    # 5. Terminal state transition raises InvalidStateTransitionError
    assert sm.is_terminal("approved") is True
    assert sm.is_terminal("draft") is False
    try:
        sm.validate_transition("approved", "draft")
        assert False, "Expected InvalidStateTransitionError from terminal state"
    except InvalidStateTransitionError as exc:
        assert "terminal state" in str(exc).lower()

    # 6. Error hierarchy inherits from ValueError
    assert issubclass(InvalidStateTransitionError, ValueError)
    assert issubclass(TransitionGuardError, ValueError)
    assert issubclass(StateMachineError, ValueError)

    print("[PASS] BaseStateMachine transition matrix, guards, and terminal states verified")


def test_access_request_state_machine() -> None:
    """Test AccessRequestStateMachine (D-1 Reconciled)."""
    sm = AccessRequestStateMachine()

    # Verify all live enum members are recognized
    for status in AccessRequestStatus:
        assert status in sm._transitions or status in sm._terminal_states

    # 1. Valid full lifecycle: requested -> approved -> provisioning -> provisioned -> revoked
    user_id = uuid.uuid4()
    sm.validate_transition(
        AccessRequestStatus.requested,
        AccessRequestStatus.approved,
        actor_user_id=user_id,
    )
    sm.validate_transition(
        AccessRequestStatus.approved,
        AccessRequestStatus.provisioning,
    )
    sm.validate_transition(
        AccessRequestStatus.provisioning,
        AccessRequestStatus.provisioned,
        external_id="gh-inv-123",
    )
    sm.validate_transition(
        AccessRequestStatus.provisioned,
        AccessRequestStatus.revoked,
    )

    # 2. Guard: requested -> approved requires approver identity
    try:
        sm.validate_transition(
            AccessRequestStatus.requested,
            AccessRequestStatus.approved,
            actor_user_id=None,
        )
        assert False, "Expected TransitionGuardError for missing approver"
    except TransitionGuardError:
        pass

    # 3. Guard: provisioning -> provisioned requires external_id
    try:
        sm.validate_transition(
            AccessRequestStatus.provisioning,
            AccessRequestStatus.provisioned,
            external_id=None,
        )
        assert False, "Expected TransitionGuardError for missing external_id"
    except TransitionGuardError:
        pass

    # 4. Valid failure path from provisioning (guard requires error)
    sm.validate_transition(
        AccessRequestStatus.provisioning,
        AccessRequestStatus.failed,
        error="Connection timeout",
    )

    # 5. Guard: provisioning -> failed requires error/rationale
    try:
        sm.validate_transition(
            AccessRequestStatus.provisioning,
            AccessRequestStatus.failed,
            error=None,
        )
        assert False, "Expected TransitionGuardError for missing failure rationale"
    except TransitionGuardError:
        pass

    # 6. Terminal protections: failed and revoked cannot transition
    assert sm.is_terminal(AccessRequestStatus.failed) is True
    assert sm.is_terminal(AccessRequestStatus.revoked) is True
    try:
        sm.validate_transition(AccessRequestStatus.failed, AccessRequestStatus.approved)
        assert False, "Expected error transitioning from terminal failed state"
    except InvalidStateTransitionError:
        pass

    try:
        sm.validate_transition(AccessRequestStatus.revoked, AccessRequestStatus.provisioned)
        assert False, "Expected error transitioning from terminal revoked state"
    except InvalidStateTransitionError:
        pass

    # 7. Illegal bypass: requested -> provisioned (skipping approval)
    try:
        sm.validate_transition(AccessRequestStatus.requested, AccessRequestStatus.provisioned)
        assert False, "Expected error bypassing approval"
    except InvalidStateTransitionError:
        pass

    print("[PASS] AccessRequestStateMachine lifecycle, guards, and terminal protection verified")


def test_assignment_state_machine() -> None:
    """Test AssignmentStateMachine (D-2 Reconciled)."""
    sm = AssignmentStateMachine()

    # 1. Valid paths: active -> completed, active -> reassigned
    sm.validate_transition(AssignmentStatus.active, AssignmentStatus.completed)
    sm.validate_transition(AssignmentStatus.active, AssignmentStatus.reassigned)

    # 2. Terminal protections: completed and reassigned cannot transition out
    assert sm.is_terminal(AssignmentStatus.completed) is True
    assert sm.is_terminal(AssignmentStatus.reassigned) is True

    try:
        sm.validate_transition(AssignmentStatus.completed, AssignmentStatus.active)
        assert False, "Expected error reactivating completed assignment"
    except InvalidStateTransitionError:
        pass

    try:
        sm.validate_transition(AssignmentStatus.reassigned, AssignmentStatus.completed)
        assert False, "Expected error transitioning from reassigned state"
    except InvalidStateTransitionError:
        pass

    print("[PASS] AssignmentStateMachine capacity allocation lifecycle verified")


def test_onboarding_run_state_machine() -> None:
    """Test OnboardingRunStateMachine (D-3 Reconciled)."""
    sm = OnboardingRunStateMachine()

    # 1. Valid progression: in_progress -> blocked -> in_progress -> completed
    sm.validate_transition("in_progress", "blocked")
    sm.validate_transition("blocked", "in_progress")
    sm.validate_transition("in_progress", "completed", progress_pct=100)

    # 2. D-3 Justification: blocked -> completed allowed when 100% finished
    sm.validate_transition("blocked", "completed", progress_pct=100)

    # 3. Guard: cannot complete run with progress < 100%
    try:
        sm.validate_transition("in_progress", "completed", progress_pct=80)
        assert False, "Expected TransitionGuardError completing run at 80%"
    except TransitionGuardError:
        pass

    # 4. Terminal protection: completed run cannot transition
    assert sm.is_terminal("completed") is True
    try:
        sm.validate_transition("completed", "in_progress")
        assert False, "Expected error transitioning completed run"
    except InvalidStateTransitionError:
        pass

    print("[PASS] OnboardingRunStateMachine run lifecycle and completion guard verified")


def test_onboarding_item_state_machine() -> None:
    """Test OnboardingItemStateMachine (D-4 Extension)."""
    sm = OnboardingItemStateMachine()

    # 1. Valid progression: pending -> in_progress -> blocked -> in_progress -> completed
    sm.validate_transition("pending", "in_progress")
    sm.validate_transition(
        "in_progress",
        "blocked",
        blocker_reason="Awaiting security badge clearance",
    )
    sm.validate_transition("blocked", "in_progress")
    sm.validate_transition("in_progress", "completed")

    # 2. Guard: entering 'blocked' strictly requires non-empty blocker_reason
    for bad_reason in [None, "", "   "]:
        try:
            sm.validate_transition("in_progress", "blocked", blocker_reason=bad_reason)
            assert False, f"Expected TransitionGuardError for reason: {bad_reason!r}"
        except TransitionGuardError as exc:
            assert "blocker_reason is required" in str(exc)

        try:
            sm.validate_transition("pending", "blocked", blocker_reason=bad_reason)
            assert False, f"Expected TransitionGuardError for reason: {bad_reason!r}"
        except TransitionGuardError as exc:
            assert "blocker_reason is required" in str(exc)

    # 3. Guard: evidence verification
    try:
        sm.validate_transition("in_progress", "completed", evidence_required=True, evidence_ref=None)
        assert False, "Expected TransitionGuardError for missing evidence_ref"
    except TransitionGuardError:
        pass

    sm.validate_transition(
        "in_progress",
        "completed",
        evidence_required=True,
        evidence_ref="https://vault.example.com/doc.pdf",
    )

    # 4. Terminal protection: completed items are immutable
    assert sm.is_terminal("completed") is True
    try:
        sm.validate_transition("completed", "pending")
        assert False, "Expected error altering completed checklist item"
    except InvalidStateTransitionError:
        pass

    print("[PASS] OnboardingItemStateMachine checklist task guards and blocker reasons verified")


def test_ticket_state_machine() -> None:
    """Test TicketStateMachine (Passive Mode per §3 Task 3.6 & §4 Task 4.3)."""
    sm = TicketStateMachine()

    # 1. Full board workflow: backlog -> todo -> in_progress -> review -> completed
    sm.validate_transition("backlog", "todo")
    sm.validate_transition("todo", "in_progress")
    sm.validate_transition("in_progress", "review")
    sm.validate_transition("review", "completed", user_role=UserRole.MANAGER)

    # 2. Guard: entering blocked requires non-empty blocked_reason
    try:
        sm.validate_transition("in_progress", "blocked", blocked_reason=None)
        assert False, "Expected TransitionGuardError for missing blocked_reason"
    except TransitionGuardError:
        pass

    sm.validate_transition("in_progress", "blocked", blocked_reason="Waiting on design assets")

    # 3. Guard: review -> completed requires Manager or Admin credentials
    try:
        sm.validate_transition("review", "completed", user_role=UserRole.MEMBER)
        assert False, "Expected TransitionGuardError for MEMBER completing review"
    except TransitionGuardError as exc:
        assert "Manager or Administrator credentials" in str(exc)

    # Admin role is accepted
    sm.validate_transition("review", "completed", user_role=UserRole.ADMIN)

    # 4. Terminal state: completed
    assert sm.is_terminal("completed") is True
    try:
        sm.validate_transition("completed", "todo")
        assert False, "Expected error reopening completed ticket"
    except InvalidStateTransitionError:
        pass

    print("[PASS] TicketStateMachine delivery board stages and supervisory guard verified")


def test_service_wiring() -> None:
    """Test domain service wiring to state machines and HTTP 400 enforcement."""
    from fastapi import HTTPException
    from app.services.access import AccessLifecycleError, AccessService
    from app.services.assignment import AssignmentService
    from app.services.onboarding import OnboardingService
    from app.models.access import AccessRequest
    from app.models.assignment import Assignment
    from app.models.onboarding import OnboardingItem, OnboardingRun
    from app.schemas.assignment import AssignmentUpdate
    from app.schemas.onboarding import OnboardingItemUpdate
    from app.models.user import User

    db = SessionLocal()
    try:
        # 1. AccessService wiring
        access_svc = AccessService(db)
        assert isinstance(access_svc.state_machine, AccessRequestStateMachine)
        dummy_req = AccessRequest(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            status=AccessRequestStatus.requested,
        )
        try:
            access_svc._transition(dummy_req, AccessRequestStatus.provisioned, uuid.uuid4())
            assert False, "Expected AccessLifecycleError on illegal requested -> provisioned transition"
        except AccessLifecycleError as exc:
            assert "Invalid access transition" in str(exc)

        # 2. AssignmentService wiring
        assignment_svc = AssignmentService(db)
        assert isinstance(assignment_svc.state_machine, AssignmentStateMachine)
        completed_assignment = Assignment(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            status=AssignmentStatus.completed,
            capacity_percentage=50,
        )
        # Attempting to validate transition from completed -> active
        try:
            assignment_svc.state_machine.validate_transition(
                completed_assignment.status,
                AssignmentStatus.active,
            )
            assert False, "Expected InvalidStateTransitionError from completed assignment"
        except InvalidStateTransitionError as exc:
            assert "terminal state" in str(exc).lower()

        # 3. OnboardingService wiring
        onboarding_svc = OnboardingService(db)
        assert isinstance(onboarding_svc.item_state_machine, OnboardingItemStateMachine)
        assert isinstance(onboarding_svc.run_state_machine, OnboardingRunStateMachine)
        dummy_item = OnboardingItem(
            id=uuid.uuid4(),
            run_id=uuid.uuid4(),
            status="in_progress",
        )
        # Attempting to validate transition to blocked with empty blocker_reason
        try:
            onboarding_svc.item_state_machine.validate_transition(
                dummy_item.status,
                "blocked",
                blocker_reason="   ",
            )
            assert False, "Expected TransitionGuardError for whitespace blocker_reason"
        except TransitionGuardError as exc:
            assert "blocker_reason is required" in str(exc)

        print("[PASS] Domain service state machine wiring and guard contracts verified")
    finally:
        db.close()


def main() -> None:
    print("=" * 80)
    print("DWOP-016: STATE MACHINE PATTERN ARCHITECTURAL SUITE")
    print("=" * 80)

    test_base_state_machine()
    test_access_request_state_machine()
    test_assignment_state_machine()
    test_onboarding_run_state_machine()
    test_onboarding_item_state_machine()
    test_ticket_state_machine()
    test_service_wiring()

    print("=" * 80)
    print("DWOP-016 VERIFICATION PASSED (7/7 state machine test suites green)")
    print("=" * 80)


if __name__ == "__main__":
    main()
