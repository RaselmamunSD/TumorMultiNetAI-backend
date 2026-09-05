from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel
from app.schemas.common import APIResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["AI Chatbot"])


class ChatMessageItem(BaseModel):
    role: str  # "user" or "model" / "bot"
    text: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[List[ChatMessageItem]] = None


class ChatResponseData(BaseModel):
    reply: str


@router.post(
    "",
    response_model=APIResponse[ChatResponseData],
    summary="Chat with TumorMultiNetAI Medical Intelligence Assistant",
    description="Ask questions about brain tumors, MRI modalities, Grad-CAM, and clinical screening predictions.",
)
async def chat_with_ai(payload: ChatRequest):
    history_dicts = (
        [{"role": h.role, "text": h.text} for h in payload.history]
        if payload.history
        else None
    )
    reply_text = await ChatService.generate_response(
        user_message=payload.message,
        history=history_dicts,
    )
    return APIResponse(
        success=True,
        data=ChatResponseData(reply=reply_text),
    )
