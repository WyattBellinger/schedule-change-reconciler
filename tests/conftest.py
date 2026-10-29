import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def fixture(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def arguments():
    return fixture("example.json")


@pytest.fixture
def expected():
    return fixture("example-expected.json")
