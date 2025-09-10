from routes import message
from fastapi import FastAPI

app = FastAPI()
app.include_router(message.router, prefix="/messages", tags=["Messages"])

@app.get("/")
def root():
    return {"message": "Message Service Running"}