from pathlib import Path

import pandas as pd

from growthpilot.data.download import download_dataset


def _workbook(path: Path) -> None:
    pd.DataFrame({"Invoice": ["1"]}).to_excel(path, index=False)


def test_direct_xlsx_payload_is_supported(tmp_path: Path) -> None:
    source = tmp_path / "remote.xlsx"
    _workbook(source)

    destination = download_dataset(source.as_uri(), tmp_path / "download")

    assert destination.name == "online_retail_II.xlsx"
    assert destination.read_bytes() == source.read_bytes()


def test_existing_workbook_is_not_overwritten_without_force(tmp_path: Path) -> None:
    output = tmp_path / "download"
    output.mkdir()
    existing = output / "online_retail_II.xlsx"
    _workbook(existing)

    result = download_dataset("https://invalid.example/not-called", output)

    assert result == existing
