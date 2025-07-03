from fastapi import FastAPI

app = FastAPI(title="API Gateway")

@app.get("/")
async def root():
    """
    Root endpoint for the API Gateway.
    """
    return {"message": "API Gateway is running"}

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "ok"}