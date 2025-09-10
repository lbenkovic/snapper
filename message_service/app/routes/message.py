import uuid
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request
from database import messages_table
from models import MessageCreate, MessageOut
import aiohttp

load_dotenv()

# .env variables
AUTH_PATH = os.getenv("AUTH_PATH")

router = APIRouter()

# Call auth service to verify user token 
async def get_current_user(request: Request):
    async with aiohttp.ClientSession() as session:
        async with session.get(AUTH_PATH, headers=request.headers) as resp: # type: ignore
            if resp.status != 200:
                raise HTTPException(status_code=401, detail="Invalid token")
            return await resp.json()

# Save the message to db
@router.post("/", response_model=MessageOut)
async def create_message(data: MessageCreate, user: dict = Depends(get_current_user)):
    sender = user["username"]
    recipient = data.to
    if sender == recipient:
        raise HTTPException(status_code=400, detail="Cannot send a message to yourself")
    
    conversation_id = "#".join(sorted([sender, recipient]))
    created_at=datetime.utcnow().isoformat()
    message_id = str(uuid.uuid4())
    expires_at = int((datetime.utcnow() + timedelta(seconds=86400)).timestamp())
    item = {
        "conversation_id": conversation_id,
        "created_at": created_at,
        "message_id": message_id,
        "sender": sender,
        "recipient": recipient,
        "content": data.content,
        "expires_at": expires_at
    }
    messages_table.put_item(Item=item)
    
    return item

# Get the conversation with the other user
@router.get("/conversations/{other_user}")
async def get_conversation(other_user: str, user: dict = Depends(get_current_user)):
    conversation_id = "#".join(sorted([user["username"], other_user]))
    resp = messages_table.query(
        KeyConditionExpression="conversation_id = :cid",
        ExpressionAttributeValues={":cid": conversation_id},
        ScanIndexForward=True  # oldest → newest
    )
    
    return resp.get("Items", [])
