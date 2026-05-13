import os
import tempfile
import unittest
from base64 import b64encode
from io import BytesIO
from unittest.mock import Mock, patch

from PIL import Image

from backend.core.image_generator import ImageGenerator


def _png_data_uri() -> str:
    buffer = BytesIO()
    Image.new("RGBA", (1, 1), (255, 255, 255, 255)).save(buffer, format="PNG")
    encoded = b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


class ImageGeneratorSafeLoggingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.generator = ImageGenerator()
        self.png_data_uri = _png_data_uri()

    def test_request_timeout_value_splits_connect_and_read_timeouts(self) -> None:
        timeout_value = self.generator._request_timeout_value(120)
        self.assertEqual(timeout_value, (8.0, 120.0))

        short_timeout_value = self.generator._request_timeout_value(3)
        self.assertEqual(short_timeout_value, (3.0, 3.0))

    def test_optimize_prompt_ignores_stdout_io_error(self) -> None:
        self.generator._make_request = Mock(
            return_value={
                "choices": [
                    {
                        "message": {
                            "content": "draw a cat on a clean white background"
                        }
                    }
                ]
            }
        )
        failing_print = Mock(side_effect=OSError(5, "Input/output error"))

        with patch("builtins.print", failing_print):
            optimized = self.generator.optimize_prompt(
                "draw a cat",
                subject="general",
                model="test-model",
                request_timeout=1,
            )

        self.assertEqual(optimized, "draw a cat on a clean white background")

    def test_generate_image_ignores_stdout_io_error(self) -> None:
        self.generator._generate_image_via_chat = Mock(return_value=self.png_data_uri)
        failing_print = Mock(side_effect=OSError(5, "Input/output error"))

        with patch("builtins.print", failing_print):
            image_url = self.generator.generate_image(
                "draw a cat",
                model="gemini-3.1-flash-image-preview",
                request_timeout=1,
            )

        self.assertEqual(image_url, self.png_data_uri)

    def test_generate_image_handles_gpt_image_2_b64_payload_without_response_format(self) -> None:
        self.generator._make_request = Mock(return_value={"data": [{"b64_json": "YWJj"}]})

        image_url = self.generator.generate_image(
            "draw a cat",
            model="gpt-image-2",
            request_timeout=1,
        )

        self.assertEqual(image_url, "data:image/png;base64,YWJj")
        request_payload = self.generator._make_request.call_args.args[1]
        self.assertNotIn("response_format", request_payload)

    def test_gemini_image_preview_prefers_generate_content_before_chat(self) -> None:
        def fake_request(endpoint, payload, **kwargs):
            if endpoint.endswith(":generateContent"):
                return None
            if endpoint == "/v1/chat/completions":
                return {"choices": [{"message": {"content": self.png_data_uri}}]}
            raise AssertionError(endpoint)

        self.generator._make_request = Mock(side_effect=fake_request)

        image_url = self.generator.generate_image(
            "draw a cat",
            model="gemini-3.1-flash-image-preview",
            size="1024x1024",
            request_timeout=1,
        )

        self.assertEqual(image_url, self.png_data_uri)
        endpoints = [call.args[0] for call in self.generator._make_request.call_args_list]
        self.assertEqual(
            endpoints[:2],
            [
                "/v1beta/models/gemini-3.1-flash-image-preview:generateContent",
                "/v1/chat/completions",
            ],
        )
        gemini_payload = self.generator._make_request.call_args_list[0].args[1]
        self.assertNotIn("model", gemini_payload)

    def test_grok_image_prefers_images_generations_and_maps_display_model(self) -> None:
        self.generator._make_request = Mock(return_value={"data": [{"url": "https://example.com/grok.png"}]})

        image_url = self.generator.generate_image(
            "draw a cat",
            model="grok-imagine-image",
            size="1280x720",
            request_timeout=1,
        )

        self.assertEqual(image_url, "https://example.com/grok.png")
        endpoint, payload = self.generator._make_request.call_args.args[:2]
        self.assertEqual(endpoint, "/v1/images/generations")
        self.assertEqual(payload["model"], "grok-3-image")

    def test_grok_image_falls_back_to_chat_when_images_generations_returns_empty(self) -> None:
        def fake_request(endpoint, payload, **kwargs):
            if endpoint == "/v1/images/generations":
                return None
            if endpoint == "/v1/chat/completions":
                return {"choices": [{"message": {"content": self.png_data_uri}}]}
            raise AssertionError(endpoint)

        self.generator._make_request = Mock(side_effect=fake_request)

        image_url = self.generator.generate_image(
            "draw a cat",
            model="grok-3-image",
            size="1280x720",
            request_timeout=1,
        )

        self.assertEqual(image_url, self.png_data_uri)
        endpoints = [call.args[0] for call in self.generator._make_request.call_args_list]
        self.assertEqual(endpoints[:2], ["/v1/images/generations", "/v1/chat/completions"])

    def test_seedream_5_payload_matches_vectorengine_images_generation_shape(self) -> None:
        self.generator._make_request = Mock(return_value={"data": [{"url": "https://example.com/seedream.png"}]})

        image_urls = self.generator.generate_seedream_images(
            "draw a cat",
            size="1024x1024",
            model="doubao-seedream-5-0-260128",
            request_timeout=1,
        )

        self.assertEqual(image_urls, ["https://example.com/seedream.png"])
        endpoint, payload = self.generator._make_request.call_args.args[:2]
        self.assertEqual(endpoint, "/v1/images/generations")
        self.assertEqual(payload["size"], "2K")
        self.assertEqual(payload["output_format"], "png")
        self.assertFalse(payload["watermark"])
        self.assertNotIn("response_format", payload)

    def test_z_image_payload_includes_required_fields(self) -> None:
        self.generator._make_request = Mock(return_value={"data": [{"url": "https://example.com/z.png"}]})

        image_url = self.generator.generate_image(
            "draw a cat",
            model="z-image-turbo",
            size="1280x720",
            request_timeout=1,
        )

        self.assertEqual(image_url, "https://example.com/z.png")
        endpoint, payload = self.generator._make_request.call_args.args[:2]
        self.assertEqual(endpoint, "/v1/images/generations")
        self.assertEqual(payload["n"], 1)
        self.assertFalse(payload["watermark"])
        self.assertTrue(payload["prompt_extend"])
        self.assertNotIn("response_format", payload)

    def test_gpt_image_2_all_reference_images_use_json_images_generation(self) -> None:
        self.generator._make_request = Mock(return_value={"data": [{"b64_json": "YWJj"}]})

        with tempfile.NamedTemporaryFile(suffix=".png") as image_file:
            image_file.write(b"fake-image")
            image_file.flush()
            image_url = self.generator.generate_modified_image(
                "make it brighter",
                [image_file.name],
                model="gpt-image-2-all",
                size="1024x1024",
                request_timeout=1,
            )

        self.assertEqual(image_url, "data:image/png;base64,YWJj")
        endpoint, payload = self.generator._make_request.call_args.args[:2]
        self.assertEqual(endpoint, "/v1/images/generations")
        self.assertEqual(payload["model"], "gpt-image-2-all")
        self.assertEqual(payload["size"], "1024x1024")
        self.assertEqual(len(payload["image"]), 1)
        self.assertTrue(payload["image"][0].startswith("data:image/png;base64,"))
        self.assertNotIn("response_format", payload)

    def test_download_image_ignores_stdout_io_error(self) -> None:
        failing_print = Mock(side_effect=OSError(5, "Input/output error"))

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "cat.png")
            with patch("builtins.print", failing_print):
                saved = self.generator.download_image(self.png_data_uri, output_path)

            self.assertTrue(saved)
            self.assertTrue(os.path.exists(output_path))
            self.assertGreater(os.path.getsize(output_path), 0)

    def test_create_local_fallback_image_creates_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "fallback.png")
            created = self.generator.create_local_fallback_image(
                "生成一张关于具身智能的教学插图",
                output_path,
                size="512x512",
            )

            self.assertTrue(created)
            self.assertTrue(os.path.exists(output_path))
            self.assertGreater(os.path.getsize(output_path), 0)


if __name__ == "__main__":
    unittest.main()
