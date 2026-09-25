import shutil
from pathlib import Path

import pytest

FIXTURE_DATA = Path(__file__).parent / "fixtures" / "data"


@pytest.fixture
def data_dir(tmp_path: Path) -> Path:
    """A writable copy of the fixture data."""
    return Path(shutil.copytree(FIXTURE_DATA, tmp_path / "data"))
