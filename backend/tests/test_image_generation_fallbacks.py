import argparse
import os
import tempfile
import unittest
from unittest.mock import patch

import backend.cli as cli
import requests
from backend.api.generate import _build_image_model_attempt_chain


class ImageGenerationFallbackTests(unittest.TestCase):
    def test_backend_attempt_chain_tries_all_enabled_image_models(self) -> None:
        catalog = [
            {"service": "image", "model": "model-a", "enabled": True},
            {"service": "image", "model": "model-b", "enabled": True},
            {"service": "image", "model": "model-c", "enabled": True},
            {"service": "image", "model": "model-disabled", "enabled": False},
            {"service": "prompt", "model": "prompt-a", "enabled": True},
        ]

        with patch("backend.api.generate._get_model_catalog", return_value=catalog), patch(
            "backend.api.generate._get_model_route_summary",
            side_effect=lambda service, model: {"executable": model != "model-c"},
        ):
            chain = _build_image_model_attempt_chain("model-b")

        self.assertEqual(chain, ["model-b", "model-a"])

    def test_cli_direct_generate_falls_back_and_keeps_original_prompt_when_optimize_fails(self) -> None:
        output_path = os.path.join(tempfile.gettempdir(), "nbs_fallback_test.png")
        printed = {}
        original_last_error = cli.img_gen.last_error

        def fake_invoke_core(func, *args, **kwargs):
            name = getattr(func, "__name__", "")
            if name == "optimize_prompt":
                cli.img_gen.last_error = {"message": "opt failed"}
                return None
            if name == "generate_image":
                if kwargs.get("model") == "bad-model":
                    cli.img_gen.last_error = {"message": "bad-model failed"}
                    return None
                return "data:image/png;base64,ok"
            if name == "download_image":
                return True
            return func(*args, **kwargs)

        namespace = argparse.Namespace(
            model="bad-model",
            json=True,
            prompt="draw a cat",
            size=None,
            quality=None,
            style=None,
            subject="general",
            output=output_path,
            optimize=True,
            prompt_model="prompt-model",
            api_key=None,
            base_url=None,
            prompt_api_key=None,
            prompt_base_url=None,
        )

        try:
            with patch("backend.cli._get_backend_session", return_value=None), patch(
                "backend.cli._build_image_model_attempt_chain",
                return_value=["bad-model", "good-model"],
            ), patch(
                "backend.cli._resolve_candidates",
                side_effect=lambda service, model, explicit_key, explicit_base_url: [
                    {"key": f"{model}-key", "base_url": "https://example.com"}
                ],
            ), patch("backend.cli._invoke_core", side_effect=fake_invoke_core), patch(
                "backend.cli._write_json_sidecar"
            ), patch("backend.cli._print", side_effect=lambda data, as_json=False: printed.setdefault("payload", data)):
                code = cli.cmd_image_generate(namespace)
        finally:
            cli.img_gen.last_error = original_last_error

        self.assertEqual(code, 0)
        payload = printed["payload"]
        self.assertEqual(payload["model"], "good-model")
        self.assertEqual(payload["requested_model"], "bad-model")
        self.assertEqual(payload["attempted_models"], ["bad-model", "good-model"])
        self.assertTrue(payload["fallback_used"])
        self.assertEqual(payload["attempt_errors"], ["bad-model: bad-model failed"])
        self.assertEqual(payload["optimize_error"], "opt failed")
        self.assertEqual(payload["prompt"], "draw a cat")
        self.assertEqual(payload["direct_reason"], "missing_backend_session")
        self.assertIn("running in direct mode", payload["direct_warning"].lower())

    def test_cli_backend_generate_continues_when_optimize_endpoint_fails(self) -> None:
        output_path = os.path.join(tempfile.gettempdir(), "nbs_backend_fallback_test.png")
        printed = {}
        requests_seen = []

        def fake_backend_json_request(session, method, path, **kwargs):
            requests_seen.append(path)
            if path == "/api/optimize_prompt":
                raise RuntimeError("opt endpoint failed")
            if path == "/api/generate/single":
                return {
                    "url": "/static/generated/fallback.png",
                    "actual_model": "good-model",
                    "attempted_models": ["bad-model", "good-model"],
                    "fallback_used": True,
                }
            raise AssertionError(path)

        namespace = argparse.Namespace(
            model="bad-model",
            json=True,
            prompt="draw a cat",
            size=None,
            quality=None,
            style=None,
            subject="general",
            output=output_path,
            optimize=True,
            prompt_model="prompt-model",
            api_key=None,
            base_url=None,
            prompt_api_key=None,
            prompt_base_url=None,
        )

        with patch("backend.cli._get_backend_session", return_value={"base_url": "http://localhost:8000", "access_token": "token"}), patch(
            "backend.cli._backend_json_request",
            side_effect=fake_backend_json_request,
        ), patch("backend.cli._backend_url", side_effect=lambda session, path: f"http://localhost:8000{path}"), patch(
            "backend.cli._download_remote_file",
            side_effect=lambda url, path: path,
        ), patch("backend.cli._write_json_sidecar"), patch(
            "backend.cli._print", side_effect=lambda data, as_json=False: printed.setdefault("payload", data)
        ):
            code = cli.cmd_image_generate(namespace)

        self.assertEqual(code, 0)
        self.assertEqual(requests_seen, ["/api/optimize_prompt", "/api/generate/single"])
        payload = printed["payload"]
        self.assertEqual(payload["model"], "good-model")
        self.assertEqual(payload["requested_model"], "bad-model")
        self.assertEqual(payload["optimize_error"], "opt endpoint failed")
        self.assertEqual(payload["attempted_models"], ["bad-model", "good-model"])
        self.assertTrue(payload["fallback_used"])

    def test_cli_backend_generate_falls_back_to_direct_when_backend_unreachable(self) -> None:
        output_path = os.path.join(tempfile.gettempdir(), "nbs_backend_unreachable_test.png")
        printed = {}
        original_last_error = cli.img_gen.last_error

        def fake_invoke_core(func, *args, **kwargs):
            name = getattr(func, "__name__", "")
            if name == "optimize_prompt":
                return "draw a cat with clean lighting"
            if name == "generate_image":
                return "data:image/png;base64,ok"
            if name == "download_image":
                return True
            return func(*args, **kwargs)

        namespace = argparse.Namespace(
            model="gpt-image-2-all",
            json=True,
            prompt="draw a cat",
            size="1024x1024",
            quality="high",
            style="vivid",
            subject="general",
            output=output_path,
            optimize=True,
            prompt_model="prompt-model",
            api_key=None,
            base_url=None,
            prompt_api_key=None,
            prompt_base_url=None,
        )

        try:
            with patch(
                "backend.cli._get_backend_session",
                return_value={"base_url": "http://10.0.0.1:8002", "access_token": "token"},
            ), patch(
                "backend.cli._backend_json_request",
                side_effect=requests.ConnectTimeout("backend connect timed out"),
            ), patch(
                "backend.cli._build_image_model_attempt_chain",
                return_value=["gpt-image-2-all"],
            ), patch(
                "backend.cli._resolve_candidates",
                side_effect=lambda service, model, explicit_key, explicit_base_url: [
                    {"key": f"{service}-{model}-key", "base_url": "https://example.com"}
                ],
            ), patch(
                "backend.cli._invoke_core",
                side_effect=fake_invoke_core,
            ), patch(
                "backend.cli._write_json_sidecar"
            ), patch(
                "backend.cli._print",
                side_effect=lambda data, as_json=False: printed.setdefault("payload", data),
            ):
                code = cli.cmd_image_generate(namespace)
        finally:
            cli.img_gen.last_error = original_last_error

        self.assertEqual(code, 0)
        payload = printed["payload"]
        self.assertEqual(payload["via"], "direct")
        self.assertEqual(payload["direct_reason"], "backend_unavailable")
        self.assertIn("timed out", payload["backend_fallback_error"])
        self.assertEqual(payload["model"], "gpt-image-2-all")
        self.assertEqual(payload["optimized_prompt"], "draw a cat with clean lighting")
        self.assertEqual(payload["attempted_models"], ["gpt-image-2-all"])
        self.assertFalse(payload["local_fallback"])

    def test_cli_prompt_optimize_backend_preserves_fallback_metadata_in_json(self) -> None:
        printed = {}
        namespace = argparse.Namespace(
            image_model="image-model",
            model="prompt-model",
            json=True,
            prompt="draw a cat",
            subject="general",
            api_key=None,
            base_url=None,
        )

        with patch("backend.cli._get_backend_session", return_value={"base_url": "http://localhost:8000", "access_token": "token"}), patch(
            "backend.cli._backend_json_request",
            return_value={
                "optimized_prompt": "draw a cat",
                "model": "fallback-model",
                "optimized": False,
                "fallback_to_original": True,
                "errors": ["fallback-model@prompt: Request timed out or failed to reach provider"],
            },
        ), patch("backend.cli._print", side_effect=lambda data, as_json=False: printed.setdefault("payload", data)):
            code = cli.cmd_prompt_optimize(namespace)

        self.assertEqual(code, 0)
        payload = printed["payload"]
        self.assertEqual(payload["optimized_prompt"], "draw a cat")
        self.assertEqual(payload["prompt_model"], "fallback-model")
        self.assertFalse(payload["optimized"])
        self.assertTrue(payload["fallback_to_original"])
        self.assertEqual(
            payload["errors"],
            ["fallback-model@prompt: Request timed out or failed to reach provider"],
        )
        self.assertEqual(payload["via"], "backend")

    def test_cli_prompt_optimize_backend_non_json_prints_original_prompt_on_fallback(self) -> None:
        printed = {}
        namespace = argparse.Namespace(
            image_model="image-model",
            model="prompt-model",
            json=False,
            prompt="draw a cat",
            subject="general",
            api_key=None,
            base_url=None,
        )

        with patch("backend.cli._get_backend_session", return_value={"base_url": "http://localhost:8000", "access_token": "token"}), patch(
            "backend.cli._backend_json_request",
            return_value={
                "optimized_prompt": "draw a cat",
                "model": "fallback-model",
                "optimized": False,
                "fallback_to_original": True,
                "errors": ["fallback-model@prompt: optimization budget exhausted"],
            },
        ), patch("backend.cli._print", side_effect=lambda data, as_json=False: printed.setdefault("payload", data)):
            code = cli.cmd_prompt_optimize(namespace)

        self.assertEqual(code, 0)
        self.assertEqual(printed["payload"], "draw a cat")

    def test_cli_direct_generate_returns_local_fallback_image_when_all_models_fail(self) -> None:
        output_path = os.path.join(tempfile.gettempdir(), "nbs_local_fallback_test.png")
        printed = {}
        original_last_error = cli.img_gen.last_error

        def fake_invoke_core(func, *args, **kwargs):
            name = getattr(func, "__name__", "")
            if name == "generate_image":
                cli.img_gen.last_error = {"message": "provider failed"}
                return None
            if name == "create_local_fallback_image":
                return True
            return func(*args, **kwargs)

        namespace = argparse.Namespace(
            model="bad-model",
            json=True,
            prompt="draw a fallback cat",
            size="512x512",
            quality=None,
            style=None,
            subject="general",
            output=output_path,
            optimize=False,
            prompt_model=None,
            api_key="fake-key",
            base_url="http://127.0.0.1:9",
            prompt_api_key=None,
            prompt_base_url=None,
        )

        try:
            with patch("backend.cli._get_backend_session", return_value=None), patch(
                "backend.cli._build_image_model_attempt_chain",
                return_value=["bad-model", "good-model"],
            ), patch(
                "backend.cli._resolve_candidates",
                side_effect=lambda service, model, explicit_key, explicit_base_url: [
                    {"key": explicit_key, "base_url": explicit_base_url}
                ],
            ), patch("backend.cli._invoke_core", side_effect=fake_invoke_core), patch(
                "backend.cli._write_json_sidecar"
            ), patch("backend.cli._print", side_effect=lambda data, as_json=False: printed.setdefault("payload", data)):
                code = cli.cmd_image_generate(namespace)
        finally:
            cli.img_gen.last_error = original_last_error

        self.assertEqual(code, 0)
        payload = printed["payload"]
        self.assertEqual(payload["model"], "local-fallback-image")
        self.assertEqual(payload["requested_model"], "bad-model")
        self.assertEqual(payload["attempted_models"], ["bad-model", "good-model"])
        self.assertTrue(payload["fallback_used"])
        self.assertTrue(payload["local_fallback"])
        self.assertIsNone(payload["image_url"])
        self.assertEqual(payload["attempt_errors"], ["bad-model: provider failed", "good-model: provider failed"])
        self.assertEqual(payload["direct_reason"], "explicit_override")
        self.assertIn("override", payload["direct_warning"].lower())

    def test_cli_direct_generate_continues_after_download_failure(self) -> None:
        output_path = os.path.join(tempfile.gettempdir(), "nbs_download_retry_test.png")
        printed = {}
        original_last_error = cli.img_gen.last_error
        download_attempts = []

        def fake_invoke_core(func, *args, **kwargs):
            name = getattr(func, "__name__", "")
            if name == "generate_image":
                model_name = kwargs.get("model")
                if model_name == "bad-model":
                    return "https://example.com/not-an-image"
                return "data:image/png;base64,ok"
            if name == "download_image":
                download_attempts.append(args[0])
                if args[0] == "https://example.com/not-an-image":
                    cli.img_gen.last_error = {"message": "Downloaded content is not a valid image"}
                    return False
                return True
            return func(*args, **kwargs)

        namespace = argparse.Namespace(
            model="bad-model",
            json=True,
            prompt="draw a resilient cat",
            size=None,
            quality=None,
            style=None,
            subject="general",
            output=output_path,
            optimize=False,
            prompt_model=None,
            api_key=None,
            base_url=None,
            prompt_api_key=None,
            prompt_base_url=None,
        )

        try:
            with patch("backend.cli._get_backend_session", return_value=None), patch(
                "backend.cli._build_image_model_attempt_chain",
                return_value=["bad-model", "good-model"],
            ), patch(
                "backend.cli._resolve_candidates",
                side_effect=lambda service, model, explicit_key, explicit_base_url: [
                    {"key": f"{model}-key", "base_url": "https://example.com"}
                ],
            ), patch("backend.cli._invoke_core", side_effect=fake_invoke_core), patch(
                "backend.cli._write_json_sidecar"
            ), patch("backend.cli._print", side_effect=lambda data, as_json=False: printed.setdefault("payload", data)):
                code = cli.cmd_image_generate(namespace)
        finally:
            cli.img_gen.last_error = original_last_error

        self.assertEqual(code, 0)
        payload = printed["payload"]
        self.assertEqual(payload["model"], "good-model")
        self.assertEqual(payload["requested_model"], "bad-model")
        self.assertEqual(payload["attempted_models"], ["bad-model", "good-model"])
        self.assertTrue(payload["fallback_used"])
        self.assertEqual(payload["attempt_errors"], ["bad-model: Downloaded content is not a valid image"])
        self.assertEqual(
            download_attempts,
            ["https://example.com/not-an-image", "data:image/png;base64,ok"],
        )

    def test_cli_image_edit_continues_after_download_failure(self) -> None:
        output_path = os.path.join(tempfile.gettempdir(), "nbs_edit_download_retry_test.png")
        printed = {}
        original_last_error = cli.img_gen.last_error
        temp_image = os.path.join(tempfile.gettempdir(), "nbs_edit_input.png")
        with open(temp_image, "wb") as fh:
            fh.write(b"fake")
        download_attempts = []
        candidate_iter = iter(
            [
                {"key": "bad-key", "base_url": "https://bad.example.com"},
                {"key": "good-key", "base_url": "https://good.example.com"},
            ]
        )

        def fake_invoke_core(func, *args, **kwargs):
            name = getattr(func, "__name__", "")
            if name == "generate_modified_image":
                base_url = kwargs.get("base_url")
                if base_url == "https://bad.example.com":
                    return "https://bad.example.com/bad.png"
                return "data:image/png;base64,ok"
            if name == "download_image":
                download_attempts.append(args[0])
                if args[0] == "https://bad.example.com/bad.png":
                    cli.img_gen.last_error = {"message": "Downloaded content is not a valid image"}
                    return False
                return True
            return func(*args, **kwargs)

        namespace = argparse.Namespace(
            model="edit-model",
            json=True,
            prompt="replace dog with cat",
            image=[temp_image],
            output=output_path,
            api_key=None,
            base_url=None,
        )

        try:
            with patch(
                "backend.cli._resolve_candidates",
                return_value=list(candidate_iter),
            ), patch("backend.cli._invoke_core", side_effect=fake_invoke_core), patch(
                "backend.cli._write_json_sidecar"
            ), patch("backend.cli._print", side_effect=lambda data, as_json=False: printed.setdefault("payload", data)):
                code = cli.cmd_image_edit(namespace)
        finally:
            cli.img_gen.last_error = original_last_error
            if os.path.exists(temp_image):
                os.remove(temp_image)

        self.assertEqual(code, 0)
        payload = printed["payload"]
        self.assertEqual(payload["model"], "edit-model")
        self.assertEqual(payload["image_url"], "data:image/png;base64,ok")
        self.assertEqual(payload["attempt_errors"], ["Downloaded content is not a valid image"])
        self.assertEqual(
            download_attempts,
            ["https://bad.example.com/bad.png", "data:image/png;base64,ok"],
        )

    def test_cli_prompt_optimize_direct_reports_missing_session_reason(self) -> None:
        printed = {}
        original_last_error = cli.img_gen.last_error
        namespace = argparse.Namespace(
            image_model="image-model",
            model="prompt-model",
            json=True,
            prompt="draw a cat",
            subject="general",
            api_key=None,
            base_url=None,
        )

        def fake_invoke_core(func, *args, **kwargs):
            if getattr(func, "__name__", "") == "optimize_prompt":
                return "optimized cat prompt"
            return func(*args, **kwargs)

        try:
            with patch("backend.cli._get_backend_session", return_value=None), patch(
                "backend.cli._resolve_candidates",
                return_value=[{"key": "k", "base_url": "https://example.com"}],
            ), patch("backend.cli._invoke_core", side_effect=fake_invoke_core), patch(
                "backend.cli._print", side_effect=lambda data, as_json=False: printed.setdefault("payload", data)
            ):
                code = cli.cmd_prompt_optimize(namespace)
        finally:
            cli.img_gen.last_error = original_last_error

        self.assertEqual(code, 0)
        payload = printed["payload"]
        self.assertEqual(payload["via"], "direct")
        self.assertEqual(payload["direct_reason"], "missing_backend_session")
        self.assertIn("direct mode", payload["direct_warning"].lower())

    def test_cli_prompt_optimize_direct_reports_explicit_override_reason(self) -> None:
        printed = {}
        original_last_error = cli.img_gen.last_error
        namespace = argparse.Namespace(
            image_model="image-model",
            model="prompt-model",
            json=True,
            prompt="draw a cat",
            subject="general",
            api_key="sk-direct",
            base_url="https://override.example.com",
        )

        def fake_invoke_core(func, *args, **kwargs):
            if getattr(func, "__name__", "") == "optimize_prompt":
                return "optimized cat prompt"
            return func(*args, **kwargs)

        try:
            with patch("backend.cli._get_backend_session", return_value=None), patch(
                "backend.cli._resolve_candidates",
                return_value=[{"key": "k", "base_url": "https://example.com"}],
            ), patch("backend.cli._invoke_core", side_effect=fake_invoke_core), patch(
                "backend.cli._print", side_effect=lambda data, as_json=False: printed.setdefault("payload", data)
            ):
                code = cli.cmd_prompt_optimize(namespace)
        finally:
            cli.img_gen.last_error = original_last_error

        self.assertEqual(code, 0)
        payload = printed["payload"]
        self.assertEqual(payload["via"], "direct")
        self.assertEqual(payload["direct_reason"], "explicit_override")
        self.assertIn("override", payload["direct_warning"].lower())


if __name__ == "__main__":
    unittest.main()
