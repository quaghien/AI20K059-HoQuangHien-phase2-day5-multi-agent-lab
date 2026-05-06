from contextlib import contextmanager

from multi_agent_research_lab.observability.tracing import trace_run


class _FakeRemoteSpan:
    def __init__(self, *, name: str, input_payload: object, metadata: dict[str, object]) -> None:
        self.name = name
        self.input_payload = input_payload
        self.metadata = metadata
        self.updated: dict[str, object] = {}
        self.ended = False

    def update(self, **kwargs: object) -> None:
        self.updated.update(kwargs)

    def end(self) -> None:
        self.ended = True


class _FakeLangfuseClient:
    def __init__(self) -> None:
        self.started_spans: list[_FakeRemoteSpan] = []
        self.trace_updates: list[dict[str, object]] = []
        self.flushed = False

    @contextmanager
    def start_as_current_span(self, *, name: str, input: object, metadata: dict[str, object], end_on_exit: bool = False):
        del end_on_exit
        span = _FakeRemoteSpan(name=name, input_payload=input, metadata=metadata)
        self.started_spans.append(span)
        yield span

    def update_current_trace(self, **kwargs: object) -> None:
        self.trace_updates.append(kwargs)

    def flush(self) -> None:
        self.flushed = True


def test_trace_run_uses_distinct_root_span_name_and_updates_trace_output(monkeypatch) -> None:
    client = _FakeLangfuseClient()
    monkeypatch.setattr("multi_agent_research_lab.observability.tracing.get_langfuse_client", lambda settings=None: client)

    with trace_run(
        "cli.baseline",
        input_payload={"query": "Explain multi-agent systems"},
        metadata={"command": "baseline"},
        settings=None,
    ) as run:
        run["output"] = {"final_answer": "ok"}

    assert client.started_spans[0].name == "run.cli.baseline"
    assert client.started_spans[0].metadata["root_span"] is True
    assert client.trace_updates[0]["name"] == "cli.baseline"
    assert client.trace_updates[-1]["output"] == {"final_answer": "ok"}
    assert client.started_spans[0].updated["output"] == {"final_answer": "ok"}
    assert client.flushed is True


def test_trace_run_records_error_output_when_exception_occurs(monkeypatch) -> None:
    client = _FakeLangfuseClient()
    monkeypatch.setattr("multi_agent_research_lab.observability.tracing.get_langfuse_client", lambda settings=None: client)

    try:
        with trace_run(
            "cli.multi_agent",
            input_payload={"query": "Explain multi-agent systems"},
            metadata={"command": "multi-agent"},
            settings=None,
        ):
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert client.started_spans[0].name == "run.cli.multi_agent"
    assert client.trace_updates[-1]["output"] == {"error": "boom", "exception_type": "RuntimeError"}
    assert client.started_spans[0].updated["output"] == {"error": "boom", "exception_type": "RuntimeError"}
    assert client.started_spans[0].updated["level"] == "ERROR"
    assert client.flushed is True
