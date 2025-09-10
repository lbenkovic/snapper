from pydantic import BaseModel
from typing import Optional

class MessageCreate(BaseModel):
    to: str
    content: str

class MessageOut(BaseModel):
    message_id: str
    conversation_id: str
    sender: str
    recipient: str
    content: str
    created_at: str
    expires_at: Optional[int] = None
