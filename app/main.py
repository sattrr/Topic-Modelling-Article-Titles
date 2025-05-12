from fastapi import FastAPI
from app.api.scrapping_service import router as scrapping_router
from app.api.topicModelling_service import router as modelling_router  
app = FastAPI()

app.include_router(scrapping_router, prefix="/scrapping")
app.include_router(modelling_router, prefix="/modelling", tags=["modelling"])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)