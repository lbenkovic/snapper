from fastapi import FastAPI
from routes import messaging

app = FastAPI()
app.include_router(messaging.router, tags=["Messaging"])

@app.get("/")
async def root():
    return {"message": "WS Service Running"}
