from pydantic import BaseModel
from typing import List, Dict, Any, Optional




class ChatRequest(BaseModel):
         
    conversation_id: str
    message: str