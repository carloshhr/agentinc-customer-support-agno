import os

from alembic import context
from app.models import Base
from sqlalchemy import engine_from_config, pool

config = context.config
target_metadata = Base.metadata
database_url = os.getenv("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url.replace("%", "%%"))


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        # Alembic's version table lives in the dedicated schema and therefore
        # needs the schema before Alembic can create that table.
        connection.execution_options(isolation_level="AUTOCOMMIT").exec_driver_sql(
            "CREATE SCHEMA IF NOT EXISTS support_inbox"
        )
        context.configure(connection=connection, target_metadata=target_metadata, version_table_schema="support_inbox")
        with context.begin_transaction():
            context.run_migrations()
            if context.get_context().opts.get("destination_rev") == "base":
                connection.exec_driver_sql("DROP SCHEMA IF EXISTS support_inbox CASCADE")


run_migrations_online()
