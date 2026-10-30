from fastapi import APIRouter, Depends, Request,status

from chemas.chatbot import ChatRequest
from controller import xuly_chatbot
router_chat = APIRouter(tags=["chatbot"])

@router_chat.get("/" )
def giaodien():
    return {"message":"tôi là gia sư toán học , tôi có thể giúp gì cho bạn"}
@router_chat.post("/chat" )
def gui_chatbot(data: ChatRequest):
    return  xuly_chatbot.xuly_thongtin(data.message,data.conversation_id)