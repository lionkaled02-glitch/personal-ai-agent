from pathlib import Path

from src import api


def test_health() -> None:
    assert api.health()["status"] == "ok"


def test_task_store_is_configurable(tmp_path: Path) -> None:
    original = api.store
    try:
        api.store = api.TaskStore(tmp_path / "tasks.sqlite3")
        response = api.create_task(api.TaskRequest(request="Run the demo tool."))
        assert response["task_id"]
        assert response["status"] in {"accepted", "completed"}
    finally:
        api.store = original
