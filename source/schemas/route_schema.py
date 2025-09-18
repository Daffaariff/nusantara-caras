from pydantic import BaseModel
from uuid import UUID

class StartChat(BaseModel):
    pass

class SendMessage(BaseModel):
    chat_id: UUID
    content: str