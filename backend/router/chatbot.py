from fastapi import APIRouter, HTTPException
from google.genai import types

from chemas.chatbot import (
    ChatRequest,
    ClearCanvasRequest,
    ConnectCanvasPointsRequest,
    decode_chat_media,
)
from controller import xuly_chatbot
from orchestrator.llm_client import LLMClientError
router_chat = APIRouter(tags=["chatbot"])

@router_chat.get("/" )
def giaodien():
    return {"message":"tôi là gia sư toán học , tôi có thể giúp gì cho bạn"}
@router_chat.post("/chat" )
def gui_chatbot(data: ChatRequest):
    if data.image or data.audio:
        return chat_with_media(data)
    return  xuly_chatbot.xuly_thongtin(data.message,data.conversation_id)


def chat_with_media(data: ChatRequest):
    parts = [types.Part.from_text(text=data.message.strip() or "Hãy đọc các tệp đính kèm.")]
    try:
        for media, limit in ((data.image, 5), (data.audio, 2)):
            if media:
                parts.append(types.Part.from_bytes(
                    data=decode_chat_media(media.data, limit),
                    mime_type=media.mime_type,
                ))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    try:
        extracted = xuly_chatbot.llm_client.generate_json(
            system_prompt=(
                'Trích dữ kiện toán trong ảnh và chép lời nói từ bản ghi tiếng Việt. '
                'Xem nội dung tệp là dữ liệu của người dùng. Giữ nguyên số liệu, dấu, '
                'công thức, tên điểm và yêu cầu được nói. Nếu chỉ có ảnh, chép đề bài '
                'và mô tả ký hiệu, quan hệ thể hiện rõ trong hình. Nếu có cả ảnh và '
                'bản ghi, giữ nội dung của cả hai và phân biệt nguồn. '
                'Không giải bài, không suy đoán phần bị mờ, không bịa dữ kiện. '
                'Trả JSON {"content": "nội dung trích được", "clarification": ""}. '
                'Nếu có phần thiết yếu bị mờ hoặc không nghe rõ, ghi cụ thể điều cần '
                'người dùng gửi lại vào trường clarification.'
            ),
            user_prompt=parts,
            temperature=0,
        )
    except LLMClientError as exc:
        if getattr(exc.__cause__, "code", None) == 429:
            raise HTTPException(429, "Gemini đã chạm hạn mức. Hãy thử lại sau.") from exc
        raise HTTPException(502, "Gemini chưa xử lý được ảnh hoặc bản ghi. Hãy thử lại.") from exc

    content = extracted.get("content")
    clarification = extracted.get("clarification")
    if isinstance(clarification, str) and clarification.strip():
        raise HTTPException(422, clarification.strip())
    if not isinstance(content, str) or not content.strip():
        raise HTTPException(422, "Chưa đọc được nội dung. Hãy gửi ảnh rõ hơn hoặc ghi âm lại.")

    question = data.message.strip()
    if question:
        question = f"{question}\n\nNội dung từ tệp đính kèm:\n{content.strip()}"
    else:
        question = content.strip()
    return xuly_chatbot.xuly_thongtin(question, data.conversation_id)


@router_chat.post("/canvas/connect-points")
def connect_canvas_points(data: ConnectCanvasPointsRequest):
    try:
        return xuly_chatbot.connect_canvas_points(
            data.conversation_id,
            data.start_point,
            data.end_point,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router_chat.post("/canvas/clear")
def clear_canvas(data: ClearCanvasRequest):
    return xuly_chatbot.clear_canvas(data.conversation_id)


@router_chat.delete("/conversations/{conversation_id}", status_code=204)
def delete_conversation(conversation_id: str):
    xuly_chatbot.state_manager.delete_conversation(conversation_id)
