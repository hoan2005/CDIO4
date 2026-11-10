from pydantic import BaseModel
from typing import List, Dict, Any, Optional




class ChatRequest(BaseModel):
         
    conversation_id: str
    message: str


class ConnectCanvasPointsRequest(BaseModel):
    conversation_id: str
    start_point: str
    end_point: str


class ClearCanvasRequest(BaseModel):
    conversation_id: str