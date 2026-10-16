"""Concurrency regressions for process-wide graph and retriever singletons."""

from concurrent.futures import ThreadPoolExecutor
import threading
import time

import pytest

import src.graph as graph
import src.vector_store as vector_store


@pytest.mark.parametrize(
    ("module", "factory_name", "instance_name", "getter_name"),
    [
        (graph, "build_graph", "_compiled_graph", "get_graph"),
        (
            vector_store,
            "HybridBgeRetriever",
            "_retriever_instance",
            "get_retriever",
        ),
    ],
)
def test_concurrent_first_use_constructs_single_resource(
    monkeypatch,
    module,
    factory_name,
    instance_name,
    getter_name,
):
    constructor_calls = 0
    calls_lock = threading.Lock()
    start_together = threading.Barrier(8)

    class FakeResource:
        def __init__(self):
            nonlocal constructor_calls
            with calls_lock:
                constructor_calls += 1
            time.sleep(0.02)

    monkeypatch.setattr(module, factory_name, FakeResource)
    monkeypatch.setattr(module, instance_name, None)
    if module is vector_store:
        monkeypatch.setattr(module, "EMBEDDING_BACKEND", "bge")

    getter = getattr(module, getter_name)

    def get_together(_):
        start_together.wait()
        return getter()

    with ThreadPoolExecutor(max_workers=8) as executor:
        resources = list(executor.map(get_together, range(8)))

    assert constructor_calls == 1
    assert len({id(resource) for resource in resources}) == 1
