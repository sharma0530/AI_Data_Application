from fastapi import FastAPI
from app.api.datasets import router as datasets_router

app = FastAPI(
    title="AI Data Application",
    version="1.0.0",
)

@app.get("/")
def root():
    return {
        "message" : "AI Data Analyst API"
    }

@app.get("/health")
def health_check():
    return {
        "status": "healthy"
    }

app.include_router(datasets_router)