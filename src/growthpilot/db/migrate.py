from alembic import command
from alembic.config import Config

from growthpilot.config import find_project_root


def alembic_config(database_url: str) -> Config:
    root = find_project_root()
    config = Config(root / "alembic.ini")
    config.set_main_option("script_location", str(root / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))
    return config


def upgrade_database(database_url: str, revision: str = "head") -> None:
    command.upgrade(alembic_config(database_url), revision)
