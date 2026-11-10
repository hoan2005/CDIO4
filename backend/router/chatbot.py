from fastapi import APIRouter, Depends, HTTPException, Request, status

from chemas.chatbot import ChatRequest, ClearCanvasRequest, ConnectCanvasPointsRequest
from controller import xuly_chatbot
router_chat = APIRouter(tags=["chatbot"])

@router_chat.get("/" )
def giaodien():
    return {"message":"tôi là gia sư toán học , tôi có thể giúp gì cho bạn"}
@router_chat.post("/chat" )
def gui_chatbot(data: ChatRequest):
    return  xuly_chatbot.xuly_thongtin(data.message,data.conversation_id)


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