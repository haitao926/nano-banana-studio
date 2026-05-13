import argparse
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_DIR.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import backend.cli as cli
from backend.main import app
from backend.core.db_manager import DBManager
from backend.core.auth_utils import get_password_hash
from backend.api import auth as auth_api


class AuthCliSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "app.db")
        self.db = DBManager(db_path=self.db_path)
        self.db.create_user("tester", get_password_hash("secret123"), is_pro=False, quota_limit=20)
        self.client = TestClient(app)

        self.db_patch = patch("backend.api.auth.db", self.db)
        self.db_patch.start()
        self.api_auth_db_patch = patch("api.auth.db", self.db)
        self.api_auth_db_patch.start()
        self.app_state_patch = patch("backend.app_state.db", self.db)
        self.app_state_patch.start()
        self.deps_patch = patch("backend.deps.db", self.db)
        self.deps_patch.start()
        self.raw_deps_patch = patch("deps.db", self.db)
        self.raw_deps_patch.start()

    def tearDown(self) -> None:
        self.raw_deps_patch.stop()
        self.deps_patch.stop()
        self.app_state_patch.stop()
        self.api_auth_db_patch.stop()
        self.db_patch.stop()
        self.tmpdir.cleanup()

    def _login(self):
        response = self.client.post("/api/auth/login", data={"username": "tester", "password": "secret123"})
        self.assertEqual(response.status_code, 200)
        return response.json()

    def test_device_flow_approves_and_returns_cli_session(self) -> None:
        session = self._login()
        start = self.client.post("/api/auth/cli/device/start")
        self.assertEqual(start.status_code, 200)
        payload = start.json()
        self.assertIn("/api/auth/cli/sync-page?user_code=", payload["verification_uri_complete"])
        self.assertIn("device_code=", payload["verification_uri_complete"])

        poll_before = self.client.post("/api/auth/cli/device/poll", json={"device_code": payload["device_code"]})
        self.assertEqual(poll_before.status_code, 428)

        approve = self.client.post(
            "/api/auth/cli/device/approve",
            json={"user_code": payload["user_code"]},
            headers={"Authorization": f"Bearer {session['access_token']}"},
        )
        self.assertEqual(approve.status_code, 200)

        poll_after = self.client.post("/api/auth/cli/device/poll", json={"device_code": payload["device_code"]})
        self.assertEqual(poll_after.status_code, 200)
        poll_payload = poll_after.json()
        self.assertEqual(poll_payload["username"], "tester")
        self.assertTrue(poll_payload["access_token"])
        self.assertTrue(poll_payload["refresh_token"])
        self.assertTrue(poll_payload["base_url"].startswith("http://testserver"))

        poll_again = self.client.post("/api/auth/cli/device/poll", json={"device_code": payload["device_code"]})
        self.assertEqual(poll_again.status_code, 400)

    def test_device_flow_uses_external_base_url_for_links_and_session(self) -> None:
        session = self._login()
        with patch.dict(os.environ, {"EXTERNAL_BASE_URL": "https://image.roil.top/"}):
            start = self.client.post("/api/auth/cli/device/start")
            self.assertEqual(start.status_code, 200)
            payload = start.json()
            self.assertTrue(payload["verification_uri"].startswith("https://image.roil.top/"))

            approve = self.client.post(
                "/api/auth/cli/device/approve",
                json={"device_code": payload["device_code"]},
                headers={"Authorization": f"Bearer {session['access_token']}"},
            )
            self.assertEqual(approve.status_code, 200)

        poll_after = self.client.post("/api/auth/cli/device/poll", json={"device_code": payload["device_code"]})
        self.assertEqual(poll_after.status_code, 200)
        self.assertEqual(poll_after.json()["base_url"], "https://image.roil.top")

    def test_cli_sync_web_writes_auth_session_after_approval(self) -> None:
        auth_file = os.path.join(self.tmpdir.name, "auth.json")
        start_payload = {
            "device_code": "device-123",
            "user_code": "ABCD-EFGH",
            "verification_uri": "https://image.roil.top/api/auth/cli/sync-page",
            "verification_uri_complete": "https://image.roil.top/api/auth/cli/sync-page?user_code=ABCD-EFGH&device_code=device-123",
            "expires_in": 60,
            "interval": 0,
        }
        poll_pending = {"detail": "Authorization pending"}
        poll_ready = {
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "token_type": "bearer",
            "base_url": "https://image.roil.top",
            "username": "tester",
        }
        responses = [
            self._mock_response(200, start_payload),
            self._mock_response(428, poll_pending),
            self._mock_response(200, poll_ready),
        ]

        printed = {}
        args = argparse.Namespace(base_url="https://image.roil.top", timeout=30, json=True)
        with patch("backend.cli._auth_request", side_effect=responses), patch(
            "backend.cli._auth_file_path", return_value=Path(auth_file)
        ), patch("backend.cli._print", side_effect=lambda data, as_json=False: printed.setdefault(len(printed), data)):
            code = cli.cmd_auth_sync_web(args)

        self.assertEqual(code, 0)
        self.assertTrue(os.path.exists(auth_file))
        saved = json.loads(Path(auth_file).read_text(encoding="utf-8"))
        self.assertEqual(saved["base_url"], "https://image.roil.top")
        self.assertEqual(saved["username"], "tester")
        self.assertEqual(saved["refresh_token"], "refresh-token")
        final_payload = printed[max(printed.keys())]
        self.assertEqual(final_payload["synced_via"], "web_device_flow")

    @staticmethod
    def _mock_response(status_code: int, payload):
        class MockResponse:
            def __init__(self, code, data):
                self.status_code = code
                self._payload = data

            def json(self):
                return self._payload

        return MockResponse(status_code, payload)


if __name__ == "__main__":
    unittest.main()
