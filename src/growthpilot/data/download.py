import io
import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path


class DownloadError(RuntimeError):
    """Raised when a downloaded payload is not a supported retail workbook."""


def _find_workbook(directory: Path) -> Path:
    workbooks = sorted([*directory.rglob("*.xlsx"), *directory.rglob("*.xls")])
    if len(workbooks) != 1:
        raise DownloadError(f"Expected exactly one workbook in archive, found {len(workbooks)}")
    return workbooks[0]


def download_dataset(url: str, output_dir: Path, *, force: bool = False) -> Path:
    """Download an official ZIP/XLSX payload and return the local workbook path."""
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / "online_retail_II.xlsx"
    if destination.exists() and not force:
        return destination

    request = urllib.request.Request(url, headers={"User-Agent": "GrowthPilot/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            payload = response.read()
    except Exception as exc:  # urllib exposes several environment-specific subclasses
        raise DownloadError(f"Could not download dataset from {url}: {exc}") from exc

    if len(payload) < 1_000:
        raise DownloadError("Downloaded payload is unexpectedly small")

    with tempfile.TemporaryDirectory(prefix="growthpilot-download-") as tmp:
        temp_dir = Path(tmp)
        if zipfile.is_zipfile(io.BytesIO(payload)):
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                names = archive.namelist()
                is_xlsx = "[Content_Types].xml" in names and any(
                    name.startswith("xl/") for name in names
                )
                if is_xlsx:
                    source = temp_dir / "source.xlsx"
                    source.write_bytes(payload)
                    names = []
                unsafe = [
                    name for name in names if Path(name).is_absolute() or ".." in Path(name).parts
                ]
                if unsafe:
                    raise DownloadError("Archive contains an unsafe path")
                if not is_xlsx:
                    archive.extractall(temp_dir)
            if not is_xlsx:
                source = _find_workbook(temp_dir)
        else:
            raise DownloadError("Payload is neither a ZIP archive nor an XLSX workbook")

        with tempfile.NamedTemporaryFile(dir=output_dir, delete=False) as handle:
            staged = Path(handle.name)
        try:
            shutil.copyfile(source, staged)
            staged.replace(destination)
        finally:
            staged.unlink(missing_ok=True)
    return destination
