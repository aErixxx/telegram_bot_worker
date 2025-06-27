import asyncio
import os
import json
import base64
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from playwright.async_api import async_playwright
from contextlib import asynccontextmanager
import logging
import uvicorn
import secrets
import hashlib

@asynccontextmanager
async def lifespan(app: FastAPI):
    # โค้ดตอน startup
    print("Starting up")
    yield
    # โค้ดตอน shutdown
    print("Shutting down")
    
# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security configuration
SECRET_KEY = os.getenv('SECRET_KEY')

if not SECRET_KEY:
    # Generate a random secret key if not provided
    SECRET_KEY = secrets.token_urlsafe(32)
    logger.warning("SECRET_KEY not found in environment. Generated temporary key.")
print(f"SECRET_KEY: {SECRET_KEY}")     
# FastAPI app
app = FastAPI(title="Playwright Worker API", version="1.0.0", lifespan=lifespan)
security = HTTPBearer()

# Security functions
async def verify_secret_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    if not secrets.compare_digest(credentials.credentials, SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid secret key")
    return credentials.credentials

async def verify_api_key(x_api_key: str = Header(None)):
    print(f"Received X-API-Key: {x_api_key}") 
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header missing")
    if not secrets.compare_digest(x_api_key, SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return x_api_key

# Request models
class ScreenshotRequest(BaseModel):
    url: str
    full_page: bool = True
    width: int = 1920
    height: int = 1080
    wait_for: str = "networkidle"

class ContentRequest(BaseModel):
    url: str
    wait_for: str = "networkidle"
    selector: str = None

class ActionRequest(BaseModel):
    url: str
    actions: list
    screenshot_after: bool = True

# Response models
class ScreenshotResponse(BaseModel):
    success: bool
    image_base64: str = None
    error: str = None
    timestamp: str
    url: str

class ContentResponse(BaseModel):
    success: bool
    content: str = None
    title: str = None
    error: str = None
    timestamp: str
    url: str

class ActionResponse(BaseModel):
    success: bool
    result: dict = None
    screenshot_base64: str = None
    error: str = None
    timestamp: str
    url: str

class PlaywrightWorker:
    def __init__(self, storage_path="playwright_storage.json"):
        self.playwright = None
        self.browser = None
        self.is_initialized = False
        self.storage_path = storage_path
        self.context = None
        self.semaphore = asyncio.Semaphore(1)  # จำกัดรันทีละ 1 งาน

    async def initialize(self):
        if self.is_initialized:
            return
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--safebrowsing-disable-auto-update',
                    '--disable-extensions',
                    '--disable-sync',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            )
            if os.path.exists(self.storage_path):
                self.context = await self.browser.new_context(storage_state=self.storage_path)
                logger.info(f"Loaded session from {self.storage_path}")
            else:
                self.context = await self.browser.new_context()
                logger.info("Created new browser context without session")
            self.is_initialized = True
            logger.info("Playwright browser initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Playwright: {e}")
            raise

    async def save_storage(self):
        if self.context:
            await self.context.storage_state(path=self.storage_path)
            logger.info(f"Storage state saved to {self.storage_path}")

    async def close(self):
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.is_initialized = False
        logger.info("Playwright browser closed")

    async def take_screenshot(self, url: str, full_page: bool = True, width: int = 1920, height: int = 1080, wait_for: str = "networkidle") -> bytes:
        await self.initialize()
        async with self.semaphore:
            try:
                page = await self.browser.new_page()
                await page.set_viewport_size({"width": width, "height": height})
                await page.goto(url, timeout=30000)

                if wait_for == "networkidle":
                    await page.wait_for_load_state('networkidle', timeout=30000)
                elif wait_for == "load":
                    await page.wait_for_load_state('load', timeout=30000)
                elif wait_for == "domcontentloaded":
                    await page.wait_for_load_state('domcontentloaded', timeout=30000)

                screenshot = await page.screenshot(full_page=full_page, type='png')
                await page.close()
                return screenshot
            except Exception as e:
                logger.error(f"Failed to take screenshot: {e}")
                raise

    async def get_page_content(self, url: str, wait_for: str = "networkidle", selector: str = None) -> dict:
        await self.initialize()
        async with self.semaphore:
            try:
                page = await self.browser.new_page()
                await page.goto(url, timeout=30000)

                if wait_for == "networkidle":
                    await page.wait_for_load_state('networkidle', timeout=30000)
                elif wait_for == "load":
                    await page.wait_for_load_state('load', timeout=30000)
                elif wait_for == "domcontentloaded":
                    await page.wait_for_load_state('domcontentloaded', timeout=30000)

                title = await page.title()
                if selector:
                    element = await page.query_selector(selector)
                    if element:
                        content = await element.inner_html()
                    else:
                        content = f"Element with selector '{selector}' not found"
                else:
                    content = await page.content()

                await page.close()
                return {"title": title, "content": content}
            except Exception as e:
                logger.error(f"Failed to get page content: {e}")
                raise

    async def perform_actions(self, url: str, actions: list, screenshot_after: bool = True) -> dict:
        await self.initialize()
        async with self.semaphore:
            try:
                page = await self.browser.new_page()
                await page.goto(url, timeout=30000)
                await page.wait_for_load_state('networkidle', timeout=30000)

                results = []
                for action in actions:
                    action_type = action.get("type")

                    if action_type == "click":
                        selector = action.get("selector")
                        await page.click(selector)
                        results.append(f"Clicked: {selector}")

                    elif action_type == "type":
                        selector = action.get("selector")
                        text = action.get("text")
                        await page.fill(selector, text)
                        results.append(f"Typed '{text}' in: {selector}")

                    elif action_type == "wait":
                        timeout = action.get("timeout", 1000)
                        await page.wait_for_timeout(timeout)
                        results.append(f"Waited: {timeout}ms")

                    elif action_type == "wait_for_selector":
                        selector = action.get("selector")
                        await page.wait_for_selector(selector, timeout=10000)
                        results.append(f"Waited for selector: {selector}")

                    elif action_type == "scroll":
                        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        results.append("Scrolled to bottom")

                screenshot_base64 = None
                if screenshot_after:
                    screenshot = await page.screenshot(full_page=True, type='png')
                    screenshot_base64 = base64.b64encode(screenshot).decode('utf-8')

                await page.close()

                return {
                    "actions_performed": results,
                    "screenshot_base64": screenshot_base64
                }
            except Exception as e:
                logger.error(f"Failed to perform actions: {e}")
                raise

playwright_worker = PlaywrightWorker()

@app.get("/")
async def root():
    return {
        "message": "Playwright Worker API is running",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "auth_required": True
    }

@app.get("/health")
async def health_check(api_key: str = Depends(verify_api_key)):
    print(f"Received X-API-Key in health_check : {x_api_key}") 
    return {
        "status": "healthy",
        "playwright_initialized": playwright_worker.is_initialized,
        "timestamp": datetime.now().isoformat(),
        "authenticated": True
    }

@app.post("/screenshot", response_model=ScreenshotResponse)
async def take_screenshot(request: ScreenshotRequest, api_key: str = Depends(verify_api_key)):
    try:
        screenshot_bytes = await playwright_worker.take_screenshot(
            url=request.url,
            full_page=request.full_page,
            width=request.width,
            height=request.height,
            wait_for=request.wait_for
        )
        screenshot_base64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        return ScreenshotResponse(
            success=True,
            image_base64=screenshot_base64,
            timestamp=datetime.now().isoformat(),
            url=request.url
        )
    except Exception as e:
        logger.error(f"Screenshot error: {e}")
        return ScreenshotResponse(
            success=False,
            error=str(e),
            timestamp=datetime.now().isoformat(),
            url=request.url
        )

@app.post("/content", response_model=ContentResponse)
async def get_content(request: ContentRequest, api_key: str = Depends(verify_api_key)):
    try:
        result = await playwright_worker.get_page_content(
            url=request.url,
            wait_for=request.wait_for,
            selector=request.selector
        )
        return ContentResponse(
            success=True,
            content=result["content"],
            title=result["title"],
            timestamp=datetime.now().isoformat(),
            url=request.url
        )
    except Exception as e:
        logger.error(f"Content error: {e}")
        return ContentResponse(
            success=False,
            error=str(e),
            timestamp=datetime.now().isoformat(),
            url=request.url
        )

@app.post("/actions", response_model=ActionResponse)
async def perform_actions(request: ActionRequest, api_key: str = Depends(verify_api_key)):
    try:
        result = await playwright_worker.perform_actions(
            url=request.url,
            actions=request.actions,
            screenshot_after=request.screenshot_after
        )
        return ActionResponse(
            success=True,
            result={"actions_performed": result["actions_performed"]},
            screenshot_base64=result["screenshot_base64"],
            timestamp=datetime.now().isoformat(),
            url=request.url
        )
    except Exception as e:
        logger.error(f"Actions error: {e}")
        return ActionResponse(
            success=False,
            error=str(e),
            timestamp=datetime.now().isoformat(),
            url=request.url
        )


if __name__ == "__main__":
    uvicorn.run("worker:app", host="0.0.0.0", port=8000, reload=False)
