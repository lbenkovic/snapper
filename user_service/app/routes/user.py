import os
import uuid
import aiohttp
from dotenv import load_dotenv
from passlib.context import CryptContext
from boto3.dynamodb.conditions import Attr
from database import users_table, s3_client
from fastapi import APIRouter, HTTPException, Request, Depends, UploadFile, File, Query

load_dotenv()

# JWT, AWS credentials and allow extenstions for files
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET = os.getenv("S3_BUCKET")
AUTH_PATH = os.getenv("AUTH_PATH")
ALLOWED_EXT = {"jpg", "jpeg", "png"}
ALLOWED_CT = {"image/jpeg", "image/png"}

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Call auth service to verify user token
async def get_current_user(request: Request):
    async with aiohttp.ClientSession() as session:
        async with session.get(AUTH_PATH, headers=request.headers) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=401, detail="Invalid token")
            return await resp.json()

# Get full user data
async def get_full_user(user: dict):
    response = users_table.get_item(Key={"username": user["username"]})
    full_user = response.get("Item")
    if not full_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return full_user

# Fetch current logged in user
@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    full_user = await get_full_user(user)
    safe_user = {k: v for k, v in full_user.items() if k not in {"password"}} 
    
    return {"user": safe_user}

# Post a profile picture
@router.post("/profile-picture")
async def upload_image(file: UploadFile = File(...), user_data: dict = Depends(get_current_user)):
    username = user_data["username"]
    filename = file.filename or ""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    ctype = (file.content_type or "").lower()
    if ext not in ALLOWED_EXT or ctype not in ALLOWED_CT:
        raise HTTPException(status_code=400, detail="Only JPG/PNG images are allowed.")
    
    if ext == "jpeg":
        ext = "jpg"
        
    s3_key = f"users/{username}/{uuid.uuid4()}.{ext}"
    s3_client.upload_fileobj(
        file.file,
        S3_BUCKET,
        s3_key,
        ExtraArgs={"ContentType": ctype}
    )
    
    file_url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
    
    users_table.update_item(
        Key={"username": username},
        UpdateExpression="SET profile_picture_url = :url",
        ExpressionAttributeValues={":url": file_url}
    )

    return {"message": "Profile picture updated", "url": file_url}

# Get my followers
@router.get("/followers")
async def get_my_followers(user_data: dict = Depends(get_current_user)):
    response = users_table.get_item(Key={"username": user_data["username"]})
    user = response.get("Item")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"followers": user.get("followers", [])}

# Get other users followers
@router.get("/followers/{username}")
async def get_user_followers(username: str, user_data: dict = Depends(get_current_user)):
    response = users_table.get_item(Key={"username": username})
    user = response.get("Item")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"followers": user.get("followers", [])}

# Get my following
@router.get("/following")
async def get_my_following(user_data: dict = Depends(get_current_user)):
    response = users_table.get_item(Key={"username": user_data["username"]})
    user = response.get("Item")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"following": user.get("following", [])}

# Get other users following
@router.get("/following/{username}")
async def get_user_following(username: str, user_data: dict = Depends(get_current_user)):
    response = users_table.get_item(Key={"username": username})
    user = response.get("Item")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"following": user.get("following", [])}

# Search users
@router.get("/search")
async def search_users(q: str = Query(..., min_length=1), user_data: dict = Depends(get_current_user)):
    response = users_table.scan(
        FilterExpression=Attr("username").contains(q),
    )
    items = response.get("Items", [])
    safe_users = [
        {k: v for k, v in user.items() if k not in {"password", "email", "following", "followers"}}
        for user in items
    ]
    
    return {"users": safe_users}

# Get another user profile
@router.get("/{username}")
async def get_user(username: str, user_data: dict = Depends(get_current_user)):
    response = users_table.get_item(Key={"username": username})
    user = response.get("Item")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    safe_user = {k: v for k, v in user.items() if k not in {"password", "email"}}
    
    return {"user": safe_user}

# Follow a user
@router.post("/{username}/follow")
async def follow_user(username: str, user: dict = Depends(get_current_user)):
    if username == user["username"]:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")
    
    response = users_table.get_item(Key={"username": username})
    target_user = response.get("Item")
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    followers = set(target_user.get("followers", []))
    if user["username"] in followers:
        raise HTTPException(status_code=400, detail=f"You are already following {username}")
    
    users_table.update_item(
        Key={"username": username},
        UpdateExpression="ADD followers :follower",
        ExpressionAttributeValues={":follower": {user["username"]}}
    )
    
    users_table.update_item(
        Key={"username": user["username"]},
        UpdateExpression="ADD following :following",
        ExpressionAttributeValues={":following": {username}}
    )
    
    return {"message": f"You are now following {username}"}

# Unfollow a user
@router.post("/{username}/unfollow")
async def unfollow_user(username: str, user: dict = Depends(get_current_user)):
    if username == user["username"]:
        raise HTTPException(status_code=400, detail="Cannot unfollow yourself")
    
    response = users_table.get_item(Key={"username": username})
    target_user = response.get("Item")
    if not target_user:
        raise HTTPException(status_code=404, detail="User not found")
    
    followers = set(target_user.get("followers", []))
    if user["username"] not in followers:
        raise HTTPException(status_code=400, detail=f"You are not following {username}")
    
    users_table.update_item(
        Key={"username": username},
        UpdateExpression="DELETE followers :follower",
        ExpressionAttributeValues={":follower": {user["username"]}}
    )
    
    users_table.update_item(
        Key={"username": user["username"]},
        UpdateExpression="DELETE following :following",
        ExpressionAttributeValues={":following": {username}}
    )
    
    return {"message": f"You unfollowed {username}"}