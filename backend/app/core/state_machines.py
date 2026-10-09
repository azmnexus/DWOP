"""State Machine Pattern — Declarative Finite State Machines and Transition Guards.

DWOP Architectural Pattern Task P-06 (CTO Mandate §3 Task 3.6 and §4 Task 4.3).
Centralizes status progression rules into deterministic state machines, eliminates
ad-hoc if/else checks, prevents illegal lifecycle bypasses, and enforces transition guards.
"""

from __future__ import annotations

import enum
from typing import Any, Callable, Dict, Generic, List, Optional, Set, Tuple, TypeVar

from app.core.policy import policy_engine
from app.models.access import AccessRequestStatus
from app.models.assignment import AssignmentStatus
from app.models.user import UserRole

StateType = TypeVar("StateType")


# ============================================================================
# Exception Hierarchy
# ============================================================================

class StateMachineError(ValueError):
    """Base error for all state machine rule violations.
    Inherits from ValueError to preserve HTTP 400 Bad Request API contracts.
    """


class InvalidStateTransitionError(StateMachineError):
    """Raised when an entity attempts an unmapped or illegal state transition."""


class TransitionGuardError(StateMachineError):
    """Raised when a transition path exists but prerequisite condition guards fail."""


# ============================================================================
# Base State Machine
# ============================================================================

class BaseStateMachine(Generic[StateType]):
    """Generic Finite State Machine with declarative transitions, guards, and terminal states."""

    def __init__(self) -> None:
        self._transitions: Dict[StateType, Set[StateType]] = {}
        self._guards: Dict[Tuple[StateType, StateType], List[Callable[..., None]]] = {}
        self._terminal_states: Set[StateType] = set()
        self._setup()

    def _setup(self) -> None:
        """Subclasses declare states, transitions, and guards here."""
        raise NotImplementedError("Subclasses must implement _setup()")

    def _add_transition(
        self,
        from_state: StateType,
        to_states: Set[StateType],
    ) -> None:
        """Register valid target states for a given source state."""
        self._transitions.setdefault(from_state, set()).update(to_states)

    def _add_guard(
        self,
        from_state: StateType,
        to_state: StateType,
        guard_fn: Callable[..., None],
    ) -> None:
        """Register a precondition guard callable for a specific transition."""
        self._guards.setdefault((from_state, to_state), []).append(guard_fn)

    def _set_terminal(self, *states: StateType) -> None:
        """Mark one or more states as terminal (absorbing)."""
        for s in states:
            self._terminal_states.add(s)
            self._transitions.setdefault(s, set())

    def can_transition(self, current_state: StateType, target_state: StateType) -> bool:
        """Non-raising check whether a transition path exists in the transition matrix."""
        if current_state == target_state:
            return True
        return target_state in self._transitions.get(current_state, set())

    def validate_transition(
        self,
        current_state: StateType,
        target_state: StateType,
        **context: Any,
    ) -> None:
        """Validate transition graph legality and evaluate all precondition guards.
        
        Raises:
            InvalidStateTransitionError: If the transition is unmapped or violates graph.
            TransitionGuardError: If condition guards evaluate to false or fail.
        """
        # Idempotent same-state check: no-op if state is unchanged
        if current_state == target_state:
            return

        # Check if current state is terminal
        if self.is_terminal(current_state):
            raise InvalidStateTransitionError(
                f"Cannot transition from terminal state '{self._format_state(current_state)}'."
            )

        allowed = self._transitions.get(current_state, set())
        if target_state not in allowed:
            allowed_names = sorted([self._format_state(s) for s in allowed])
            raise InvalidStateTransitionError(
                f"Illegal state transition from '{self._format_state(current_state)}' "
                f"to '{self._format_state(target_state)}'. "
                f"Allowed target states: {allowed_names}."
            )

        # Evaluate registered guards for (current_state, target_state)
        guards = self._guards.get((current_state, target_state), [])
        for guard in guards:
            guard(**context)

    def transition(
        self,
        current_state: StateType,
        target_state: StateType,
        **context: Any,
    ) -> StateType:
        """Validate transition and return target_state upon success."""
        self.validate_transition(current_state, target_state, **context)
        return target_state

    def is_terminal(self, state: StateType) -> bool:
        """Return True if state is a terminal state."""
        return state in self._terminal_states

    def get_allowed_transitions(self, current_state: StateType) -> Set[StateType]:
        """Return a copy of all allowed target states from the current state."""
        return set(self._transitions.get(current_state, set()))

    @staticmethod
    def _format_state(state: StateType) -> str:
        """Format state as human-readable string."""
        if isinstance(state, enum.Enum):
            return state.value
        return str(state)


# ============================================================================
# 1. Access Request State Machine (D-1 Reconciled)
# ============================================================================

class AccessRequestStateMachine(BaseStateMachine[AccessRequestStatus]):
    """Formal state machine for AccessRequest lifecycle.
    
    Reconciled against live AccessRequestStatus enum:
    - requested -> approved (Guard: approver present)
    - requested -> failed (Guard: rejection decision/reason recorded, terminal)
    - approved -> provisioning (Guard: actor present, live DWOP-010 behaviour)
    - approved -> failed (Guard: pre-flight failure recorded)
    - provisioning -> provisioned (Guard: external_id/reference recorded)
    - provisioning -> failed (Guard: provider error recorded)
    - provisioned -> revoked (Guard: revocation confirmed)
    - failed, revoked: terminal absorbing states
    """

    def _setup(self) -> None:
        # Transitions
        self._add_transition(
            AccessRequestStatus.requested,
            {AccessRequestStatus.approved, AccessRequestStatus.failed},
        )
        self._add_transition(
            AccessRequestStatus.approved,
            {AccessRequestStatus.provisioning, AccessRequestStatus.failed},
        )
        self._add_transition(
            AccessRequestStatus.provisioning,
            {AccessRequestStatus.provisioned, AccessRequestStatus.failed},
        )
        self._add_transition(
            AccessRequestStatus.provisioned,
            {AccessRequestStatus.revoked},
        )

        # Terminal States
        self._set_terminal(AccessRequestStatus.failed, AccessRequestStatus.revoked)

        # Guards
        self._add_guard(
            AccessRequestStatus.requested,
            AccessRequestStatus.approved,
            self._guard_approver_present,
        )
        self._add_guard(
            AccessRequestStatus.provisioning,
            AccessRequestStatus.provisioned,
            self._guard_external_id_present,
        )
        self._add_guard(
            AccessRequestStatus.provisioning,
            AccessRequestStatus.failed,
            self._guard_error_recorded,
        )

    @staticmethod
    def _guard_approver_present(**context: Any) -> None:
        actor_id = context.get("actor_user_id") or context.get("approver_id") or context.get("approver")
        if not actor_id:
            raise TransitionGuardError("Approval transition requires an authenticated approver identity.")

    @staticmethod
    def _guard_external_id_present(**context: Any) -> None:
        ext_id = (
            context.get("external_id")
            or context.get("external_reference")
            or (context.get("metadata") or {}).get("external_id")
            or (context.get("metadata") or {}).get("external_reference")
        )
        if not ext_id:
            raise TransitionGuardError("Provisioned state requires an external provider reference or ID.")

    @staticmethod
    def _guard_error_recorded(**context: Any) -> None:
        error = (
            context.get("error")
            or context.get("error_message")
            or (context.get("metadata") or {}).get("error")
            or (context.get("metadata") or {}).get("error_message")
            or context.get("rationale")
        )
        if not error:
            raise TransitionGuardError("Failed state requires an error message or failure rationale.")


# ============================================================================
# 2. Assignment State Machine (D-2 Reconciled)
# ============================================================================

class AssignmentStateMachine(BaseStateMachine[AssignmentStatus]):
    """Formal state machine for Assignment capacity allocations.
    
    Reconciled against live AssignmentStatus enum (active, completed, reassigned).
    ('planned' omitted per ruling D-2 under zero-model-edits invariant).
    - active -> completed (Terminal)
    - active -> reassigned (Terminal)
    """

    def _setup(self) -> None:
        self._add_transition(
            AssignmentStatus.active,
            {AssignmentStatus.completed, AssignmentStatus.reassigned},
        )
        self._set_terminal(AssignmentStatus.completed, AssignmentStatus.reassigned)


# ============================================================================
# 3. Onboarding Run State Machine (D-3 Reconciled)
# ============================================================================

class OnboardingRunStatus(str, enum.Enum):
    """Workflow statuses for an active onboarding run."""
    pending = "pending"          # Explicitly marked reserved
    in_progress = "in_progress"
    blocked = "blocked"
    completed = "completed"


class OnboardingRunStateMachine(BaseStateMachine[str]):
    """Formal state machine for OnboardingRun lifecycle.
    
    Aligned to live string statuses ('in_progress', 'blocked', 'completed';
    'pending' reserved).
    - in_progress -> {blocked, completed}
    - blocked -> {in_progress, completed} (blocked->completed accepted per D-3 for item-completion recalc)
    - completed: terminal state
    """

    def _setup(self) -> None:
        # Pending reserved
        self._add_transition("pending", {"in_progress"})

        # Active transitions
        self._add_transition("in_progress", {"blocked", "completed"})
        self._add_transition("blocked", {"in_progress", "completed"})

        # Terminal
        self._set_terminal("completed")

        # Guard
        self._add_guard("in_progress", "completed", self._guard_all_items_completed)
        self._add_guard("blocked", "completed", self._guard_all_items_completed)

    @staticmethod
    def _guard_all_items_completed(**context: Any) -> None:
        progress_pct = context.get("progress_pct")
        if progress_pct is not None and progress_pct < 100:
            raise TransitionGuardError(
                f"Cannot mark onboarding run as completed: progress is {progress_pct}%, requires 100%."
            )


# ============================================================================
# 4. Onboarding Item State Machine (D-4 Extension)
# ============================================================================

class OnboardingItemStatus(str, enum.Enum):
    """Statuses for individual checklist tasks."""
    pending = "pending"
    in_progress = "in_progress"
    blocked = "blocked"
    completed = "completed"


class OnboardingItemStateMachine(BaseStateMachine[str]):
    """Formal state machine for individual OnboardingItem checklist tasks.
    
    Documented 5th machine extension (D-4) enforcing blocker_reason and evidence guards:
    - pending -> {in_progress, blocked, completed}
    - in_progress -> {blocked, completed}
    - blocked -> {in_progress, completed}
    - completed: terminal state
    """

    def _setup(self) -> None:
        self._add_transition("pending", {"in_progress", "blocked", "completed"})
        self._add_transition("in_progress", {"blocked", "completed"})
        self._add_transition("blocked", {"in_progress", "completed"})
        self._set_terminal("completed")

        # Guard: non-empty blocker_reason required for blocked state
        self._add_guard("pending", "blocked", self._guard_blocker_reason_required)
        self._add_guard("in_progress", "blocked", self._guard_blocker_reason_required)

        # Guard: evidence validation if required
        self._add_guard("pending", "completed", self._guard_evidence_check)
        self._add_guard("in_progress", "completed", self._guard_evidence_check)
        self._add_guard("blocked", "completed", self._guard_evidence_check)

    @staticmethod
    def _guard_blocker_reason_required(**context: Any) -> None:
        reason = context.get("blocker_reason")
        if not reason or not str(reason).strip():
            raise TransitionGuardError(
                "A non-empty blocker_reason is required when marking an onboarding item as blocked."
            )

    @staticmethod
    def _guard_evidence_check(**context: Any) -> None:
        evidence_required = context.get("evidence_required", False)
        evidence_ref = context.get("evidence_ref")
        if evidence_required and (not evidence_ref or not str(evidence_ref).strip()):
            raise TransitionGuardError(
                "An evidence reference is required to mark this checklist item as completed."
            )


# ============================================================================
# 5. Ticket State Machine (Passive Mode per §3 Task 3.6 & §4 Task 4.3)
# ============================================================================

class TicketStage(str, enum.Enum):
    """Delivery board stages for Work Management tickets."""
    backlog = "backlog"
    todo = "todo"
    in_progress = "in_progress"
    blocked = "blocked"
    review = "review"
    completed = "completed"


class TicketStateMachine(BaseStateMachine[str]):
    """Delivery board state machine for Work Management tickets.
    
    Enforces §4 Task 4.3 lifecycle rules:
    - backlog -> todo
    - todo -> {in_progress, blocked}
    - in_progress -> {blocked, review}
    - blocked -> {in_progress, todo}
    - review -> {completed, in_progress}
    - completed: terminal state
    
    Guards:
    - to_blocked: requires non-empty blocked_reason
    - review -> completed: requires supervisory credentials (Admin or Manager)
    """

    def _setup(self) -> None:
        self._add_transition("backlog", {"todo"})
        self._add_transition("todo", {"in_progress", "blocked"})
        self._add_transition("in_progress", {"blocked", "review"})
        self._add_transition("blocked", {"in_progress", "todo"})
        self._add_transition("review", {"completed", "in_progress"})
        self._set_terminal("completed")

        # Guards
        self._add_guard("todo", "blocked", self._guard_blocked_reason)
        self._add_guard("in_progress", "blocked", self._guard_blocked_reason)
        self._add_guard("review", "completed", self._guard_supervisory_approval)

    @staticmethod
    def _guard_blocked_reason(**context: Any) -> None:
        reason = context.get("blocked_reason")
        if not reason or not str(reason).strip():
            raise TransitionGuardError(
                "A non-empty blocked_reason is required when transitioning ticket to blocked."
            )

    @staticmethod
    def _guard_supervisory_approval(**context: Any) -> None:
        user_role = context.get("user_role")
        actor = context.get("actor")
        resolved = user_role or getattr(actor, "role", None)
        # ADR-002: supervisory authority resolved from the in-memory policy
        # matrix instead of a hardcoded string-literal role comparison.
        if not policy_engine.has_role(resolved, UserRole.ADMIN, UserRole.MANAGER):
            raise TransitionGuardError(
                "Transition from 'review' to 'completed' requires Manager or Administrator credentials."
            )
