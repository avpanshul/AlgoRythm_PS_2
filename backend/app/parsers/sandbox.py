r"""Parser sandboxing (ULPF-master-prompt.md Part D6): run untrusted parser
input in an isolated OS process with CPU/time/memory limits, rather than
in-process where a malicious or pathological sample (e.g. a catastrophic
regex-backtracking payload) could hang or exhaust the whole API server.

Scope, and why: this wraps the parser *fixture test* path
(POST /parsers/{id}/test and the publish-time fixture check) -- the exact
moment an operator is trying out a new, unvetted vendor sample. It does
**not** wrap the high-volume bulk ingestion path (app/core/processing.py),
where every event already goes through a format that passed this same
fixture test before being published; adding a process-spawn per event there
would be a real, measured performance cost (see docs/benchmarks.md's
existing per-event overhead findings) for a boundary that isn't actually
untrusted at that point.

Platform honesty: wall-clock timeout enforcement (Process.terminate()) works
identically on Windows and POSIX -- multiprocessing spawns a real OS
process either way, and terminating it actually stops CPU-bound hangs,
unlike a thread-based timeout. CPU-time and memory *rlimits*
(resource.setrlimit) are POSIX-only; on Windows they are skipped, which is
a genuine, stated gap (a memory-exhausting-but-fast sample would still be
caught by the wall-clock timeout eventually finishing, but not by a hard
memory cap) rather than something silently claimed to work everywhere.
"""
import multiprocessing
import os


def _sandboxed_worker(raw_log: str, format_type: str, config_yaml, out_queue):
    if os.name == "posix":
        try:
            import resource
            resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
            resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
        except (ImportError, ValueError, OSError):
            pass  # best-effort -- some platforms/containers restrict setrlimit itself

    try:
        import yaml
        from app.parsers.deterministic import parse_log
        from app.core.processing import normalize_parsed_data, normalize_with_source_pack, redact_pii

        config_json = yaml.safe_load(config_yaml) if config_yaml else None
        parsed = parse_log(raw_log, format_type)
        if not parsed or parsed == {}:
            out_queue.put({"status": "failed", "error": "Parser returned no data"})
            return

        if config_json and config_json.get("field_mappings"):
            normalized = normalize_with_source_pack(parsed, config_json, raw_log)
            mapping_method = "source_pack"
        else:
            normalized = normalize_parsed_data(parsed, format_type, raw_log)
            mapping_method = "deterministic (no field_mappings in config -- add some to test the source pack itself)"

        redacted_message, _ = redact_pii(normalized.get("message") or "")
        normalized["message"] = redacted_message

        missing = [f for f in ("event_data", "source_ip") if not normalized.get(f)]
        out_queue.put({
            "status": "success" if not missing else "warning",
            "mapping_method": mapping_method,
            "parsed_raw": parsed,
            "normalized_ecs": normalized,
            "missing_required_fields": missing,
        })
    except Exception as e:  # noqa: BLE001 -- any exception in untrusted-input parsing is a fixture failure, not a server error
        out_queue.put({"status": "error", "error": str(e)})


def run_parser_fixture_sandboxed(raw_log: str, format_type: str, config_yaml=None, timeout_seconds: float = 20.0) -> dict:
    """Runs a parser's fixture test in a separate process with a hard
    wall-clock timeout. Returns the same shape as the in-process fixture
    test, plus a `sandbox_timeout` status if the sample didn't finish in
    time (a strong, honest signal that a sample is pathological, not
    something to silently retry in-process)."""
    ctx = multiprocessing.get_context("spawn")
    out_queue = ctx.Queue()
    proc = ctx.Process(target=_sandboxed_worker, args=(raw_log, format_type, config_yaml, out_queue))
    proc.start()
    proc.join(timeout=timeout_seconds)

    if proc.is_alive():
        proc.terminate()
        proc.join(timeout=1.0)
        if proc.is_alive():
            proc.kill()
        return {
            "status": "sandbox_timeout",
            "error": f"Parser did not finish within {timeout_seconds}s -- treated as a hostile/pathological "
                     f"sample and killed, not retried in-process.",
        }

    if not out_queue.empty():
        return out_queue.get()
    return {"status": "error", "error": f"Sandboxed parser process exited (code {proc.exitcode}) without a result -- likely crashed or was killed by the OS (e.g. OOM)."}
