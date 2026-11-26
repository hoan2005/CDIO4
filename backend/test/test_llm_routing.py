import json
import unittest
from uuid import uuid4
from unittest.mock import patch

from fastapi.testclient import TestClient

from controller import xuly_chatbot
from main import app
from orchestrator.llm_client import LLMClient, LLMClientError, repair_attempt_budget, trace_llm


class LLMRoutingTests(unittest.TestCase):
    def setUp(self):
        self.client = LLMClient(api_key="test-gemini")
        self.client.groq_key = "test-groq"

    def test_primary_three_attempts_then_fallback_two_attempts(self):
        models = self.client.routes["math"]
        errors = [LLMClientError("quota", status_code=429)] * 4
        with patch.object(self.client, "request_once", side_effect=[*errors, "x = 2"]) as call:
            with patch("orchestrator.llm_client.time.sleep"), trace_llm() as trace:
                self.assertEqual(self.client.generate_text("system", "user"), "x = 2")
        self.assertEqual([c.args[0] for c in call.call_args_list], [models[0]] * 3 + [models[1]] * 2)
        self.assertEqual(trace.models, [
            {"stage": "math", "provider": models[1].provider, "model": models[1].model},
        ])

    def test_all_quota_errors_return_429(self):
        with patch.object(self.client, "request_once", side_effect=LLMClientError("quota", status_code=429)) as call:
            with patch("orchestrator.llm_client.time.sleep"), self.assertRaises(LLMClientError) as raised:
                self.client.generate_text("system", "user")
        self.assertEqual(call.call_count, 5)
        self.assertTrue(raised.exception.rate_limited)

    def test_permanent_error_moves_to_other_provider(self):
        with patch.object(
            self.client, "request_once", side_effect=[LLMClientError("unknown model", status_code=404), "ok"],
        ) as call:
            self.assertEqual(self.client.generate_text("system", "user"), "ok")
        self.assertEqual([c.args[0] for c in call.call_args_list], list(self.client.routes["math"]))

    def test_repair_budget_carries_across_coordinate_proposals(self):
        primary, fallback = self.client.routes["repair"]
        with patch.object(self.client, "request_once", return_value={"success": True}) as call:
            with repair_attempt_budget():
                for _ in range(5):
                    self.client.generate_json("system", "proposal", stage="repair")
                with self.assertRaises(LLMClientError):
                    self.client.generate_json("system", "proposal", stage="repair")
            self.client.generate_json("system", "new solve", stage="repair")
        self.assertEqual([c.args[0] for c in call.call_args_list], [primary] * 3 + [fallback] * 2 + [primary])

    def test_stream_reports_retry_and_uses_only_successful_models_in_reply(self):
        conversation_id = str(uuid4())
        self.addCleanup(xuly_chatbot.state_manager.delete_conversation, conversation_id)
        request = {"message": "Giải phương trình x=2", "conversation_id": conversation_id}
        plan = {"tasks": [{"operation": "answer", "input": {"question": request["message"]}}]}
        invalid_plan = {"tasks": [{"operation": "nonsense"}]}
        with patch.object(xuly_chatbot, "llm_client", self.client):
            with patch.object(
                self.client, "request_once", side_effect=[invalid_plan] * 3 + [plan, "Kết quả là $x=2$."],
            ), TestClient(app) as http:
                response = http.post("/chat/stream", json=request)
        self.assertEqual(response.status_code, 200)
        events = [json.loads(line) for line in response.text.splitlines()]
        progress = [event["data"] for event in events if event["type"] == "progress"]
        self.assertEqual([(item["stage"], item["attempt"], item["limit"]) for item in progress], [
            ("plan", 1, 3), ("plan", 2, 3), ("plan", 3, 3), ("plan", 1, 2), ("math", 1, 3),
        ])
        self.assertEqual(events[-1]["type"], "result")
        message = events[-1]["data"]["message"]
        self.assertIn("$x=2$", message["content"])
        self.assertEqual([(item["stage"], item["provider"]) for item in message["llm_models"]], [
            ("plan", "Groq"), ("math", "Groq"),
        ])

    def test_stream_keeps_media_error_as_terminal_event(self):
        with TestClient(app) as http:
            response = http.post("/chat/stream", json={
                "message": "", "conversation_id": "invalid-media",
                "image": {"mime_type": "image/png", "data": "???"},
            })
        self.assertEqual(
            [json.loads(line) for line in response.text.splitlines()],
            [{"type": "error", "data": {
                "status": 422, "detail": "Dữ liệu ảnh hoặc bản ghi không hợp lệ.",
            }}],
        )
