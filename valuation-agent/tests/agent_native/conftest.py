import pytest

from valuation_agent.workflow_run_state import RUN_STATE_DIR_ENV


@pytest.fixture(autouse=True)
def isolated_run_state_dir(tmp_path, monkeypatch):
    """Keep workflow run state out of the developer's real home directory."""
    monkeypatch.setenv(RUN_STATE_DIR_ENV, str(tmp_path / "run_state"))
