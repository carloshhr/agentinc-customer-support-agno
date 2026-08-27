"""Dedicated product knowledge base, isolated from platform-wide knowledge."""

from agno.knowledge import Knowledge

from db import create_knowledge

STORE_KNOWLEDGE_NAME = "store-product-knowledge"
store_knowledge: Knowledge = create_knowledge(STORE_KNOWLEDGE_NAME, "store_product_knowledge")
