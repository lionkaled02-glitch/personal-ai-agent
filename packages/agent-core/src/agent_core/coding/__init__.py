"""Phase 10 Step 1: bounded, provider-neutral coding data contracts.

Only in-memory analysis, edit proposals, and test plans are represented. The
package adds no coding runtime, file writes, command execution, or real model
provider. Resolve all project/file paths through the existing ``Workspace``.
"""

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
    CodeAnalysisRequest,
    CodeAnalysisResult,
    CodeAnalysisStatus,
    CodeChange,
    CodeDiagnostic,
    CodeEditRequest,
    CodeEditResult,
    CodeEditStatus,
    CodeFile,
    CodePatch,
    CodeRegion,
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
    TestCasePlan,
)

__all__ = [
    "CodeAnalysisRequest",
    "CodeAnalysisResult",
    "CodeAnalysisStatus",
    "CodeChange",
    "CodeDiagnostic",
    "CodeEditRequest",
    "CodeEditResult",
    "CodeEditStatus",
    "CodeFile",
    "CodePatch",
    "CodeRegion",
    "CodeSymbol",
    "CodeSymbolKind",
    "CodeTestPlanRequest",
    "CodeTestPlanResult",
    "CodeTestPlanStatus",
    "CodingError",
    "CodingLimitError",
    "CodingLimits",
    "CodingObservation",
    "CodingOperation",
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
    "PatchCheckStatus",
    "PatchValidationCheck",
    "PatchValidationMetadata",
    "PatchValidationStatus",
    "TestCasePlan",
]
