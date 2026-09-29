"""Tests for parser sandboxing (ULPF-master-prompt.md Part D6): untrusted
parser input runs in an isolated, time-limited OS process."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.parsers.sandbox import run_parser_fixture_sandboxed


def _hang_forever(out_queue):
    """Module-level (not a closure) so it's picklable under Windows'
    "spawn" multiprocessing start method."""
    import time
    while True:
        time.sleep(0.1)


class TestParserSandbox:
    def test_normal_cef_sample_succeeds(self):
        result = run_parser_fixture_sandboxed(
            "CEF:0|Palo Alto|PAN-OS|10.1|4000|Traffic Deny|7|src=192.168.1.20 dst=10.0.0.5 dpt=22 act=deny",
            "CEF",
        )
        assert result["status"] == "success"
        assert result["normalized_ecs"]["source_ip"] == "192.168.1.20"

    def test_garbage_input_fails_cleanly_not_a_server_error(self):
        result = run_parser_fixture_sandboxed("not a real format at all", "JSON")
        assert result["status"] in ("failed", "error")

    def test_normal_call_completes_well_within_timeout(self):
        import time as _time
        start = _time.monotonic()
        result = run_parser_fixture_sandboxed(
            "CEF:0|V|P|1.0|1|E|1|src=1.1.1.1", "CEF", timeout_seconds=5.0,
        )
        assert _time.monotonic() - start < 5.0
        assert result["status"] in ("success", "warning", "failed", "error")

    def test_the_underlying_process_timeout_mechanism_actually_kills_a_hang(self):
        """Exercises the same Process.start/join(timeout)/terminate() pattern
        run_parser_fixture_sandboxed uses, against a target engineered to
        hang forever -- proves the sandbox would actually stop a
        pathological parse, not just a well-behaved one that happens to
        finish quickly. Doesn't go through the parser code itself (nothing
        in this repo's real parsers is known to hang), so it verifies the
        sandboxing *mechanism* directly."""
        import multiprocessing
        import time as _time

        ctx = multiprocessing.get_context("spawn")
        q = ctx.Queue()
        proc = ctx.Process(target=_hang_forever, args=(q,))
        start = _time.monotonic()
        proc.start()
        proc.join(timeout=1.0)
        assert proc.is_alive()  # still running -- the timeout alone doesn't kill it
        proc.terminate()
        proc.join(timeout=2.0)
        elapsed = _time.monotonic() - start

        assert not proc.is_alive()  # terminate() actually stopped the OS process
        assert elapsed < 5.0  # didn't hang forever waiting for a "hang forever" target
