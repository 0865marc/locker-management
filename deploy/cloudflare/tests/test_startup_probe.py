"""Controlled startup, failure diagnostics and cleanup without native runtimes."""

import contextlib
import io
import json
import signal
import subprocess
import tempfile
import unittest
from http.client import RemoteDisconnected
from pathlib import Path
from unittest.mock import Mock, patch

import run_runtime
import run_spike
import startup_probe


class StartupProbeTests(unittest.TestCase):
    def test_disconnect_then_valid_response_recovers_and_cleans_group(self) -> None:
        process = Mock(spec=subprocess.Popen)
        process.poll.return_value = None
        process.pid = 123
        response = io.BytesIO(b'{"ok":true}')
        with tempfile.TemporaryDirectory() as directory:
            logfile = Path(directory) / "runtime.log"
            with (
                patch.object(startup_probe.subprocess, "Popen", return_value=process),
                patch.object(startup_probe.os, "killpg") as kill,
                patch.object(startup_probe.time, "monotonic", return_value=0),
                patch.object(startup_probe.time, "sleep") as sleep,
                patch.object(
                    startup_probe.CLIENT,
                    "open",
                    side_effect=[RemoteDisconnected("initial disconnect"), response],
                ) as opened,
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                with startup_probe.worker_process(
                    ["fake"], Path(directory), logfile
                ) as child:
                    result = startup_probe.wait_until_ready(
                        child, "http://local", json.load
                    )
            self.assertEqual(result, {"ok": True})
            self.assertEqual(opened.call_count, 2)
            sleep.assert_called_once_with(0.05)
            kill.assert_called_once_with(123, signal.SIGTERM)
            process.wait.assert_called_once_with(timeout=10)
            self.assertEqual(output.getvalue(), "")

    def test_deadline_is_not_reset_after_disconnect_and_diagnoses_before_cleanup(
        self,
    ) -> None:
        process = Mock(spec=subprocess.Popen)
        process.poll.return_value = None
        process.pid = 123
        now = [0.0]

        def disconnect(*args: object, **kwargs: object) -> None:
            now[0] += 45
            raise RemoteDisconnected("still disconnected")

        with tempfile.TemporaryDirectory() as directory:
            logfile = Path(directory) / "runtime.log"
            with (
                patch.object(startup_probe.subprocess, "Popen", return_value=process),
                patch.object(startup_probe.os, "killpg") as kill,
                patch.object(
                    startup_probe.time, "monotonic", side_effect=lambda: now[0]
                ),
                patch.object(startup_probe.time, "sleep"),
                patch.object(
                    startup_probe.CLIENT, "open", side_effect=disconnect
                ) as opened,
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):

                def cleanup(pid: int, sent: int) -> None:
                    self.assertIn(
                        "process status before cleanup: running", output.getvalue()
                    )

                kill.side_effect = cleanup
                with self.assertRaisesRegex(TimeoutError, "still disconnected"):
                    with startup_probe.worker_process(
                        ["fake"], Path(directory), logfile
                    ) as child:
                        startup_probe.wait_until_ready(child, "http://local")
            self.assertEqual(opened.call_count, 2)
            process.wait.assert_called_once_with(timeout=10)
            self.assertIn("RemoteDisconnected", output.getvalue())

    def test_late_success_is_rejected_and_request_timeout_uses_remaining_budget(
        self,
    ) -> None:
        process = Mock(spec=subprocess.Popen)
        process.poll.return_value = None
        now = [0.0]
        attempts: list[float] = []

        def open_response(url: str, timeout: float) -> io.BytesIO:
            attempts.append(timeout)
            if len(attempts) == 1:
                now[0] = 89.75
                raise RemoteDisconnected("transient")
            now[0] = 90.01
            return io.BytesIO(b"{}")

        with (
            patch.object(startup_probe.time, "monotonic", side_effect=lambda: now[0]),
            patch.object(startup_probe.time, "sleep"),
            patch.object(startup_probe.CLIENT, "open", side_effect=open_response),
        ):
            with self.assertRaisesRegex(TimeoutError, "arrived after"):
                startup_probe.wait_until_ready(process, "http://local", json.load)
        self.assertEqual(attempts, [1.0, 0.25])

    def test_exit_status_and_missing_log_preserve_original_failure_and_escalate(
        self,
    ) -> None:
        process = Mock(spec=subprocess.Popen)
        process.poll.return_value = 17
        process.pid = 123
        process.wait.side_effect = [subprocess.TimeoutExpired("fake", 10), 17]
        with tempfile.TemporaryDirectory() as directory:
            logfile = Path(directory) / "runtime.log"
            with (
                patch.object(startup_probe.subprocess, "Popen", return_value=process),
                patch.object(startup_probe.os, "killpg") as kill,
                patch.object(startup_probe.time, "monotonic", return_value=0),
                patch.object(startup_probe.CLIENT, "open") as opened,
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                with self.assertRaisesRegex(RuntimeError, "status=17"):
                    with startup_probe.worker_process(
                        ["fake"], Path(directory), logfile
                    ) as child:
                        logfile.unlink()
                        startup_probe.wait_until_ready(child, "http://local")
            opened.assert_not_called()
            self.assertIn("process status before cleanup: 17", output.getvalue())
            self.assertIn("log unavailable", output.getvalue())
            self.assertEqual(
                [call.args[1] for call in kill.call_args_list],
                [signal.SIGTERM, signal.SIGKILL],
            )

    def test_unexpected_decode_error_is_not_retried_and_cleanup_keeps_its_cause(
        self,
    ) -> None:
        process = Mock(spec=subprocess.Popen)
        process.poll.return_value = None
        process.pid = 123
        with tempfile.TemporaryDirectory() as directory:
            logfile = Path(directory) / "runtime.log"
            with (
                patch.object(startup_probe.subprocess, "Popen", return_value=process),
                patch.object(startup_probe.os, "killpg") as kill,
                patch.object(startup_probe.time, "monotonic", return_value=0),
                patch.object(
                    startup_probe.CLIENT, "open", return_value=io.BytesIO(b"bad JSON")
                ) as opened,
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                with self.assertRaises(json.JSONDecodeError):
                    with startup_probe.worker_process(
                        ["fake"], Path(directory), logfile
                    ) as child:
                        startup_probe.wait_until_ready(child, "http://local", json.load)
            self.assertEqual(opened.call_count, 1)
            kill.assert_called_once_with(123, signal.SIGTERM)
            self.assertIn("JSONDecodeError", output.getvalue())

    def test_log_tail_bounds_huge_lines_and_reports_unreadable_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            logfile = Path(directory) / "runtime.log"
            logfile.write_text("old-line\n" * 200 + "x" * 100000)
            tail = startup_probe.log_tail(logfile)
            self.assertLessEqual(len(tail.encode()), 65536)
            self.assertLessEqual(len(tail.splitlines()), 120)
            self.assertNotIn("old-line", tail)
            logfile.write_text("\n".join(str(n) for n in range(200)))
            self.assertEqual(
                startup_probe.log_tail(logfile).splitlines(),
                [str(n) for n in range(80, 200)],
            )
            with patch.object(Path, "open", side_effect=PermissionError):
                self.assertIn("PermissionError", startup_probe.log_tail(logfile))

    def test_both_runners_share_recovery_and_cleanup_on_success_and_failure(
        self,
    ) -> None:
        for runner in (run_spike, run_runtime):
            for fails in (False, True):
                with (
                    self.subTest(runner=runner.__name__, fails=fails),
                    tempfile.TemporaryDirectory() as directory,
                ):
                    process = Mock(spec=subprocess.Popen)
                    process.poll.return_value = None
                    process.pid = 123
                    root = Path(directory)
                    results = (
                        [ValueError("unexpected startup error")]
                        if fails
                        else [RemoteDisconnected("transient"), io.BytesIO(b"{}")]
                    )
                    with (
                        patch.object(runner, "CLOUDFLARE", root),
                        patch.object(run_spike, "EVIDENCE", root / "evidence"),
                        patch.object(runner, "run"),
                        patch.object(run_runtime.socket, "socket") as socket_factory,
                        patch.object(
                            startup_probe.subprocess, "Popen", return_value=process
                        ),
                        patch.object(run_runtime.subprocess, "run"),
                        patch.object(startup_probe.os, "killpg") as kill,
                        patch.object(startup_probe.time, "monotonic", return_value=0),
                        patch.object(startup_probe.time, "sleep"),
                        patch.object(
                            startup_probe.CLIENT, "open", side_effect=results
                        ) as opened,
                        patch.dict("os.environ", {}, clear=False),
                        contextlib.redirect_stdout(io.StringIO()) as output,
                    ):
                        socket_factory.return_value.__enter__.return_value.getsockname.return_value = (
                            "127.0.0.1",
                            8123,
                        )
                        if fails:
                            with self.assertRaisesRegex(
                                ValueError, "unexpected startup error"
                            ):
                                runner.main()
                            self.assertIn(
                                "process status before cleanup: running",
                                output.getvalue(),
                            )
                        else:
                            runner.main()
                            self.assertEqual(opened.call_count, 2)
                        kill.assert_called_once_with(123, signal.SIGTERM)
                        process.wait.assert_called_once_with(timeout=10)

    def test_spike_selects_startup_units_before_sync_without_running_native(
        self,
    ) -> None:
        commands: list[list[str]] = []

        class StopBeforeNative(Exception):
            pass

        def record(
            command: list[str], logfile: str, environment: dict[str, str] | None = None
        ) -> None:
            commands.append(command)
            if command == ["uv", "run", "--locked", "pywrangler", "sync"]:
                raise StopBeforeNative

        with tempfile.TemporaryDirectory() as directory:
            with (
                patch.object(run_spike, "EVIDENCE", Path(directory)),
                patch.object(run_spike, "run", side_effect=record),
            ):
                with self.assertRaises(StopBeforeNative):
                    run_spike.main()
        selection = next(
            command for command in commands if "test_startup_*.py" in command
        )
        self.assertLess(commands.index(selection), len(commands) - 1)
        suite = unittest.TestLoader().discover(
            str(Path(__file__).parent), pattern="test_startup_*.py"
        )
        self.assertGreaterEqual(suite.countTestCases(), 7)
