import uuid
import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

class Post(BaseModel):
    post_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    post_text: str
    post_img_src: List[str] = []
    likes: Optional[List[str]] = None
    comments: List[dict] = []
    created_at:str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    pinned: bool = False
    expires_at: int = Field(
        default_factory=lambda: int(
            (datetime.datetime.utcnow() + datetime.timedelta(seconds=86400)).timestamp()
        )
)
class PostUpdate(BaseModel):
    post_text: Optional[str]
    
class Comment(BaseModel):
    username: Optional[str] = None 
    comment: str
    created_at:str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
