from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from models import Finding

@dataclass
class RunInitialized:
    pass

@dataclass
class BeforeRunStart:
    pass

@dataclass
class BeforeFindingCreated:
    finding: Finding

@dataclass
class FindingCreated(BeforeFindingCreated):
    pass

@dataclass
class BeforeTerminateRun:
    pass

@dataclass
class BeforeFinalizeRun:
    pass

@dataclass
class FileRead:
    path: Path

@dataclass
class BeforeRestartRun:
    pass

@dataclass
class StartReviewFile:
    path: Path

@dataclass
class FileReviewed:
    path: Path

SAISTRunEvent = StartReviewFile | FileReviewed | FindingCreated

SAISTEvent = RunInitialized | BeforeRunStart | BeforeFindingCreated | FindingCreated | BeforeTerminateRun | BeforeFinalizeRun | FileRead | BeforeRestartRun | SAISTRunEvent

@dataclass
class Skip:
    """
    Explicitly skip for this event, don't influence the outcome.
    """
    pass

@dataclass
class Prevent:
    reason: str | None = None

@dataclass
class PreventTerminal:
    reason: str | None = None

SAISTEventResponse = Skip | Prevent | PreventTerminal
