from fastapi import FastAPI, Request, Response
from app.api.scrapping_service import router as scrapping_router
from app.api.topicModelling_service import router as modelling_router
from prometheus_client import (
    Counter, Summary, generate_latest, CONTENT_TYPE_LATEST
)

app = FastAPI()

# Router
app.include_router(scrapping_router, prefix="/scraping")
app.include_router(modelling_router, prefix="/modelling", tags=["modelling"])

# General API metrics
REQUEST_COUNT = Counter("request_count", "Request total", ["method", "endpoint"])
RESPONSE_TIME = Summary("response_time_seconds", "Respond time per endpoint", ["endpoint"])

@app.middleware("http")
async def prometheus_middleware(request: Request, call_next):
    with RESPONSE_TIME.labels(request.url.path).time():
        response = await call_next(request)
    REQUEST_COUNT.labels(request.method, request.url.path).inc()
    return response

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
