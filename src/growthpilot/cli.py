import argparse
from pathlib import Path

from growthpilot.config import DEFAULT_UCI_URL, ProjectPaths
from growthpilot.data.demo import generate_demo_transactions
from growthpilot.data.download import download_dataset
from growthpilot.data.pipeline import run_phase1
from growthpilot.db.loader import load_processed_data
from growthpilot.db.migrate import upgrade_database
from growthpilot.db.session import build_engine, resolve_database_url
from growthpilot.features.contract import DEFAULT_FEATURE_VERSION
from growthpilot.features.service import build_and_store_features
from growthpilot.ml.orchestrator import train_all


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="growthpilot", description="GrowthPilot CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    download = subparsers.add_parser("download", help="Download the official UCI workbook")
    download.add_argument("--url", default=DEFAULT_UCI_URL)
    download.add_argument("--output-dir", type=Path, default=ProjectPaths().raw)
    download.add_argument("--force", action="store_true")

    demo = subparsers.add_parser(
        "demo-data", help="Generate a deterministic synthetic demo dataset"
    )
    demo.add_argument(
        "--output",
        type=Path,
        default=ProjectPaths().root / "data" / "demo" / "demo_transactions.csv",
    )
    demo.add_argument("--customers", type=int, default=240)
    demo.add_argument("--seed", type=int, default=42)

    phase1 = subparsers.add_parser("phase1", help="Run cleaning, quality checks, and EDA")
    phase1.add_argument("--input", type=Path, required=True)
    phase1.add_argument("--processed-dir", type=Path, default=ProjectPaths().processed)
    phase1.add_argument("--report-dir", type=Path, default=ProjectPaths().reports)
    phase1.add_argument("--fail-on-quality", action=argparse.BooleanOptionalAction, default=True)

    upgrade = subparsers.add_parser("db-upgrade", help="Apply all database migrations")
    upgrade.add_argument("--database-url")

    load = subparsers.add_parser("load-db", help="Load Phase 1 outputs into the database")
    load.add_argument("--database-url")
    load.add_argument(
        "--purchases", type=Path, default=ProjectPaths().processed / "transactions_clean.csv"
    )
    load.add_argument(
        "--returns", type=Path, default=ProjectPaths().processed / "transactions_returns.csv"
    )
    load.add_argument("--workspace-slug", default="demo-retail")
    load.add_argument("--workspace-name", default="Demo Retail")
    load.add_argument("--currency", default="GBP")
    load.add_argument("--chunk-size", type=int, default=25_000)

    features = subparsers.add_parser(
        "build-features", help="Build and persist a cutoff-safe customer feature snapshot"
    )
    features.add_argument("--database-url")
    features.add_argument("--workspace-slug", default="demo-retail")
    features.add_argument("--as-of", required=True)
    features.add_argument("--feature-version", default=DEFAULT_FEATURE_VERSION)
    features.add_argument(
        "--output", type=Path, default=ProjectPaths().processed / "customer_features.csv"
    )

    train = subparsers.add_parser(
        "train-all", help="Train, evaluate, and persist all intelligence models"
    )
    train.add_argument("--database-url")
    train.add_argument("--workspace-slug", default="demo-retail")
    train.add_argument(
        "--artifact-dir", type=Path, default=ProjectPaths().root / "artifacts" / "models"
    )
    train.add_argument(
        "--training-output",
        type=Path,
        default=ProjectPaths().processed / "supervised_snapshots.csv",
    )

    serve = subparsers.add_parser("serve", help="Run the FastAPI application")
    serve.add_argument("--host", default="0.0.0.0")
    serve.add_argument("--port", type=int, default=8000)
    serve.add_argument("--reload", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "download":
        path = download_dataset(args.url, args.output_dir, force=args.force)
        print(f"Dataset ready: {path}")
        return 0

    if args.command == "demo-data":
        path = generate_demo_transactions(args.output, customers=args.customers, seed=args.seed)
        print(f"Synthetic demo dataset ready: {path}")
        return 0

    if args.command == "db-upgrade":
        upgrade_database(resolve_database_url(args.database_url))
        print("Database schema is at the latest revision")
        return 0

    if args.command == "load-db":
        engine = build_engine(resolve_database_url(args.database_url))
        result = load_processed_data(
            engine,
            args.purchases,
            args.returns,
            workspace_slug=args.workspace_slug,
            workspace_name=args.workspace_name,
            currency=args.currency,
            chunk_size=args.chunk_size,
        )
        action = "Skipped existing import" if result.skipped else "Loaded database"
        print(
            f"{action}: {result.loaded_rows} rows "
            f"({result.purchase_rows} purchases, {result.return_rows} returns)"
        )
        return 0

    if args.command == "build-features":
        engine = build_engine(resolve_database_url(args.database_url))
        result = build_and_store_features(
            engine,
            workspace_slug=args.workspace_slug,
            as_of=args.as_of,
            feature_version=args.feature_version,
            output_path=args.output,
        )
        action = "Skipped existing snapshot" if result.skipped else "Built feature snapshot"
        print(
            f"{action}: {result.customer_count} customers as of "
            f"{result.as_of.isoformat()} ({result.feature_version})"
        )
        return 0

    if args.command == "train-all":
        engine = build_engine(resolve_database_url(args.database_url))
        result = train_all(
            engine,
            workspace_slug=args.workspace_slug,
            artifact_dir=args.artifact_dir,
            training_output=args.training_output,
        )
        print(
            f"Training complete: {result.customers} current customers, "
            f"{result.supervised_rows} historical snapshots"
        )
        for name, path in result.artifacts.items():
            print(f"  {name}: {path}")
        return 0

    if args.command == "serve":
        import uvicorn

        uvicorn.run("growthpilot.api.main:app", host=args.host, port=args.port, reload=args.reload)
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
