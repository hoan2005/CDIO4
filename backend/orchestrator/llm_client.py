"""Small Gemini client wrapper used by the Orchestrator."""

import json
import os
from typing import Any, Dict, Optional


class LLMClientError(RuntimeError):
    """Raised when the LLM call fails or returns invalid JSON."""


class LLMClient:
    """
    Thin wrapper around Google's google-genai SDK.

    Install:
        pip install google-genai

    Configure:
        GEMINI_API_KEY=your_api_key
        GEMINI_MODEL=gemini-2.5-flash   # optional
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        client=None,
    ):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self._client = client

        if self._client is None:
            if not self.api_key:
                raise LLMClientError(
                    "Thiếu GEMINI_API_KEY. Hãy đặt biến môi trường trước khi gọi LLM."
                )
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except ImportError as exc:
                raise LLMClientError(
                    "Chưa cài google-genai. Cài bằng: pip install google-genai"
                ) from exc

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.2,
    ) -> Dict[str, Any]:
        """Call Gemini and parse a JSON object from the response."""
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=user_prompt,
                config={
                    "system_instruction": system_prompt,
                    "temperature": temperature,
                    "response_mime_type": "application/json",
                },
            )
        except Exception as exc:
            raise LLMClientError(f"Gọi LLM thất bại: {exc}") from exc

        text = getattr(response, "text", None)
        if not text or not text.strip():
            raise LLMClientError("LLM trả về nội dung rỗng.")

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMClientError(
                f"LLM không trả về JSON hợp lệ: {text[:300]}"
            ) from exc

        if not isinstance(data, dict):
            raise LLMClientError("JSON trả về phải là một object.")

        return data
