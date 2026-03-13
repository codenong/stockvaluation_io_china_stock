import importlib
import threading
import time


def test_get_notebook_service_initializes_singleton_once_under_concurrency(monkeypatch, tmp_path):
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))

    service_module = importlib.import_module("services.notebook_service")
    service_module._notebook_service = None

    created_instances = []
    real_init = service_module.NotebookService.__init__

    def wrapped_init(self):
        created_instances.append(object())
        time.sleep(0.05)
        real_init(self)

    monkeypatch.setattr(service_module.NotebookService, "__init__", wrapped_init)

    results = []
    errors = []

    def worker():
        try:
            results.append(service_module.get_notebook_service())
        except Exception as exc:  # pragma: no cover - failure path assertion below
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors
    assert len(created_instances) == 1
    assert len(results) == 6
    assert len({id(instance) for instance in results}) == 1
