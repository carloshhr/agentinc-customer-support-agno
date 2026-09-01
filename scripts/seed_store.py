"""Idempotently seed the mock store data and dedicated catalog knowledge."""

from pathlib import Path

from agno.knowledge.reader.markdown_reader import MarkdownReader

from app.store import ensure_store_schema, get_store_repository
from app.store_knowledge import store_knowledge


def seed_store() -> None:
    """Create storage, insert immutable fixtures, and upsert the catalog Markdown."""
    repository = get_store_repository()
    ensure_store_schema(repository.engine)
    repository.seed_orders()
    catalog_path = Path(__file__).resolve().parents[1] / "knowledge" / "store_catalog.md"
    store_knowledge.insert(path=str(catalog_path), reader=MarkdownReader(), skip_if_exists=False)


if __name__ == "__main__":
    seed_store()
