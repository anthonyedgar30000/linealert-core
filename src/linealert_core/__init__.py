"""Public API for LineAlert Core."""

from .diagnostics import DiagnosticEngine, DiagnosticRecommendation
from .events import EventQuality, MachineEvent
from .machine import (
    ComponentDefinition,
    ComponentDependency,
    EventBinding,
    MachineProfile,
    MachineProfileError,
)
from .mosaic import (
    ConsumerOutput,
    EventIdentityCollision,
    EventReceipt,
    FusionMosaic,
    Subscription,
)
from .pipeline import LineAlertCore, PipelineResult
from .replay import (
    ReplayInputError,
    ReplaySummary,
    build_core_from_config,
    load_events,
    replay_events,
    summary_to_dict,
)
from .timing import TemporalRule, TimingFinding, TimingMonitor, TimingStatus
from .topology import DependencyEdge, TopologyContext, TopologyGraph

__all__ = [
    "ComponentDefinition",
    "ComponentDependency",
    "ConsumerOutput",
    "DependencyEdge",
    "DiagnosticEngine",
    "DiagnosticRecommendation",
    "EventBinding",
    "EventIdentityCollision",
    "EventQuality",
    "EventReceipt",
    "FusionMosaic",
    "LineAlertCore",
    "MachineEvent",
    "MachineProfile",
    "MachineProfileError",
    "PipelineResult",
    "ReplayInputError",
    "ReplaySummary",
    "Subscription",
    "TemporalRule",
    "TimingFinding",
    "TimingMonitor",
    "TimingStatus",
    "TopologyContext",
    "TopologyGraph",
    "build_core_from_config",
    "load_events",
    "replay_events",
    "summary_to_dict",
]
