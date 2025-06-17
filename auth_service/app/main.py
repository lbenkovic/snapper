from fastapi import FastAPI
from app import users

app = FastAPI()
app.include_router(users.router)
