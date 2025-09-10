import os
import uuid
import aiohttp
from typing import List
from dotenv import load_dotenv
from boto3.dynamodb.conditions import Key
from datetime import datetime, timedelta
from database import posts_table, s3_client
from models import Post, Comment, PostUpdate
from fastapi import APIRouter, HTTPException, Request, Depends, UploadFile, File, Form

load_dotenv()

# JWT, AWS credentials and allow extenstions for files
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")
AWS_REGION = os.getenv("AWS_REGION")
S3_BUCKET = os.getenv("S3_BUCKET")
AUTH_PATH = os.getenv("AUTH_PATH")
USER_PATH = os.getenv("USER_PATH")
ALLOWED_EXT = {"jpg", "jpeg", "png"}
ALLOWED_CT = {"image/jpeg", "image/png"}

router = APIRouter()

# Call auth service to verify user token
async def get_current_user(request: Request):
    async with aiohttp.ClientSession() as session:
        async with session.get(AUTH_PATH, headers=request.headers) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=401, detail="Invalid token")
            return await resp.json()

# Get full user data (returns only safe fields)
async def get_full_user(request: Request):
    async with aiohttp.ClientSession() as session:
        async with session.get(USER_PATH, headers=request.headers) as resp:
            if resp.status != 200:
                raise HTTPException(status_code=resp.status, detail="Failed to fetch user data")
            return await resp.json()

# Get your posts, and the people you follow
@router.get("/")
async def get_feed(user_response: dict = Depends(get_full_user), limit: int = 50):
    user = user_response.get("user", {})
    if not user:
        raise HTTPException(status_code=404, detail="Failed to fetch user data")
    
    usernames_to_fetch = set(user.get("following", []))
    usernames_to_fetch.add(user["username"]) 
    posts = []
    for username in usernames_to_fetch:
        response = posts_table.query(
            IndexName="username-created_at-index",
            KeyConditionExpression=Key("username").eq(username),
            ScanIndexForward=False,  # newest -> oldest
            Limit=limit
        )
        items = response.get("Items", [])
        posts.extend(items)
        
    posts = sorted(
        posts,
        key=lambda p: (not p.get("pinned", False), p.get("created_at", "")),
        reverse=False
    )
    
    return {"posts": posts[:limit]}

# Create a new post
@router.post("/")
async def create_post(
    post_text: str = Form(...),
    pinned: bool = Form(False),
    files: List[UploadFile] = File(None),
    user_data: dict = Depends(get_current_user)
):
    username = user_data["username"]
    file_urls = []
    if files:
        for file in files:
            filename = file.filename or ""
            ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
            ctype = (file.content_type or "").lower()
            if ext not in ALLOWED_EXT or ctype not in ALLOWED_CT:
                raise HTTPException(status_code=400, detail="Only JPG/PNG images are allowed.")
            
            if ext == "jpeg":
                ext = "jpg"
                
            s3_key = f"posts/{username}/{uuid.uuid4()}.{ext}"
            s3_client.upload_fileobj(
                file.file,
                S3_BUCKET,
                s3_key,
                ExtraArgs={"ContentType": ctype}
            )
            file_url = f"https://{S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com/{s3_key}"
            file_urls.append(file_url)
            
    if pinned:
        expires_at = int(datetime(2100, 1, 1).timestamp())
    else:
        expires_at = int((datetime.utcnow() + timedelta(seconds=86400)).timestamp())
        
    post = Post(
        username=username,
        post_text=post_text,
        post_img_src=file_urls,
        comments=[],
        created_at=datetime.utcnow().isoformat(),
        pinned=pinned,
        expires_at=expires_at
    )
    
    posts_table.put_item(Item=post.dict(exclude={"likes"}))
    
    return {"message": "Post created", "post": post}

# Edit a post (only edit text and not the image for continuity/safety reasons)
@router.put("/{post_id}")
async def edit_post(
    post_id: str,
    updated_post: PostUpdate,
    user_data: dict = Depends(get_current_user)
):
    username = user_data['username']
    response = posts_table.get_item(Key={"post_id": post_id})
    post = response.get("Item")
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if post['username'] != username:
        raise HTTPException(status_code=403, detail="Not authorized to edit this post")
    
    if updated_post.post_text is None:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    result = posts_table.update_item(
        Key={"post_id": post_id},
        UpdateExpression="SET post_text = :text",
        ExpressionAttributeValues={":text": updated_post.post_text},
        ReturnValues="ALL_NEW"
    )
    
    return {"message": "Post updated", "post": result["Attributes"]}

# Delete a post
@router.delete("/{post_id}")
async def delete_post(post_id: str, user_data: dict = Depends(get_current_user)):
    username = user_data["username"]
    response = posts_table.get_item(Key={"post_id": post_id})
    post = response.get("Item")
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if post["username"] != username:
        raise HTTPException(status_code=403, detail="Not authorized to delete this post")
    
    img_urls = post.get("post_img_src", [])
    for url in img_urls:
        try:
            key = url.split(f".amazonaws.com/")[-1]
            s3_client.delete_object(Bucket=S3_BUCKET, Key=key)
        except Exception as e:
            print(f"Failed to delete {url} from S3: {e}")
            
    posts_table.delete_item(Key={"post_id": post_id})
    
    return {"message": "Post deleted", "deleted_images": img_urls}

# Like a post
@router.post("/{post_id}/like")
async def like_post(post_id: str, user_data: dict = Depends(get_current_user)):
    username = user_data['username']
    response = posts_table.get_item(Key={"post_id": post_id})
    post = response.get("Item")
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    currently_liked = username in set(post.get("likes", []))
    if currently_liked:
        update_expr = "DELETE likes :user"
    else:
        update_expr = "ADD likes :user"
        
    result = posts_table.update_item(
        Key={"post_id": post_id},
        UpdateExpression=update_expr,
        ExpressionAttributeValues={":user": {username}},
        ReturnValues="ALL_NEW"
    )
    
    return {
        "message": "Like status updated",
        "post": result["Attributes"]
    }

# Comment on a post
@router.post("/{post_id}/comment")
async def comment_post(
    post_id: str,
    comment: Comment,
    user_data: dict = Depends(get_current_user)
):
    comment.username = user_data['username']
    response = posts_table.get_item(Key={"post_id": post_id})
    post = response.get("Item")
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    result = posts_table.update_item(
        Key={"post_id": post_id},
        UpdateExpression="SET comments = list_append(if_not_exists(comments, :empty_list), :new_comment)",
        ExpressionAttributeValues={
            ":new_comment": [comment.dict()],
            ":empty_list": []
        },
        ReturnValues="ALL_NEW"
    )
    
    return {
        "message": "Comment added",
        "comments": result["Attributes"].get("comments", [])
    }

# Pin/Unpin a post (set very far TTL)
@router.post("/{post_id}/pin")
async def toggle_pin_post(post_id: str, user_data: dict = Depends(get_current_user)):
    username = user_data["username"]
    response = posts_table.get_item(Key={"post_id": post_id})
    post = response.get("Item")
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    if post["username"] != username:
        raise HTTPException(status_code=403, detail="Not authorized to pin/unpin this post")
    
    if post.get("pinned", False):
        new_pinned = False
        new_expires = int((datetime.utcnow() + timedelta(seconds=86400)).timestamp())
    else:
        new_pinned = True
        new_expires = int(datetime(2100, 1, 1).timestamp())
        
    result = posts_table.update_item(
        Key={"post_id": post_id},
        UpdateExpression="SET pinned = :pinned, expires_at = :expires",
        ExpressionAttributeValues={
            ":pinned": new_pinned,
            ":expires": new_expires
        },
        ReturnValues="ALL_NEW"
    )
    
    return {
        "message": "Post pinned" if new_pinned else "Post unpinned",
        "post": result["Attributes"]
    }
