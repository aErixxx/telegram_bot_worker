import asyncio
import os
import json
import base64
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from playwright.async_api import async_playwright
import logging
import uvicorn
import secrets
import hashlib


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security configuration
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    # Generate a random secret key if not provided
    SECRET_KEY = secrets.token_urlsafe(32)
    logger.warning("SECRET_KEY not found in environment. Generated temporary key.")

# FastAPI app
app = FastAPI(title="Playwright Worker API", version="1.0.0")
security = HTTPBearer()

# Security functions
async def verify_secret_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify the secret key from Authorization header"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authorization header missing")
    
    # Compare the provided token with our secret key
    if not secrets.compare_digest(credentials.credentials, SECRET_KEY):
        raise HTTPException(status_code=401, detail="Invalid secret key")
    
    return credentials.credentials

async def verify_api_key(x_api_key: str = Header(None)):
    """Alternative: Verify API key from X-API-Key header"""
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
    wait_for: str = "networkidle"  # load, domcontentloaded, networkidle

class ContentRequest(BaseModel):
    url: str
    wait_for: str = "networkidle"
    selector: str = None  # Optional CSS selector to get specific content

class ActionRequest(BaseModel):
    url: str
    actions: list  # List of actions to perform
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
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.is_initialized = False
        
    async def initialize(self):
        """Initialize Playwright browser"""
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
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor'
                ]
            )
            self.is_initialized = True
            logger.info("Playwright browser initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Playwright: {e}")
            raise
    
    async def close(self):
        """Close Playwright browser"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.is_initialized = False
        logger.info("Playwright browser closed")
    
    async def take_screenshot(self, url: str, full_page: bool = True, width: int = 1920, height: int = 1080, wait_for: str = "networkidle") -> bytes:
        """Take screenshot of a webpage"""
        try:
            await self.initialize()
            
            page = await self.browser.new_page()
            await page.set_viewport_size({"width": width, "height": height})
            await page.goto(url, timeout=30000)
            
            # Wait for page to be ready
            if wait_for == "networkidle":
                await page.wait_for_load_state('networkidle', timeout=30000)
            elif wait_for == "load":
                await page.wait_for_load_state('load', timeout=30000)
            elif wait_for == "domcontentloaded":
                await page.wait_for_load_state('domcontentloaded', timeout=30000)
            
            # Take screenshot
            screenshot = await page.screenshot(full_page=full_page, type='png')
            await page.close()
            return screenshot
            
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            raise
    
    async def get_page_content(self, url: str, wait_for: str = "networkidle", selector: str = None) -> dict:
        """Get page content"""
        try:
            await self.initialize()
            
            page = await self.browser.new_page()
            await page.goto(url, timeout=30000)
            
            # Wait for page to be ready
            if wait_for == "networkidle":
                await page.wait_for_load_state('networkidle', timeout=30000)
            elif wait_for == "load":
                await page.wait_for_load_state('load', timeout=30000)
            elif wait_for == "domcontentloaded":
                await page.wait_for_load_state('domcontentloaded', timeout=30000)
            
            # Get content
            title = await page.title()
            
            if selector:
                # Get specific element content
                element = await page.query_selector(selector)
                if element:
                    content = await element.inner_html()
                else:
                    content = f"Element with selector '{selector}' not found"
            else:
                # Get full page content
                content = await page.content()
            
            await page.close()
            return {"title": title, "content": content}
            
        except Exception as e:
            logger.error(f"Failed to get page content: {e}")
            raise
    
    async def perform_actions(self, url: str, actions: list, screenshot_after: bool = True) -> dict:
        """Perform actions on a webpage"""
        try:
            await self.initialize()
            
            page = await self.browser.new_page()
            await page.goto(url, timeout=30000)
            await page.wait_for_load_state('networkidle', timeout=30000)
            
            results = []
            
            # Perform each action
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
            
            # Take screenshot if requested
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

# Initialize worker
playwright_worker = PlaywrightWorker()

@app.on_event("startup")
async def startup_event():
    """Initialize Playwright on startup"""
    await playwright_worker.initialize()

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    await playwright_worker.close()

@app.get("/")
async def root():
    """Public health check endpoint"""
    return {
        "message": "Playwright Worker API is running",
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "auth_required": True
    }

@app.get("/health")
async def health_check(api_key: str = Depends(verify_api_key)):
    """Authenticated health check"""
    return {
        "status": "healthy",
        "playwright_initialized": playwright_worker.is_initialized,
        "timestamp": datetime.now().isoformat(),
        "authenticated": True
    }

@app.post("/screenshot", response_model=ScreenshotResponse)
async def take_screenshot(request: ScreenshotRequest, api_key: str = Depends(verify_api_key)):
    """Take screenshot of a webpage - Requires API Key"""
    try:
        screenshot_bytes = await playwright_worker.take_screenshot(
            url=request.url,
            full_page=request.full_page,
            width=request.width,
            height=request.height,
            wait_for=request.wait_for
        )
        
        # Convert to base64
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
    """Get webpage content - Requires API Key"""
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
    """Perform actions on a webpage - Requires API Key"""
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
    # Get port from environment variable (for Render deployment)
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)