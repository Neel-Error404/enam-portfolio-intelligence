"""Explicit exceptions for the ENAM assessment foundation."""


class EnamAssessmentError(Exception):
    """Base exception for expected assessment-package failures."""


class ConfigurationError(EnamAssessmentError):
    """Raised when caller-supplied project configuration is invalid."""


class MissingInputError(EnamAssessmentError):
    """Raised when a required protected input is absent."""


class WorkbookIngestionError(EnamAssessmentError):
    """Base exception for expected workbook-ingestion failures."""


class WorkbookPasswordError(WorkbookIngestionError):
    """Raised when an encrypted workbook password is absent or incorrect."""


class WorkbookReadError(WorkbookIngestionError):
    """Raised when the workbook cannot be parsed as a supported Excel file."""


class WorkbookSchemaError(WorkbookIngestionError):
    """Raised when required sheets or columns no longer match the contract."""


class HistoricalAnalysisError(EnamAssessmentError):
    """Base exception for expected historical-analysis failures."""


class InvalidAnalysisInputError(HistoricalAnalysisError):
    """Raised when a calculation receives an invalid value or denominator."""


class UnsupportedRecordError(HistoricalAnalysisError):
    """Raised when a record cannot support the requested calculation."""


class EvidenceError(EnamAssessmentError):
    """Base exception for expected point-in-time evidence failures."""


class EvidenceValidationError(EvidenceError):
    """Raised when an evidence record violates its data contract."""


class UnsupportedIdentifierError(EvidenceError):
    """Raised when an instrument identifier is not in the verified mapping."""


class MissingEvidenceError(EvidenceError):
    """Raised when required dated evidence is absent."""


class SourceRetrievalError(EvidenceError):
    """Raised when a configured evidence source cannot be retrieved."""


class DecisionEngineError(EnamAssessmentError):
    """Base exception for deterministic decision-engine failures."""


class InvalidDecisionInputError(DecisionEngineError):
    """Raised when a decision calculation receives unsupported inputs."""


class EvidenceReferenceError(DecisionEngineError):
    """Raised when a decision cites evidence outside the frozen snapshot."""


class DecisionConsistencyError(DecisionEngineError):
    """Raised when a frozen Phase 5 input no longer reconciles to its source artifact."""


class MemoError(EnamAssessmentError):
    """Base exception for bounded memo-generation failures."""


class MemoConfigurationError(MemoError):
    """Raised when required Azure OpenAI memo configuration is absent or invalid."""


class MemoContextError(MemoError):
    """Raised when a memo context violates the frozen evidence boundary."""


class MemoProviderError(MemoError):
    """Raised when the configured memo provider cannot return a response."""


class MemoCompatibilityError(MemoProviderError):
    """Raised when a provider cannot satisfy the structured-output contract."""


class MemoValidationError(MemoError):
    """Raised when generated memo content fails schema or citation validation."""


class UIArtifactError(EnamAssessmentError):
    """Raised when a local dashboard artifact is missing, malformed, or inconsistent."""


class PortfolioIntelligenceError(EnamAssessmentError):
    """Base exception for bounded interactive portfolio-intelligence failures."""


class QuestionContextError(PortfolioIntelligenceError):
    """Raised when a grounded question context is unsupported or exceeds its budget."""


class QuestionValidationError(PortfolioIntelligenceError):
    """Raised when a generated answer violates its schema or citation boundary."""


class ScenarioLabError(PortfolioIntelligenceError):
    """Raised when a scenario override cannot be recalculated safely."""


class HoldingsOverlayError(PortfolioIntelligenceError):
    """Raised when session-local holdings or cash inputs are invalid."""
