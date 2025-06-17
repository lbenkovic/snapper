from fastapi import APIRouter, HTTPException
from app.models import UserCreate, Token
from app.auth import hash_password, verify_password, create_access_token
from datetime import timedelta

router = APIRouter()

# In-memory fake user store for now
fake_db = {}

@router.post("/register")
def register(user: UserCreate):
    if user.email in fake_db:
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed = hash_password(user.password)
    fake_db[user.email] = {"email": user.email, "hashed_password": hashed}
    return {"msg": "User registered successfully"}

@router.post("/login", response_model=Token)
def login(user: UserCreate):
    db_user = fake_db.get(user.email)
    if not db_user or not verify_password(user.password, db_user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_access_token(data={"sub": user.email}, expires_delta=timedelta(minutes=30))
    return {"access_token": token, "token_type": "bearer"}
