from fastapi import FastAPI
from routes import user

app = FastAPI()
app.include_router(user.router, tags=["User"], prefix="/users")

@app.get("/")
async def root():
    return {"message": "User Service Running"}
