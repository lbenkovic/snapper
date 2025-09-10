from routes import auth
from fastapi import FastAPI

app = FastAPI()
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])

@app.get("/")
def root():
    return {"message": "Auth Service Running"}