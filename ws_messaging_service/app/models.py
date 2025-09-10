from pydantic import BaseModel

class DMMessage(BaseModel):
    type: str
    to: str
    content: str
