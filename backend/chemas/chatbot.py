import base64
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class ChatImage(BaseModel):
    mime_type: Literal["image/jpeg", "image/png", "image/webp"]
    data: str = Field(max_length=4 * ((5 * 1024 * 1024 + 2) // 3))


class ChatAudio(BaseModel):
    mime_type: Literal["audio/webm", "audio/ogg", "audio/m4a"]
    data: str = Field(max_length=4 * ((2 * 1024 * 1024 + 2) // 3))

class ChatRequest(BaseModel):
    conversation_id: str
    message: str
    image: ChatImage | None = None
    audio: ChatAudio | None = None

    @model_validator(mode="after")
    def require_input(self):
        if not (self.message.strip() or self.image or self.audio):
            raise ValueError("Hãy nhập câu hỏi, chọn ảnh hoặc ghi âm.")
        return self


def decode_chat_media(data: str, max_mib: int) -> bytes:
    try:
        decoded = base64.b64decode(data, validate=True)
    except ValueError as exc:
        raise ValueError("Dữ liệu ảnh hoặc bản ghi không hợp lệ.") from exc
    if not 0 < len(decoded) <= max_mib * 1024 * 1024:
        raise ValueError(f"Tệp phải có dữ liệu và không vượt quá {max_mib} MiB.")
    return decoded


class ConnectCanvasPointsRequest(BaseModel):
    conversation_id: str
    start_point: str
    end_point: str


class ClearCanvasRequest(BaseModel):
    conversation_id: str
