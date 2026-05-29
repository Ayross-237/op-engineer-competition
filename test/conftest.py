"""Shared test configuration.

Seeds Python's random module before every test so any weighted_random /
random.choices call produces a deterministic sequence — keeps the menu
distribution tests from flaking.
"""
import random

import pytest


@pytest.fixture(autouse=True)
def _seed_random():
    random.seed(42)
    yield
