import argparse
from pathlib import Path

from growthpilot.config import DEFAULT_UCI_URL, ProjectPaths
from growthpilot.data.download import download_dataset
from growthpilot.data.pipeline import run_phase1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="growthpilot", description="GrowthPilot CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download", help="Download the official UCI workbook")
    download.add_argument("--url", default=DEFAULT_UCI_URL)
    download.add_argument("--output-dir", type=Path, default=ProjectPaths().raw)
    download.add_argument("--force", action="store_true")

    phase1 = subparsers.add_parser("phase1", help="Run cleaning, quality checks, and EDA")
    phase1.add_argument("--input", type=Path, required=True)
    phase1.add_argument("--processed-dir", type=Path, default=ProjectPaths().processed)
    phase1.add_argument("--report-dir", type=Path, default=ProjectPaths().reports)
    phase1.add_argument("--fail-on-quality", action=argparse.BooleanOptionalAction, default=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "download":
        path = download_dataset(args.url, args.output_dir, force=args.force)
        print(f"Dataset ready: {path}")
        return 0

    result = run_phase1(
        args.input,
        processed_dir=args.processed_dir,
        report_dir=args.report_dir,
        fail_on_quality=args.fail_on_quality,
    )
    print(f"Phase 1 complete: {result.quality_report_path}")
    print(
        f"Rows: {result.input_rows} input -> {result.purchase_rows} purchases, "
        f"{result.return_rows} returns, {result.rejected_rows} rejected"
    )
    return 0
