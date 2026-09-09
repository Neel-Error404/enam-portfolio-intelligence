from pathlib import Path

import pytest

from enam_assessment.config import ProjectPaths
from enam_assessment.errors import ConfigurationError, MissingInputError


def test_from_root_exposes_deterministic_project_paths(tmp_path: Path) -> None:
    paths = ProjectPaths.from_root(tmp_path)

    assert paths.root == tmp_path
    assert paths.assessment_inputs == tmp_path / "assessment_inputs"
    assert paths.data == tmp_path / "data"
    assert paths.artifacts == tmp_path / "artifacts"
    assert not paths.assessment_inputs.exists()
    assert not paths.data.exists()
    assert not paths.artifacts.exists()


def test_from_root_rejects_missing_or_non_directory_roots(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing"
    file_root = tmp_path / "file-root"
    file_root.write_text("not a directory", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="existing directory"):
        ProjectPaths.from_root(missing_root)
    with pytest.raises(ConfigurationError, match="existing directory"):
        ProjectPaths.from_root(file_root)


@pytest.mark.parametrize(
    "filename",
    [
        "../trade.xlsx",
        "nested/trade.xlsx",
        r"nested\trade.xlsx",
        "/trade.xlsx",
        r"C:\trade.xlsx",
        r"\\server\share\trade.xlsx",
        "trade\x00.xlsx",
        "CON",
    ],
)
def test_require_input_rejects_non_plain_filenames(tmp_path: Path, filename: str) -> None:
    paths = ProjectPaths.from_root(tmp_path)

    with pytest.raises(ConfigurationError, match="plain filename"):
        paths.require_input(filename)


def test_require_input_raises_actionable_error_for_missing_file(tmp_path: Path) -> None:
    paths = ProjectPaths.from_root(tmp_path)

    with pytest.raises(MissingInputError, match="Required assessment input is missing"):
        paths.require_input("missing.xlsx")


def test_require_input_returns_existing_direct_child_file(tmp_path: Path) -> None:
    paths = ProjectPaths.from_root(tmp_path)
    paths.assessment_inputs.mkdir()
    input_file = paths.assessment_inputs / "trade.xlsx"
    input_file.write_text("test fixture", encoding="utf-8")

    assert paths.require_input("trade.xlsx") == input_file


@pytest.mark.parametrize("alias", ["trade.xlsx.", "trade.xlsx ", "trade.xlsx::$DATA"])
def test_require_input_rejects_windows_filename_aliases(tmp_path: Path, alias: str) -> None:
    paths = ProjectPaths.from_root(tmp_path)
    paths.assessment_inputs.mkdir()
    (paths.assessment_inputs / "trade.xlsx").write_text("test fixture", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="plain filename"):
        paths.require_input(alias)


def test_require_input_rejects_case_alias_of_existing_file(tmp_path: Path) -> None:
    paths = ProjectPaths.from_root(tmp_path)
    paths.assessment_inputs.mkdir()
    (paths.assessment_inputs / "Trade.xlsx").write_text("test fixture", encoding="utf-8")

    with pytest.raises(ConfigurationError, match="exact.*casing"):
        paths.require_input("trade.xlsx")


def test_require_input_rejects_assessment_inputs_symlink_outside_root(tmp_path: Path) -> None:
    paths = ProjectPaths.from_root(tmp_path)
    outside = tmp_path.parent / "outside-inputs"
    outside.mkdir(exist_ok=True)
    (outside / "trade.xlsx").write_text("test fixture", encoding="utf-8")

    try:
        paths.assessment_inputs.symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"Symlink creation is unavailable: {error}")

    with pytest.raises(ConfigurationError, match="resolve beneath"):
        paths.require_input("trade.xlsx")


def test_require_input_rejects_file_symlink_outside_inputs(tmp_path: Path) -> None:
    paths = ProjectPaths.from_root(tmp_path)
    paths.assessment_inputs.mkdir()
    outside_file = tmp_path.parent / "outside-trade.xlsx"
    outside_file.write_text("test fixture", encoding="utf-8")
    linked_file = paths.assessment_inputs / "trade.xlsx"

    try:
        linked_file.symlink_to(outside_file)
    except OSError as error:
        pytest.skip(f"Symlink creation is unavailable: {error}")

    with pytest.raises(ConfigurationError, match="resolve beneath"):
        paths.require_input("trade.xlsx")


def test_require_input_rejects_assessment_inputs_equal_to_project_root(tmp_path: Path) -> None:
    (tmp_path / "trade.xlsx").write_text("test fixture", encoding="utf-8")
    paths = ProjectPaths(
        root=tmp_path,
        assessment_inputs=tmp_path,
        data=tmp_path / "data",
        artifacts=tmp_path / "artifacts",
    )

    with pytest.raises(ConfigurationError, match="direct child"):
        paths.require_input("trade.xlsx")


@pytest.mark.parametrize(
    "filename",
    [
        "trade<.xlsx",
        "trade>.xlsx",
        'trade".xlsx',
        "trade|.xlsx",
        "trade?.xlsx",
        "trade*.xlsx",
        "CONIN$",
        "CONOUT$",
        "COM¹",
        "LPT²",
    ],
)
def test_require_input_rejects_windows_forbidden_or_reserved_names(
    tmp_path: Path, filename: str
) -> None:
    paths = ProjectPaths.from_root(tmp_path)

    with pytest.raises(ConfigurationError, match="plain filename"):
        paths.require_input(filename)
