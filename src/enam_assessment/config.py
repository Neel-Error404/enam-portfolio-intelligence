"""Deterministic, side-effect-free project paths."""

from dataclasses import dataclass
from pathlib import Path

from .errors import ConfigurationError, MissingInputError

_WINDOWS_FORBIDDEN_FILENAME_CHARACTERS = frozenset('<>"|?*')
_WINDOWS_RESERVED_DEVICE_STEMS = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"COM{suffix}" for suffix in "123456789¹²³"}
    | {f"LPT{suffix}" for suffix in "123456789¹²³"}
)


@dataclass(frozen=True, slots=True)
class ProjectPaths:
    """Project locations derived only from an explicitly supplied root directory."""

    root: Path
    assessment_inputs: Path
    data: Path
    artifacts: Path

    @classmethod
    def from_root(cls, root: Path) -> "ProjectPaths":
        """Build project paths without reading the environment or creating directories."""
        root_path = Path(root)
        if not root_path.is_dir():
            raise ConfigurationError(
                f"Project root must be an existing directory; received: {root_path}"
            )

        resolved_root = root_path.resolve()
        return cls(
            root=resolved_root,
            assessment_inputs=resolved_root / "assessment_inputs",
            data=resolved_root / "data",
            artifacts=resolved_root / "artifacts",
        )

    def require_input(self, filename: str) -> Path:
        """Return an existing direct child of assessment_inputs or raise an explicit error."""
        self._validate_plain_windows_filename(filename)
        resolved_root = self.root.resolve()
        resolved_inputs = self.assessment_inputs.resolve()
        if resolved_inputs.parent != resolved_root:
            raise ConfigurationError(
                "assessment_inputs must resolve to a direct child beneath the configured "
                "project root."
            )
        if self.assessment_inputs.exists() and not self.assessment_inputs.is_dir():
            raise ConfigurationError("assessment_inputs must be a directory when it exists.")

        input_path = self.assessment_inputs / filename
        if not input_path.exists():
            raise MissingInputError(f"Required assessment input is missing: {input_path}")

        exact_path = next(
            (entry for entry in resolved_inputs.iterdir() if entry.name == filename),
            None,
        )
        if exact_path is None:
            raise ConfigurationError(
                "Assessment input name must match the exact on-disk filename casing."
            )

        resolved_input = exact_path.resolve()
        if not resolved_input.is_relative_to(resolved_inputs):
            raise ConfigurationError(
                "Assessment input must resolve beneath assessment_inputs; "
                "external links are not allowed."
            )
        if not exact_path.is_file():
            raise MissingInputError(f"Required assessment input is missing: {input_path}")
        return exact_path

    @staticmethod
    def _validate_plain_windows_filename(filename: str) -> None:
        if (
            not filename
            or filename in {".", ".."}
            or "/" in filename
            or "\\" in filename
            or ":" in filename
            or filename.endswith((" ", "."))
            or any(ord(character) < 32 for character in filename)
            or any(character in _WINDOWS_FORBIDDEN_FILENAME_CHARACTERS for character in filename)
            or filename.split(".", 1)[0].upper() in _WINDOWS_RESERVED_DEVICE_STEMS
        ):
            raise ConfigurationError(
                "Assessment input name must be a plain filename without path components, "
                "Windows aliases, or reserved device names."
            )
