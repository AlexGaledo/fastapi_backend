


from urllib import response
from fastapi import APIRouter, HTTPException
from ..services.gemini import generate_response
from pydantic import BaseModel

class ChatbotRequest(BaseModel):
    user_message: str




router = APIRouter()

@router.post("/chatbotInput")
def chatbot_input(request: ChatbotRequest):
    """Process user message through chatbot and return response."""
    try:
        response = generate_response(request.user_message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chatbot error: {str(e)}")
    
    return {"response": response}