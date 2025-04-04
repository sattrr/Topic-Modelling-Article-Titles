from fastapi import FastAPI
import json
from pathlib import Path

app = FastAPI()


@app.get("/")
def read_root():
    try:
        with open('/app/data/raw/scraped_articles.json') as f:
            data = json.load(f)
        return {"message": data}
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)