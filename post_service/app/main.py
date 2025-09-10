from routes import post
from fastapi import FastAPI

app = FastAPI()
app.include_router(post.router, prefix="/posts", tags=["Posts"])

@app.get("/")
async def root():
    return {"message": "Post Service Running"}
