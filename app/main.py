from fastapi import FastAPI
from fastapi.responses import Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
from app.api.scrapping_service import router as scrapping_router
from app.api.topicModelling_service import router as modelling_router  

app = FastAPI()

app.include_router(scrapping_router, prefix="/scrapping")
app.include_router(modelling_router, prefix="/modelling", tags=["modelling"])

@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)