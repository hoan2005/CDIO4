"""Provider adapters and retry policy for all chat LLM calls."""

import base64
import json
import os
import time
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx
from dotenv import load_dotenv

PRIMARY_ATTEMPTS = 3
FALLBACK_ATTEMPTS = 2


@dataclass(frozen=True)
class Model:
    provider: str
    model: str


class LLMClientError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code

    @property
    def rate_limited(self) -> bool:
        return self.status_code == 429 or getattr(self.__cause__, "code", None) == 429


@dataclass
class LLMTrace:
    on_progress: Callable | None
    models: list[dict]


_trace = ContextVar("llm_trace", default=None)
_repair_attempts = ContextVar("repair_attempts", default=None)


@contextmanager
def repair_attempt_budget():
    """Share the retry limits across coordinate proposals for one geometry solve."""
    token = _repair_attempts.set([0, 0])
    try:
        yield
    finally:
        _repair_attempts.reset(token)


@contextmanager
def trace_llm(on_progress=None):
    trace = LLMTrace(on_progress, [])
    token = _trace.set(trace)
    try:
        yield trace
    finally:
        _trace.reset(token)


def _report(model: Model, stage: str, **progress):
    trace = _trace.get()
    if trace is None:
        return
    info = {"stage": stage, **asdict(model)}
    if progress:
        if trace.on_progress:
            trace.on_progress({**info, **progress})
    elif info not in trace.models:
        trace.models.append(info)


def _parse_object(text: str) -> dict:
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("JSON trả về phải là một object.")
    return data


class LLMClient:
    def __init__(self, api_key=None, model=None, client=None):
        load_dotenv(Path(__file__).resolve().parents[2] / ".env")
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.groq_key = os.getenv("GROQ_API_KEY")
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
        self.groq_base = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1").rstrip("/")
        self._client = client
        self.gemini = Model("Gemini", self.model)
        self.gemini_answer = Model("Gemini", os.getenv("GEMINI_ANSWER_MODEL") or self.model)
        self.gpt = Model("Groq", os.getenv("GROQ_MODEL_GPT", "openai/gpt-oss-120b"))
        self.qwen = Model("Groq", os.getenv("GROQ_MODEL_QWEN", "qwen/qwen3.8-27b"))
        self.whisper = Model("Groq", "whisper-large-v3")
        self.routes = {
            "plan": (self.gemini, self.gpt),
            "math": (self.gpt, self.gemini_answer),
            "explain": (self.gpt, self.gemini_answer),
            "check": (self.gpt, self.gemini),
            "repair": (self.gpt, self.gemini),
            "image": (self.qwen, self.gemini),
            "audio": (self.gemini, self.whisper),
        }

    def _gemini_request(self, model, system_prompt, user_prompt, temperature, json_mode):
        if self._client is None:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                api_key=self.api_key,
                http_options=types.HttpOptions(
                    timeout=30_000, retry_options=types.HttpRetryOptions(attempts=1),
                ),
            )
        config = {"system_instruction": system_prompt, "temperature": temperature}
        if json_mode:
            config["response_mime_type"] = "application/json"
        return self._client.models.generate_content(
            model=model.model, contents=user_prompt, config=config,
        ).text

    def _groq_post(self, path, **payload):
        response = httpx.post(
            f"{self.groq_base}/{path}",
            headers={"Authorization": f"Bearer {self.groq_key}"},
            timeout=30.0,
            **payload,
        )
        response.raise_for_status()
        return response.json()

    def _groq_request(self, model, system_prompt, user_prompt, temperature, json_mode):
        if model == self.whisper:
            audio = next(part.inline_data for part in user_prompt if part.inline_data)
            extension = audio.mime_type.split("/")[-1]
            return self._groq_post(
                "audio/transcriptions",
                data={"model": model.model, "language": "vi", "temperature": "0"},
                files={"file": (f"recording.{extension}", audio.data, audio.mime_type)},
            ).get("text")

        content = user_prompt
        if isinstance(user_prompt, list):
            content = []
            for part in user_prompt:
                if part.inline_data:
                    blob = part.inline_data
                    encoded = base64.b64encode(blob.data).decode("ascii")
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:{blob.mime_type};base64,{encoded}"},
                    })
                elif part.text:
                    content.append({"type": "text", "text": part.text})
        payload = {
            "model": model.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content},
            ],
            "temperature": temperature,
            "reasoning_format": "hidden",
            "max_completion_tokens": 4096,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if model == self.qwen:
            payload["reasoning_effort"] = "none" if isinstance(user_prompt, list) else "low"
            if isinstance(user_prompt, list):
                payload["max_completion_tokens"] = 900
        elif json_mode:
            payload["reasoning_effort"] = "low"
        result = self._groq_post("chat/completions", json=payload)
        choice = result["choices"][0]
        if choice["finish_reason"] == "length":
            raise ValueError("Đã đạt giới hạn token đầu ra.")
        return choice["message"]["content"]

    def request_once(self, model, system_prompt, user_prompt, temperature, *, json_mode=False):
        """Run exactly one call, shared by production routing and the live evaluation."""
        try:
            if model.provider == "Groq":
                text = self._groq_request(model, system_prompt, user_prompt, temperature, json_mode)
            else:
                text = self._gemini_request(model, system_prompt, user_prompt, temperature, json_mode)
            if not text or not text.strip():
                raise ValueError("LLM trả về nội dung rỗng.")
            if not json_mode:
                return text.strip()
            if model == self.whisper:
                return {"content": text.strip(), "clarification": ""}
            return _parse_object(text)
        except Exception as exc:
            status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else getattr(exc, "code", None)
            reason = f"HTTP {status}" if status else type(exc).__name__
            raise LLMClientError(f"{model.model} chưa trả kết quả hợp lệ ({reason}).", status_code=status) from exc

    def _generate(self, stage, system_prompt, user_prompt, temperature, *,
                  json_mode, validate=None, groq_system_prompt=None):
        errors = []
        budget = _repair_attempts.get() if stage == "repair" else None
        if budget is None:
            budget = [0, 0]
        for index, (model, limit) in enumerate(
            zip(self.routes[stage], (PRIMARY_ATTEMPTS, FALLBACK_ATTEMPTS))
        ):
            key = self.groq_key if model.provider == "Groq" else self.api_key
            if not key and (model.provider == "Groq" or self._client is None):
                continue
            prompt = (groq_system_prompt or system_prompt) if model.provider == "Groq" else system_prompt
            while budget[index] < limit:
                budget[index] += 1
                attempt = budget[index]
                _report(model, stage, attempt=attempt, limit=limit)
                try:
                    result = self.request_once(model, prompt, user_prompt, temperature, json_mode=json_mode)
                except LLMClientError as exc:
                    errors.append(exc)
                    if exc.status_code in {400, 401, 403, 404, 413, 422}:
                        budget[index] = limit
                        break
                    if attempt < limit:
                        time.sleep(0.4 * attempt)
                    continue
                if validate:
                    try:
                        result = validate(result)
                    except ValueError as exc:
                        errors.append(exc)
                        continue
                _report(model, stage)
                return result

        invalid = [error for error in errors if isinstance(error, ValueError)]
        if invalid:
            raise invalid[-1]
        if errors:
            retryable = [error for error in errors if error.status_code not in {400, 401, 403, 404, 413, 422}]
            if retryable and all(error.rate_limited for error in retryable):
                raise LLMClientError("Các model đang chạm hạn mức.", status_code=429) from errors[-1]
            raise LLMClientError("Các model chưa xử lý được yêu cầu.") from errors[-1]
        raise LLMClientError("Không có model được cấu hình hoặc đã hết số lần thử.")

    def generate_json(self, system_prompt, user_prompt, temperature=0.2, *, stage="plan",
                      validate=None, groq_system_prompt=None):
        return self._generate(
            stage, system_prompt, user_prompt, temperature, json_mode=True,
            validate=validate, groq_system_prompt=groq_system_prompt,
        )

    def generate_text(self, system_prompt, user_prompt, temperature=0.3, *, stage="math", groq_system_prompt=None):
        return self._generate(
            stage, system_prompt, user_prompt, temperature, json_mode=False,
            groq_system_prompt=groq_system_prompt,
        )
