"""Phase 10 coding foundation: bounded analysis, diagnostics, and patch application.

The local runtime reads validated workspace files and returns bounded facts;
the diagnostics engine consumes only those source snapshots. Edit proposals
and test plans remain structured data, while patch application is a separate
permission-gated mutation step with live hash/size preconditions. This package
adds no shell, arbitrary code execution, command runner, or real model provider.
Resolve paths through Workspace.
"""

from .diagnostics import CodeDiagnosticBatch, CodeDiagnosticsEngine
from .errors import (
    CodingError,
    CodingLimitError,
    CodingPermissionError,
    CodingProviderError,
    CodingTimeoutError,
    CodingUnsupportedOperationError,
    CodingValidationError,
    CodingWorkspaceError,
)
from .interfaces import CodingOperation, CodingProvider
from .limits import CodingLimits
from .mock import MockCodingProvider
from .models import (
    AnalyzedCodeFile,
    CodeAnalysisLimitReason,
    CodeAnalysisMethod,
    CodeAnalysisRequest,
    CodeAnalysisResult,
    CodeAnalysisStatus,
    CodeChange,
    CodeDiagnostic,
    CodeDiagnosticCategory,
    CodeEditRequest,
    CodeEditResult,
    CodeEditStatus,
    CodeFile,
    CodeFileMetric,
    CodeLanguage,
    CodePatch,
    CodeRegion,
    CodeSkipReason,
    CodeSymbol,
    CodeSymbolKind,
    CodeTestPlanRequest,
    CodeTestPlanResult,
    CodeTestPlanStatus,
    CodingObservation,
    CodingProject,
    DiagnosticSeverity,
    ObservedCodeFile,
    PatchCheckStatus,
    PatchValidationCheck,
    PatchValidationMetadata,
    PatchValidationStatus,
    SkippedCodeFile,
    TestCasePlan,
)
from .patches import (
    CodingPatchRuntime,
    PatchApplicationResult,
    PatchApplicationStatus,
    PatchFileResult,
)
from .runtime import CodingAnalysisRuntime

__all__ = [
    "AnalyzedCodeFile",
    "CodeAnalysisLimitReason",
    "CodeAnalysisMethod",
    "CodeAnalysisRequest",
    "CodeAnalysisResult",
    "CodeAnalysisStatus",
    "CodeChange",
    "CodeDiagnostic",
    "CodeDiagnosticBatch",
    "CodeDiagnosticCategory",
    "CodeDiagnosticsEngine",
    "CodeEditRequest",
    "CodeEditResult",
    "CodeEditStatus",
    "CodeFile",
    "CodeFileMetric",
    "CodeLanguage",
    "CodePatch",
    "CodeRegion",
    "CodeSkipReason",
    "CodeSymbol",
    "CodeSymbolKind",
    "CodeTestPlanRequest",
    "CodeTestPlanResult",
    "CodeTestPlanStatus",
    "CodingAnalysisRuntime",
    "CodingError",
    "CodingLimitError",
    "CodingLimits",
    "CodingObservation",
    "CodingOperation",
    "CodingPatchRuntime",
    "CodingPermissionError",
    "CodingProject",
    "CodingProvider",
    "CodingProviderError",
    "CodingTimeoutError",
    "CodingUnsupportedOperationError",
    "CodingValidationError",
    "CodingWorkspaceError",
    "DiagnosticSeverity",
    "MockCodingProvider",
    "ObservedCodeFile",
    "PatchApplicationResult",
    "PatchApplicationStatus",
    "PatchCheckStatus",
    "PatchFileResult",
    "PatchValidationCheck",
    "PatchValidationMetadata",
    "PatchValidationStatus",
    "SkippedCodeFile",
    "TestCasePlan",
]
