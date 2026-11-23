import base64
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from controller import xuly_chatbot
from main import app
from orchestrator.llm_client import LLMClientError


class ChatMediaTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.turn = {"conversation_id": "media-test", "message": ""}
        self.image = {"mime_type": "image/png", "data": base64.b64encode(b"image").decode()}
        self.audio = {"mime_type": "audio/webm", "data": base64.b64encode(b"audio").decode()}

    def test_attachments_feed_the_existing_chat_pipeline(self):
        for attachments, mimes in [
            ({"image": self.image}, ["image/png"]),
            ({"audio": self.audio}, ["audio/webm"]),
            ({"image": self.image, "audio": self.audio, "message": "Giải giúp mình"}, ["image/png", "audio/webm"]),
        ]:
            with self.subTest(mimes=mimes), patch.object(
                xuly_chatbot.llm_client, "generate_json", return_value={"content": "Tính x."}
            ) as extract, patch.object(
                xuly_chatbot, "xuly_thongtin", return_value={"message": "Lời giải", "canvas": {}}
            ) as solve:
                response = self.client.post("/chat", json={**self.turn, **attachments})
                self.assertEqual(response.status_code, 200)
                parts = extract.call_args.kwargs["user_prompt"]
                self.assertEqual([part.inline_data.mime_type for part in parts[1:]], mimes)
                question, conversation = solve.call_args.args
                self.assertIn("Tính x.", question)
                self.assertEqual(conversation, "media-test")
                if "message" in attachments:
                    self.assertTrue(question.startswith("Giải giúp mình"))

    def test_invalid_media_does_not_call_gemini(self):
        with patch.object(xuly_chatbot.llm_client, "generate_json") as extract:
            for body in [self.turn, {**self.turn, "image": {**self.image, "data": "???"}}]:
                self.assertEqual(self.client.post("/chat", json=body).status_code, 422)
            extract.assert_not_called()

    def test_quota_error_stops_the_turn(self):
        error = LLMClientError("quota")
        cause = RuntimeError("quota")
        cause.code = 429
        error.__cause__ = cause
        with patch.object(
            xuly_chatbot.llm_client, "generate_json", side_effect=error
        ), patch.object(xuly_chatbot, "xuly_thongtin") as solve:
            response = self.client.post("/chat", json={**self.turn, "audio": self.audio})
            self.assertEqual(response.status_code, 429)
            solve.assert_not_called()
