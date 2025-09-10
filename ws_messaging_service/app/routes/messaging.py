import aiohttp
import os
from dotenv import load_dotenv
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException
from models import DMMessage

load_dotenv()

AUTH_PATH = os.getenv("AUTH_PATH")
USERS_PATH = os.getenv("USERS_PATH")
MESSAGES_PATH = os.getenv("MESSAGES_PATH")

router = APIRouter()

# In-memory connection manager
connections = {}

# Call auth service to verify user token
async def verify_token(token: str):
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    async with aiohttp.ClientSession() as session:
        async with session.get(AUTH_PATH, headers={"Authorization": f"Bearer {token}"}) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=401, detail="Invalid token")
            return await resp.json()

# WS route that receives the message, checks if the user is sending a message to him/herself
# and checks if the user exists the message is sent to
# Calls the message service to save the message in the db
@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    token = websocket.query_params.get("token")
    if not token:
        await websocket.accept()
        await websocket.send_json({"type": "error", "detail": "Missing token"})
        await websocket.close(code=1008)
        return
    
    try:
        user = await verify_token(token)
    except HTTPException:
        await websocket.accept()
        await websocket.send_json({"type": "error", "detail": "Authentication failed"})
        await websocket.close(code=1008)
        return
    
    await websocket.accept()
    
    username = user["username"]
    connections[username] = websocket
    
    await websocket.send_json({"type": "info", "detail": f"Connected as {username}"})
    
    try:
        while True:
            msg = await websocket.receive_json()
            if msg.get("type") != "dm":
                await websocket.send_json({"type": "error", "detail": "Invalid message type"})
                continue
            
            dm = DMMessage(**msg)
            
            if dm.to == username:
                await websocket.send_json({
                    "type": "error",
                    "detail": "Cannot send a message to yourself"
                })
                continue
            
            async with aiohttp.ClientSession() as session:
                resp = await session.get(
                    f"{USERS_PATH}/{dm.to}",
                    headers={"Authorization": f"Bearer {token}"}
                )
                if resp.status == 404:
                    await websocket.send_json({
                        "type": "error",
                        "detail": f"Recipient '{dm.to}' does not exist"
                    })
                    continue
                elif resp.status != 200:
                    await websocket.send_json({
                        "type": "error",
                        "detail": "Failed to validate recipient"
                    })
                    continue
                
            async with aiohttp.ClientSession() as session:
                resp = await session.post(
                    MESSAGES_PATH,
                    json={"to": dm.to, "content": dm.content},
                    headers={"Authorization": f"Bearer {token}"}
                )
                if resp.status != 200:
                    try:
                        error = await resp.json()
                    except Exception:
                        error = {"detail": await resp.text()}
                    await websocket.send_json({
                        "type": "error",
                        "detail": error.get("detail", "Failed to save message")
                    })
                    continue
                
                saved_message = await resp.json()
                
            if dm.to in connections:
                await connections[dm.to].send_json({
                    "type": "dm",
                    "from": username,
                    "content": dm.content,
                    "message_id": saved_message["message_id"],
                    "created_at": saved_message["created_at"]
                })
                
            await websocket.send_json({"type": "ack", "message_id": saved_message["message_id"]})
    except WebSocketDisconnect:
        pass
    finally:
        connections.pop(username, None)
