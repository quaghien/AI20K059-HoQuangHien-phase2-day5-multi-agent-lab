"""Tracing hooks with optional Langfuse integration."""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
import logging
from time import perf_counter
from typing import Any

from multi_agent_research_lab.core.config import Settings, get_settings

logger = logging.getLogger(__name__)
_CURRENT_LANGFUSE_CLIENT: ContextVar[Any | None] = ContextVar("current_langfuse_client", default=None)


def get_langfuse_client(settings: Settings | None = None) -> Any | None:
    """Return a Langfuse client when credentials and package are available."""

    resolved_settings = settings or get_settings()
    if not resolved_settings.langfuse_public_key or not resolved_settings.langfuse_secret_key:
        return None

    try:
        from langfuse import Langfuse
    except ImportError:
        logger.debug("Langfuse package is not installed; continuing without remote tracing.")
        return None

    try:
        return Langfuse(
            public_key=resolved_settings.langfuse_public_key,
            secret_key=resolved_settings.langfuse_secret_key,
            host=resolved_settings.langfuse_host,
        )
    except Exception:
        logger.exception("Failed to initialize Langfuse client; continuing without remote tracing.")
        return None


@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
    *,
    langfuse_client: Any | None = None,
    input_payload: Any | None = None,
) -> Iterator[dict[str, Any]]:
    """Track a local span and mirror it to Langfuse when available."""

    started = perf_counter()
    span: dict[str, Any] = {
        "name": name,
        "attributes": attributes or {},
        "duration_seconds": None,
        "input": input_payload,
        "output": None,
    }
    resolved_client = langfuse_client or _CURRENT_LANGFUSE_CLIENT.get()
    remote_span = None
    remote_span_cm = None

    if resolved_client is not None:
        try:
            remote_span_cm = resolved_client.start_as_current_span(
                name=name,
                input=input_payload,
                metadata=span["attributes"],
                end_on_exit=False,
            )
            remote_span = remote_span_cm.__enter__()
        except Exception:
            logger.exception("Failed to start Langfuse span for %s.", name)
            remote_span = None
            remote_span_cm = None

    try:
        yield span
    except Exception as exc:
        span["attributes"]["error"] = str(exc)
        raise
    finally:
        span["duration_seconds"] = perf_counter() - started
        if remote_span is not None:
            try:
                remote_span.update(
                    output=span["output"],
                    metadata=span["attributes"],
                    level="ERROR" if "error" in span["attributes"] else "DEFAULT",
                )
                remote_span.end()
                if remote_span_cm is not None:
                    remote_span_cm.__exit__(None, None, None)
            except Exception:
                logger.exception("Failed to end Langfuse span for %s.", name)


@contextmanager
def trace_generation(
    name: str,
    *,
    model: str,
    input_payload: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    langfuse_client: Any | None = None,
) -> Iterator[dict[str, Any]]:
    """Track an LLM generation and mirror prompt/completion to Langfuse."""

    started = perf_counter()
    generation: dict[str, Any] = {
        "name": name,
        "model": model,
        "input": input_payload,
        "metadata": metadata or {},
        "output": None,
        "usage": {},
        "cost_usd": None,
        "duration_seconds": None,
    }
    resolved_client = langfuse_client or _CURRENT_LANGFUSE_CLIENT.get()
    remote_generation = None
    remote_generation_cm = None

    if resolved_client is not None:
        try:
            remote_generation_cm = resolved_client.start_as_current_generation(
                name=name,
                model=model,
                input=input_payload,
                metadata=generation["metadata"],
                end_on_exit=False,
            )
            remote_generation = remote_generation_cm.__enter__()
        except Exception:
            logger.exception("Failed to start Langfuse generation for %s.", name)
            remote_generation = None
            remote_generation_cm = None

    try:
        yield generation
    except Exception as exc:
        generation["metadata"]["error"] = str(exc)
        raise
    finally:
        generation["duration_seconds"] = perf_counter() - started
        if remote_generation is not None:
            try:
                remote_generation.update(
                    output=generation["output"],
                    usage_details=generation["usage"] or None,
                    metadata=generation["metadata"],
                    cost_details={"total_cost": generation["cost_usd"]}
                    if generation["cost_usd"] is not None
                    else None,
                    level="ERROR" if "error" in generation["metadata"] else "DEFAULT",
                )
                remote_generation.end()
                if remote_generation_cm is not None:
                    remote_generation_cm.__exit__(None, None, None)
            except Exception:
                logger.exception("Failed to end Langfuse generation for %s.", name)


@contextmanager
def trace_run(
    name: str,
    *,
    input_payload: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    settings: Settings | None = None,
) -> Iterator[dict[str, Any]]:
    """Create a root trace/span for an end-to-end CLI run."""

    resolved_settings = settings or get_settings()
    client = get_langfuse_client(resolved_settings)
    run: dict[str, Any] = {"name": name, "input": input_payload, "output": None, "metadata": metadata or {}}
    root_span_name = f"run.{name}"
    token = _CURRENT_LANGFUSE_CLIENT.set(client)
    remote_span = None
    remote_span_cm = None

    if client is not None:
        try:
            remote_span_cm = client.start_as_current_span(
                name=root_span_name,
                input=input_payload,
                metadata={**run["metadata"], "root_span": True, "trace_name": name},
                end_on_exit=False,
            )
            remote_span = remote_span_cm.__enter__()
            client.update_current_trace(
                name=name,
                input=input_payload,
                metadata=run["metadata"],
            )
        except Exception:
            logger.exception("Failed to create Langfuse root trace for %s.", name)
            remote_span = None
            remote_span_cm = None

    try:
        yield run
    except Exception as exc:
        if run["output"] is None:
            run["output"] = {"error": str(exc), "exception_type": exc.__class__.__name__}
        run["metadata"]["error"] = str(exc)
        raise
    finally:
        if client is not None:
            try:
                client.update_current_trace(
                    name=name,
                    input=input_payload,
                    output=run["output"],
                    metadata=run["metadata"],
                )
                if remote_span is not None:
                    remote_span.update(
                        output=run["output"],
                        metadata={**run["metadata"], "root_span": True, "trace_name": name},
                        level="ERROR" if "error" in run["metadata"] else "DEFAULT",
                    )
                    remote_span.end()
                if remote_span_cm is not None:
                    remote_span_cm.__exit__(None, None, None)
                flush_traces(client)
            except Exception:
                logger.exception("Failed to finalize Langfuse root trace for %s.", name)
        _CURRENT_LANGFUSE_CLIENT.reset(token)


def flush_traces(langfuse_client: Any | None) -> None:
    """Flush provider traces when supported."""

    if langfuse_client is None:
        return

    try:
        langfuse_client.flush()
    except Exception:
        logger.exception("Failed to flush Langfuse traces.")
