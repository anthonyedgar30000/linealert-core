"""Deterministic functional-temporal evidence semantics for LineAlert."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class FunctionalTemporalError(ValueError):
    """Raised when the functional-temporal model or evidence is invalid."""


class TemporalCoverage(StrEnum):
    """How much temporal scope one evidence item actually establishes."""

    POINT_ONLY = "POINT_ONLY"
    THROUGHOUT_SCOPE = "THROUGHOUT_SCOPE"
    REACHABLE_STATE_SET = "REACHABLE_STATE_SET"


class EvidenceValidity(StrEnum):
    """Current applicability of immutable evidence."""

    CURRENT = "CURRENT"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


class EpistemicState(StrEnum):
    """Bounded evidence state; EXPOSED is derived, never raw evidence."""

    VERIFIED = "VERIFIED"
    UNRESOLVED = "UNRESOLVED"
    VIOLATED = "VIOLATED"
    CONFLICT = "CONFLICT"
    EXPOSED = "EXPOSED"


class TransitionDisposition(StrEnum):
    """Deterministic outcome for one event-triggered transition candidate."""

    NOT_TRIGGERED = "NOT_TRIGGERED"
    ADMITTED = "ADMITTED"
    REJECTED = "REJECTED"
    UNRESOLVED = "UNRESOLVED"


@dataclass(frozen=True, slots=True)
class EvidenceObservation:
    """One already-classified observation proposed for temporal reasoning."""

    evidence_id: str
    evidence_key: str
    state: EpistemicState
    validity: EvidenceValidity
    coverage: TemporalCoverage
    source_id: str
    cycle_id: str | None = None
    phase_id: str | None = None

    def __post_init__(self) -> None:
        for field_name in ("evidence_id", "evidence_key", "source_id"):
            value = getattr(self, field_name)
            if not value.strip():
                raise FunctionalTemporalError(f"{field_name} must not be empty")
        if self.state is EpistemicState.EXPOSED:
            raise FunctionalTemporalError("EXPOSED is derived and cannot be raw evidence")
        for field_name in ("cycle_id", "phase_id"):
            value = getattr(self, field_name)
            if value is not None and not value.strip():
                raise FunctionalTemporalError(f"{field_name} must not be empty when supplied")


@dataclass(frozen=True, slots=True)
class RequirementDefinition:
    """Evidence-backed condition used as a guard or phase invariant."""

    requirement_id: str
    evidence_keys: tuple[str, ...]
    required_coverage: TemporalCoverage
    depends_on_requirement_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.requirement_id.strip():
            raise FunctionalTemporalError("requirement_id must not be empty")
        if not self.evidence_keys:
            raise FunctionalTemporalError("requirements need at least one evidence key")
        if any(not key.strip() for key in self.evidence_keys):
            raise FunctionalTemporalError("requirement evidence keys must not be empty")
        if len(self.evidence_keys) != len(set(self.evidence_keys)):
            raise FunctionalTemporalError("requirement evidence keys must be unique")
        if any(not item.strip() for item in self.depends_on_requirement_ids):
            raise FunctionalTemporalError("requirement dependencies must not be empty")
        if self.requirement_id in self.depends_on_requirement_ids:
            raise FunctionalTemporalError("a requirement cannot depend on itself")


@dataclass(frozen=True, slots=True)
class GuardDefinition(RequirementDefinition):
    """Condition that must hold before a transition may be admitted."""


@dataclass(frozen=True, slots=True)
class InvariantDefinition(RequirementDefinition):
    """Condition expected to remain valid while a phase is active."""


@dataclass(frozen=True, slots=True)
class PhaseDefinition:
    """One sustained machine condition inside a repeating operating cycle."""

    phase_id: str
    name: str
    owner_component_id: str
    invariant_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field_name in ("phase_id", "name", "owner_component_id"):
            if not getattr(self, field_name).strip():
                raise FunctionalTemporalError(f"{field_name} must not be empty")
        if len(self.invariant_ids) != len(set(self.invariant_ids)):
            raise FunctionalTemporalError("phase invariant IDs must be unique")


@dataclass(frozen=True, slots=True)
class TransitionDefinition:
    """Event-triggered candidate transition whose guards must still pass."""

    transition_id: str
    from_phase_id: str
    to_phase_id: str
    trigger_event_type: str
    guard_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in (
            "transition_id",
            "from_phase_id",
            "to_phase_id",
            "trigger_event_type",
        ):
            if not getattr(self, field_name).strip():
                raise FunctionalTemporalError(f"{field_name} must not be empty")
        if self.from_phase_id == self.to_phase_id:
            raise FunctionalTemporalError("transition phases must differ")
        if not self.guard_ids:
            raise FunctionalTemporalError("transitions need at least one guard")
        if len(self.guard_ids) != len(set(self.guard_ids)):
            raise FunctionalTemporalError("transition guard IDs must be unique")


@dataclass(frozen=True, slots=True)
class FunctionalTemporalModel:
    """Validated phase, transition, guard, and invariant contract."""

    phases: tuple[PhaseDefinition, ...]
    transitions: tuple[TransitionDefinition, ...]
    guards: tuple[GuardDefinition, ...]
    invariants: tuple[InvariantDefinition, ...]

    def __post_init__(self) -> None:
        if not self.phases:
            raise FunctionalTemporalError("model requires at least one phase")
        self._validate_unique(self.phases, "phase_id", "phase")
        self._validate_unique(self.transitions, "transition_id", "transition")
        self._validate_unique(self.guards, "requirement_id", "guard")
        self._validate_unique(self.invariants, "requirement_id", "invariant")

        phase_ids = {item.phase_id for item in self.phases}
        guard_ids = {item.requirement_id for item in self.guards}
        invariant_ids = {item.requirement_id for item in self.invariants}
        if guard_ids & invariant_ids:
            raise FunctionalTemporalError("guard and invariant IDs must not overlap")

        for transition in self.transitions:
            if transition.from_phase_id not in phase_ids or transition.to_phase_id not in phase_ids:
                raise FunctionalTemporalError("transition references an unknown phase")
            unknown = set(transition.guard_ids) - guard_ids
            if unknown:
                raise FunctionalTemporalError(
                    f"transition references unknown guards: {sorted(unknown)}"
                )
        for phase in self.phases:
            unknown = set(phase.invariant_ids) - invariant_ids
            if unknown:
                raise FunctionalTemporalError(
                    f"phase references unknown invariants: {sorted(unknown)}"
                )
        requirements = {item.requirement_id: item for item in (*self.guards, *self.invariants)}
        for requirement in requirements.values():
            unknown = set(requirement.depends_on_requirement_ids) - requirements.keys()
            if unknown:
                raise FunctionalTemporalError(
                    f"requirement references unknown dependencies: {sorted(unknown)}"
                )
        self._validate_dependency_cycles(requirements)

    @staticmethod
    def _validate_unique(items: tuple[object, ...], field: str, label: str) -> None:
        values = [getattr(item, field) for item in items]
        if len(values) != len(set(values)):
            raise FunctionalTemporalError(f"{label} IDs must be unique")

    @staticmethod
    def _validate_dependency_cycles(requirements: Mapping[str, RequirementDefinition]) -> None:
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(requirement_id: str) -> None:
            if requirement_id in visited:
                return
            if requirement_id in visiting:
                raise FunctionalTemporalError("requirement dependency graph contains a cycle")
            visiting.add(requirement_id)
            for dependency in requirements[requirement_id].depends_on_requirement_ids:
                visit(dependency)
            visiting.remove(requirement_id)
            visited.add(requirement_id)

        for requirement_id in requirements:
            visit(requirement_id)


@dataclass(frozen=True, slots=True)
class RequirementEvaluation:
    requirement_id: str
    state: EpistemicState
    reasons: tuple[str, ...]
    evidence_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class PhaseEvaluation:
    phase_id: str
    state: EpistemicState
    invariant_results: tuple[RequirementEvaluation, ...]


@dataclass(frozen=True, slots=True)
class TransitionEvaluation:
    transition_id: str
    disposition: TransitionDisposition
    from_phase_id: str
    to_phase_id: str
    target_phase_admission_state: EpistemicState
    guard_results: tuple[RequirementEvaluation, ...]


class FunctionalTemporalEvaluator:
    """Evaluate already-classified operational evidence without diagnosing cause."""

    def __init__(self, model: FunctionalTemporalModel) -> None:
        self.model = model
        self._phases = MappingProxyType({item.phase_id: item for item in model.phases})
        self._guards = MappingProxyType({item.requirement_id: item for item in model.guards})
        self._invariants = MappingProxyType(
            {item.requirement_id: item for item in model.invariants}
        )
        self._requirements = MappingProxyType({**self._guards, **self._invariants})

    def evaluate_requirements(
        self, evidence: Mapping[str, EvidenceObservation]
    ) -> Mapping[str, RequirementEvaluation]:
        cache: dict[str, RequirementEvaluation] = {}

        def resolve(requirement_id: str) -> RequirementEvaluation:
            if requirement_id in cache:
                return cache[requirement_id]
            definition = self._requirements[requirement_id]
            base = self._evaluate_local(definition, evidence)
            if base.state is not EpistemicState.VERIFIED:
                cache[requirement_id] = base
                return base

            dependencies = tuple(resolve(item) for item in definition.depends_on_requirement_ids)
            state = self._dependency_state(dependencies)
            if state is EpistemicState.VERIFIED:
                result = base
            else:
                reasons = base.reasons + (
                    "dependency state prevents this requirement from being established",
                )
                result = RequirementEvaluation(
                    requirement_id=requirement_id,
                    state=state,
                    reasons=reasons,
                    evidence_ids=base.evidence_ids,
                )
            cache[requirement_id] = result
            return result

        for requirement_id in self._requirements:
            resolve(requirement_id)
        return MappingProxyType(dict(cache))

    def evaluate_phase(
        self, phase_id: str, evidence: Mapping[str, EvidenceObservation]
    ) -> PhaseEvaluation:
        phase = self._phases.get(phase_id)
        if phase is None:
            raise FunctionalTemporalError(f"unknown phase {phase_id!r}")
        requirements = self.evaluate_requirements(evidence)
        results = tuple(requirements[item] for item in phase.invariant_ids)
        return PhaseEvaluation(
            phase_id=phase_id,
            state=(
                self._aggregate(item.state for item in results)
                if results
                else EpistemicState.UNRESOLVED
            ),
            invariant_results=results,
        )

    def evaluate_transition(
        self,
        current_phase_id: str,
        trigger_event_type: str,
        evidence: Mapping[str, EvidenceObservation],
    ) -> TransitionEvaluation:
        if current_phase_id not in self._phases:
            raise FunctionalTemporalError(f"unknown phase {current_phase_id!r}")
        candidates = tuple(
            item
            for item in self.model.transitions
            if item.from_phase_id == current_phase_id
            and item.trigger_event_type == trigger_event_type
        )
        if not candidates:
            return TransitionEvaluation(
                transition_id="",
                disposition=TransitionDisposition.NOT_TRIGGERED,
                from_phase_id=current_phase_id,
                to_phase_id=current_phase_id,
                target_phase_admission_state=EpistemicState.UNRESOLVED,
                guard_results=(),
            )
        if len(candidates) != 1:
            raise FunctionalTemporalError(
                "event matches multiple transitions from the current phase"
            )
        transition = candidates[0]
        requirements = self.evaluate_requirements(evidence)
        guards = tuple(requirements[item] for item in transition.guard_ids)
        states = {item.state for item in guards}
        if states == {EpistemicState.VERIFIED}:
            disposition = TransitionDisposition.ADMITTED
            target_state = EpistemicState.VERIFIED
        elif EpistemicState.VIOLATED in states:
            disposition = TransitionDisposition.REJECTED
            target_state = EpistemicState.VIOLATED
        elif EpistemicState.CONFLICT in states:
            disposition = TransitionDisposition.UNRESOLVED
            target_state = EpistemicState.CONFLICT
        else:
            disposition = TransitionDisposition.UNRESOLVED
            target_state = EpistemicState.EXPOSED
        return TransitionEvaluation(
            transition_id=transition.transition_id,
            disposition=disposition,
            from_phase_id=transition.from_phase_id,
            to_phase_id=transition.to_phase_id,
            target_phase_admission_state=target_state,
            guard_results=guards,
        )

    @staticmethod
    def _evaluate_local(
        definition: RequirementDefinition,
        evidence: Mapping[str, EvidenceObservation],
    ) -> RequirementEvaluation:
        observations: list[EvidenceObservation] = []
        reasons: list[str] = []
        states: list[EpistemicState] = []
        for key in definition.evidence_keys:
            observation = evidence.get(key)
            if observation is None:
                states.append(EpistemicState.UNRESOLVED)
                reasons.append(f"missing evidence for {key}")
                continue
            if observation.evidence_key != key:
                raise FunctionalTemporalError(
                    f"evidence mapping key {key!r} does not match observation key "
                    f"{observation.evidence_key!r}"
                )
            observations.append(observation)
            if observation.validity is not EvidenceValidity.CURRENT:
                states.append(EpistemicState.UNRESOLVED)
                reasons.append(f"{key} evidence validity is {observation.validity}")
                continue
            if not _coverage_satisfies(observation.coverage, definition.required_coverage):
                states.append(EpistemicState.UNRESOLVED)
                reasons.append(
                    f"{key} coverage {observation.coverage} does not satisfy "
                    f"{definition.required_coverage}"
                )
                continue
            states.append(observation.state)
        state = FunctionalTemporalEvaluator._aggregate(states)
        return RequirementEvaluation(
            requirement_id=definition.requirement_id,
            state=state,
            reasons=tuple(reasons),
            evidence_ids=tuple(item.evidence_id for item in observations),
        )

    @staticmethod
    def _dependency_state(
        dependencies: tuple[RequirementEvaluation, ...],
    ) -> EpistemicState:
        states = {item.state for item in dependencies}
        if not states or states == {EpistemicState.VERIFIED}:
            return EpistemicState.VERIFIED
        if EpistemicState.VIOLATED in states:
            return EpistemicState.VIOLATED
        if EpistemicState.CONFLICT in states:
            return EpistemicState.CONFLICT
        return EpistemicState.EXPOSED

    @staticmethod
    def _aggregate(states) -> EpistemicState:
        values = tuple(states)
        if not values:
            return EpistemicState.VERIFIED
        if EpistemicState.VIOLATED in values:
            return EpistemicState.VIOLATED
        if EpistemicState.CONFLICT in values:
            return EpistemicState.CONFLICT
        if EpistemicState.EXPOSED in values:
            return EpistemicState.EXPOSED
        if EpistemicState.UNRESOLVED in values:
            return EpistemicState.UNRESOLVED
        return EpistemicState.VERIFIED


def _coverage_satisfies(actual: TemporalCoverage, required: TemporalCoverage) -> bool:
    """Fail closed when interval/reachable-set semantics are not equivalent."""

    if required is TemporalCoverage.POINT_ONLY:
        return True
    return actual is required
