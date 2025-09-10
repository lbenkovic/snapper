import os
import jwt
import uuid
import datetime
from dotenv import load_dotenv
from database import users_table
from passlib.context import CryptContext
from boto3.dynamodb.conditions import Key, Attr
from models import User, LoginRequest, TokenResponse
from fastapi import APIRouter, HTTPException, Request

load_dotenv()

# .env variables
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM")

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Hash the password
def hash_password(password: str):
    return pwd_context.hash(password)

# Verify the password
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

# Create JWT token
def create_jwt_token(username: str):
    expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=2)
    token_data = {"sub": username, "exp": expiration}
    return jwt.encode(token_data, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM) # type: ignore

# Decode JWT token
def decode_jwt_token(token: str):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM]) # type: ignore
        return payload.get("sub")
    except jwt.ExpiredSignatureError:
        return None

# Register new user
@router.post("/register")
def register(user: User):
    user_id = str(uuid.uuid4())
    response = users_table.query(
        KeyConditionExpression=Key("username").eq(user.username)
    )
    
    if response.get("Items"):
        raise HTTPException(status_code=400, detail="Username already exists.")
    
    email_response = users_table.scan(
        FilterExpression=Attr("email").eq(user.email),
        ProjectionExpression="email"
    )
    
    if email_response.get("Items"):
        raise HTTPException(status_code=400, detail="Email already in use.")
    
    users_table.put_item(Item={
        "user_id": user_id,
        "username": user.username,
        "email": user.email,
        "password": hash_password(user.password)
    })
    
    return {"message": "User successfully registered!", "user_id": user_id}

# Login and token generation
@router.post("/login", response_model=TokenResponse)
def login(login_data: LoginRequest):
    response = users_table.query(
        KeyConditionExpression=Key("username").eq(login_data.username)
    )
    
    items = response.get("Items", [])
    if not items or not verify_password(login_data.password, items[0]["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_jwt_token(items[0]["username"])
    
    return {"access_token": token, "token_type": "bearer"}

# Token verification
@router.get("/verify")
def verify_token(request: Request):
    token = request.headers.get("Authorization")
    if not token or not token.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token not found")
    
    token = token.split("Bearer ")[1]
    username = decode_jwt_token(token)
    if not username:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    response = users_table.get_item(Key={"username": username})
    user = response.get("Item")
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {"username": username, "email": user["email"]}