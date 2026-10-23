import logging
import asyncio
from pathlib import Path
from fastapi import APIRouter, BackgroundTasks, HTTPException
from starlette.responses import StreamingResponse
from pydantic import BaseModel, HttpUrl
from prometheus_client import Counter, Summary
from src.scrapping.getLink import scrape_links, save_links
from src.scrapping.getTitle import scrape_titles

router = APIRouter()

BASE_DIR = Path(__file__).resolve().parents[2]
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

SCRAPING_DURATION = Summary("scraping_duration_seconds", "Scraping Duration")
SCRAPED_LINKS_COUNT = Counter("scraped_links_total", "Number of links successfully scraped")

log_file_path = LOGS_DIR / "scraping.log"
logger = logging.getLogger(__name__)

class ScrapeLinksRequest(BaseModel):
    url: HttpUrl

class ScrapeLinksResponse(BaseModel):
    url: str
    total: int
    links: list[str]

@router.post("/scrape-links", response_model=ScrapeLinksResponse)
async def scrape_links_endpoint(body: ScrapeLinksRequest):
    logger.info(f"Received request to scrape links from: {body.url}")
    
    try:
        links = await asyncio.to_thread(scrape_links, str(body.url))
        SCRAPED_LINKS_COUNT.inc(len(links))
        logger.info(f"Successfully scraped {len(links)} links from {body.url}")

        save_links(links)

        return ScrapeLinksResponse(
            url=str(body.url),
            total=len(links),
            links=links
        )
    except Exception as e:
        logger.error(f"Error scraping links from {body.url}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
# @router.post("/scrape-titles")
# async def scrape_titles_endpoint():
#     async def generate():
#         queue = asyncio.Queue()

#         class QueueHandler(logging.Handler):
#             def emit(self, record):
#                 asyncio.get_event_loop().call_soon_threadsafe(\
#                     queue.put_nowait, self.format(record) + "\n"
#                 )

#         queue_handler = QueueHandler()
#         logger.addHandler(queue_handler)

#         async def run_in_thread():
#             try:
#                 await asyncio.to_thread(scrape_titles)
#                 await asyncio.to_thread(clean_data)
#             finally:
#                 await queue.put(None)

#         task = asyncio.create_task(run_in_thread())

#         while True:
#             msg = await queue.get()
#             if msg is None:
#                 break
#             yield msg

#         logger.removeHandler(queue_handler)
#         await task

#     return StreamingResponse(generate(), media_type="text/plain")

@router.post("/scrape-titles/")
async def scrape_titles_endpoint(body: ScrapeLinksRequest):
    async def generate():
        try:
            yield f"SCraping links from {str(body.url)}\n"
            links = await asyncio.to_thread(scrape_links, str(body.url))
            yield f"Scraped {len(links)} links\n"

            if not links:
                yield "No links found."
                return
            
            await asyncio.to_thread(save_links, links)
            yield "Links saved."

            yield f"Starting to scrape titles from {len(links)} links\n"
            results = await asyncio.to_thread(scrape_titles, links)
            yield f"Finished. {len(results)} titles scraped.\n"

        except Exception as e:
            logger.error(f"Error in scraping titles: {e}")
            yield f"Error: {str(e)}\n"
    
    return StreamingResponse(generate(), media_type="text/plain")

@router.post("/run-scraping-processes/")
async def run_all(body: ScrapeLinksRequest, background_task: BackgroundTasks):
    async def full_pipeline():
        logger.info("Starting pipeline..")

        links = await asyncio.to_thread(scrape_links, body.url)
        logger.info(f"Step 1: Scraped {len(links)} links")
        SCRAPED_LINKS_COUNT.inc(len(links))

        await asyncio.to_thread(scrape_titles)
        logger.info("Step 2: Scraped titles")

        await asyncio.to_thread(clean_data)
        logger.info("Step 3: Cleaned data")

        logger.info("Pipeline completed successfully.")

    background_task.add_task(full_pipeline)
    return {"message": f"Pipeline started for URL: {body.url}"}