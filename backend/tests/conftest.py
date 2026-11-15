"""Pytest Configuration for Balbird Intelligence Backend.
Enables offline-first deterministic test execution against in-memory repository store.
"""
import os
import pytest
from app.core.config import get_settings
from app.repositories.store import get_store

# Ensure tests run offline by default without hitting external cloud servers
os.environ["SUPABASE_URL"] = ""
os.environ["SUPABASE_ANON_KEY"] = ""
os.environ["SUPABASE_SERVICE_ROLE_KEY"] = ""
os.environ["AI_PROVIDER"] = "mock"

get_settings.cache_clear()


@pytest.fixture(autouse=True)
def clean_in_memory_store():
    """Reset the in-memory store before each test for complete isolation."""
    store = get_store()
    store.clear()
    yield
    store.clear()
