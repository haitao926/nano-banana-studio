import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[2]
SKILL_ROOT = REPO_ROOT / ".codex" / "skills" / "roil-drawing" / "scripts"


def _load_script_module(name: str, filename: str) -> ModuleType:
    module_path = SKILL_ROOT / filename
    spec = importlib.util.spec_from_file_location(name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


roil_preflight = _load_script_module("test_roil_preflight", "roil_preflight.py")
sys.modules.setdefault("roil_preflight", roil_preflight)
roil_draw = _load_script_module("test_roil_draw", "roil_draw.py")


class RoilPreflightTests(unittest.TestCase):
    def test_candidate_base_urls_prefer_stored_and_platform_before_lan(self) -> None:
        candidates = roil_preflight._candidate_base_urls(
            "https://image.roil.top/",
            "http://10.15.46.72:8002",
            {"base_url": "http://10.15.46.72:8002"},
        )

        self.assertEqual(
            candidates,
            ["https://image.roil.top", "http://10.15.46.72:8002"],
        )

    def test_build_status_prefers_authenticated_cli_backend(self) -> None:
        with patch.object(roil_preflight, "probe_platform", return_value={"reachable": True}), patch.object(
            roil_preflight,
            "detect_nbs_cli",
            return_value={"available": True, "path": "/repo/nbs", "source": "cwd"},
        ), patch.object(
            roil_preflight,
            "inspect_nbs_auth",
            return_value={"session_available": True},
        ):
            status = roil_preflight.build_status(check_platform=True)

        self.assertEqual(status["recommended_next_step"], "generate_via_nbs_cli_backend")
        self.assertEqual(status["decision_summary"]["category"], "cli_backend_ready")
        self.assertIn("Authenticated NBS session", status["decision_summary"]["reason"])
        for field in (
            "skill",
            "platform_url",
            "platform_probe",
            "nbs_cli",
            "nbs_auth",
            "fallback_key_available",
            "agent_contract",
            "recommended_commands",
            "decision_summary",
            "recommended_next_step",
            "safe_to_show_user",
        ):
            self.assertIn(field, status)
        self.assertIn("draw", status["recommended_commands"])
        self.assertIn("preflight", status["recommended_commands"])
        self.assertTrue(status["recommended_commands"]["draw"].endswith("--json"))
        self.assertTrue(status["recommended_commands"]["preflight"].endswith("roil_preflight.py --json"))
        self.assertEqual(status["safe_to_show_user"]["login_url"], "https://image.roil.top/")
        self.assertIn("must_not_do", status["agent_contract"])
        self.assertTrue(
            any("Do not inspect ~/.nbs/auth.json" in item for item in status["agent_contract"]["must_not_do"])
        )

    def test_build_status_prefers_cli_direct_when_no_session(self) -> None:
        with patch.object(roil_preflight, "probe_platform", return_value={"reachable": True}), patch.object(
            roil_preflight,
            "detect_nbs_cli",
            return_value={"available": True, "path": "/repo/nbs", "source": "cwd"},
        ), patch.object(
            roil_preflight,
            "inspect_nbs_auth",
            return_value={"session_available": False},
        ):
            status = roil_preflight.build_status(check_platform=True)

        self.assertEqual(status["recommended_next_step"], "try_nbs_cli_direct")
        self.assertEqual(status["decision_summary"]["category"], "cli_direct_only")
        self.assertFalse(status["nbs_auth"]["cli_probe"]["success"])

    def test_build_status_prefers_platform_when_lan_login_is_unreachable(self) -> None:
        auth_info = {
            "auth_file_present": True,
            "access_token_present": True,
            "stored_base_url": "http://10.15.46.72:8002",
            "session_available": False,
            "probes": [
                {
                    "base_url": "http://10.15.46.72:8002",
                    "valid": False,
                    "reachable": False,
                    "error": "timed out",
                }
            ],
            "cli_probe": {"success": False},
        }
        with patch.object(roil_preflight, "probe_platform", return_value={"reachable": True}), patch.object(
            roil_preflight,
            "detect_nbs_cli",
            return_value={"available": True, "path": "/repo/nbs", "source": "cwd"},
        ), patch.object(
            roil_preflight,
            "inspect_nbs_auth",
            return_value=dict(auth_info),
        ):
            status = roil_preflight.build_status(check_platform=True)

        self.assertEqual(status["recommended_next_step"], "open_or_login_platform")
        self.assertEqual(status["decision_summary"]["category"], "platform_login_handoff")

    def test_build_status_uses_nbs_cli_probe_when_http_probe_disagrees(self) -> None:
        auth_info = {
            "auth_file_path": "/tmp/auth.json",
            "auth_file_present": True,
            "candidate_base_urls": ["https://image.roil.top"],
            "session_available": False,
            "session_base_url": None,
            "session_user": None,
            "quota_remaining": None,
            "quota_limit": None,
            "quota_used": None,
            "error": "Stored session token was not accepted by any candidate Roil endpoint.",
        }
        cli_probe = {
            "attempted": True,
            "success": True,
            "base_url": "https://image.roil.top",
            "username": "admin",
            "quota_remaining": 62,
            "quota_limit": 1000,
            "quota_used": 938,
            "error": None,
        }
        with patch.object(roil_preflight, "probe_platform", return_value={"reachable": True}), patch.object(
            roil_preflight,
            "detect_nbs_cli",
            return_value={"available": True, "path": "/repo/nbs", "source": "cwd"},
        ), patch.object(
            roil_preflight,
            "inspect_nbs_auth",
            return_value=dict(auth_info),
        ), patch.object(
            roil_preflight,
            "_probe_session_via_cli",
            return_value=cli_probe,
        ):
            status = roil_preflight.build_status(check_platform=True)

        self.assertEqual(status["recommended_next_step"], "generate_via_nbs_cli_backend")
        self.assertEqual(status["nbs_auth"]["session_user"], "admin")
        self.assertEqual(status["nbs_auth"]["quota_remaining"], 62)
        self.assertTrue(status["nbs_auth"]["cli_probe"]["success"])

    def test_build_status_prefers_platform_handoff_when_cli_missing(self) -> None:
        with patch.object(roil_preflight, "probe_platform", return_value={"reachable": True}), patch.object(
            roil_preflight,
            "detect_nbs_cli",
            return_value={"available": False, "path": None, "source": None},
        ), patch.object(
            roil_preflight,
            "inspect_nbs_auth",
            return_value={"session_available": False},
        ):
            status = roil_preflight.build_status(check_platform=True)

        self.assertEqual(status["recommended_next_step"], "open_or_login_platform")
        self.assertEqual(status["decision_summary"]["category"], "platform_login_handoff")

    def test_build_status_falls_back_to_manual_platform_check(self) -> None:
        with patch.object(roil_preflight, "probe_platform", return_value={"reachable": False}), patch.object(
            roil_preflight,
            "detect_nbs_cli",
            return_value={"available": False, "path": None, "source": None},
        ), patch.object(
            roil_preflight,
            "inspect_nbs_auth",
            return_value={"session_available": False},
        ):
            status = roil_preflight.build_status(check_platform=True)

        self.assertEqual(status["recommended_next_step"], "check_network_or_open_platform_manually")
        self.assertEqual(status["decision_summary"]["category"], "manual_platform_check")


class RoilDrawTests(unittest.TestCase):
    def test_default_model_prefers_gpt_image_2_all(self) -> None:
        self.assertEqual(roil_draw.DEFAULT_MODEL, "gpt-image-2-all")

    def test_run_nbs_generate_backend_success_uses_stable_fields(self) -> None:
        status = {"nbs_cli": {"path": "/repo/nbs"}, "nbs_auth": {}}
        completed = SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"status": "generated", "actual_model": "gpt-image-2"}),
            stderr="",
        )
        with patch.object(roil_draw, "_prepare_auth_override", return_value=(None, None)), patch.object(
            roil_draw.subprocess,
            "run",
            return_value=completed,
        ):
            payload = roil_draw._run_nbs_generate(
                "draw a cat",
                Path("/tmp/out.png"),
                status,
                model="gpt-image-2",
                size="1024x1024",
                quality="low",
                force_direct=False,
            )

        self.assertTrue(payload["success"])
        self.assertEqual(payload["via"], "nbs-cli-backend")
        self.assertEqual(payload["runner"], "roil-drawing")
        self.assertEqual(payload["model"], "gpt-image-2")
        self.assertEqual(payload["output_path"], "/tmp/out.png")
        self.assertIn("message", payload)

    def test_main_falls_back_from_backend_to_direct(self) -> None:
        calls = []

        def fake_run(prompt, out, status, *, model, size, quality, force_direct):
            calls.append(force_direct)
            if not force_direct:
                return {
                    "success": False,
                    "status": "nbs_cli_error",
                    "via": "nbs-cli-backend",
                    "runner": "roil-drawing",
                    "model": model,
                    "output_path": None,
                    "message": "backend failed",
                }
            return {
                "success": True,
                "status": "generated",
                "via": "nbs-cli-direct",
                "runner": "roil-drawing",
                "model": model,
                "output_path": str(out),
                "message": "direct succeeded",
            }

        status = {
            "platform_url": "https://image.roil.top/",
            "platform_probe": {"reachable": True},
            "nbs_auth": {"session_available": True},
            "nbs_cli": {"available": True},
        }

        argv = [
            "roil_draw.py",
            "--prompt",
            "draw a cat",
            "--out",
            "/tmp/roil-draw-direct.png",
        ]
        stdout = io.StringIO()
        with patch.object(roil_draw, "build_status", return_value=status), patch.object(
            roil_draw,
            "_run_nbs_generate",
            side_effect=fake_run,
        ), patch.object(roil_draw.os, "environ", {}), patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout):
            code = roil_draw.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 0)
        self.assertEqual(calls, [False, True])
        self.assertEqual(payload["via"], "nbs-cli-direct")
        self.assertEqual(payload["fallback_from"], "nbs-cli-backend")
        self.assertEqual(payload["runner"], "roil-drawing")

    def test_main_uses_platform_handoff_after_direct_failure(self) -> None:
        status = {
            "platform_url": "https://image.roil.top/",
            "platform_probe": {"reachable": True},
            "recommended_next_step": "try_nbs_cli_direct",
            "nbs_auth": {"session_available": False},
            "nbs_cli": {"available": True},
        }
        direct_result = {
            "success": False,
            "status": "nbs_cli_error",
            "via": "nbs-cli-direct",
            "runner": "roil-drawing",
            "model": "gpt-image-2",
            "output_path": None,
            "message": "direct failed",
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "generated.png"
            argv = [
                "roil_draw.py",
                "--prompt",
                "draw a cat",
                "--out",
                str(out_path),
            ]
            stdout = io.StringIO()
            with patch.object(roil_draw, "build_status", return_value=status), patch.object(
                roil_draw,
                "_run_nbs_generate",
                return_value=direct_result,
            ), patch.object(roil_draw.os, "environ", {}), patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout):
                code = roil_draw.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "needs_platform_login")
        self.assertEqual(payload["via"], "roil-web")
        self.assertEqual(payload["runner"], "roil-drawing")
        self.assertTrue(payload["login_required"])
        self.assertEqual(payload["login_url"], "https://image.roil.top/")
        self.assertEqual(payload["previous_attempt"]["via"], "nbs-cli-direct")
        self.assertTrue(payload["prompt_path"].endswith(".prompt.txt"))

    def test_main_does_not_use_openai_when_cli_missing_even_if_key_available(self) -> None:
        status = {
            "platform_url": "https://image.roil.top/",
            "platform_probe": {"reachable": True},
            "recommended_next_step": "open_or_login_platform",
            "nbs_auth": {"session_available": False},
            "nbs_cli": {"available": False},
        }
        argv = [
            "roil_draw.py",
            "--prompt",
            "draw a cat",
            "--out",
            "/tmp/roil-openai.png",
        ]
        stdout = io.StringIO()
        with patch.object(roil_draw, "build_status", return_value=status), patch.object(
            roil_draw,
            "_generate_openai",
            return_value=0,
        ) as generate_openai, patch.object(roil_draw.os, "environ", {"OPENAI_API_KEY": "present"}), patch.object(
            sys, "argv", argv
        ), contextlib.redirect_stdout(stdout):
            code = roil_draw.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "needs_platform_login")
        self.assertEqual(payload["via"], "roil-web")
        self.assertTrue(payload["login_required"])
        self.assertEqual(payload["login_url"], "https://image.roil.top/")
        generate_openai.assert_not_called()

    def test_main_returns_platform_handoff_when_no_execution_path(self) -> None:
        status = {
            "platform_url": "https://image.roil.top/",
            "platform_probe": {"reachable": False},
            "recommended_next_step": "check_network_or_open_platform_manually",
            "nbs_auth": {"session_available": False},
            "nbs_cli": {"available": False},
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "generated.png"
            argv = [
                "roil_draw.py",
                "--prompt",
                "draw a cat",
                "--out",
                str(out_path),
            ]
            stdout = io.StringIO()
            with patch.object(roil_draw, "build_status", return_value=status), patch.object(
                roil_draw.os, "environ", {}
            ), patch.object(sys, "argv", argv), contextlib.redirect_stdout(stdout):
                code = roil_draw.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "needs_platform_login")
        self.assertEqual(payload["runner"], "roil-drawing")
        self.assertEqual(payload["platform_url"], "https://image.roil.top/")
        self.assertTrue(payload["login_required"])
        self.assertEqual(payload["login_url"], "https://image.roil.top/")

    def test_main_prefers_platform_handoff_when_preflight_requests_it(self) -> None:
        status = {
            "platform_url": "https://image.roil.top/",
            "platform_probe": {"reachable": True},
            "recommended_next_step": "open_or_login_platform",
            "nbs_auth": {"session_available": False},
            "nbs_cli": {"available": True},
        }
        argv = [
            "roil_draw.py",
            "--prompt",
            "draw a cat",
            "--out",
            "/tmp/roil-platform-handoff.png",
        ]
        stdout = io.StringIO()
        with patch.object(roil_draw, "build_status", return_value=status), patch.object(
            roil_draw,
            "_run_nbs_generate",
        ) as run_nbs_generate, patch.object(roil_draw.os, "environ", {}), patch.object(
            sys, "argv", argv
        ), contextlib.redirect_stdout(stdout):
            code = roil_draw.main()

        payload = json.loads(stdout.getvalue())
        self.assertEqual(code, 2)
        self.assertEqual(payload["status"], "needs_platform_login")
        self.assertEqual(payload["login_url"], "https://image.roil.top/")
        run_nbs_generate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
