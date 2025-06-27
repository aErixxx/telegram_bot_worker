# 🤖 Playwright Worker API

A secure REST API service for web automation tasks using Playwright. Perfect for integrating with Telegram bots or other applications that need web scraping, screenshot capture, and browser automation capabilities.

## ✨ Features

- 📸 **Screenshot Capture** - Take full-page or viewport screenshots of any webpage
- 📄 **Content Extraction** - Extract HTML content, page titles, and specific elements
- 🎯 **Browser Automation** - Perform actions like clicking, typing, scrolling
- 🔐 **Secure Authentication** - API key-based authentication
- 🚀 **Fast & Reliable** - Built with FastAPI and async Playwright
- 🐳 **Docker Ready** - Containerized for easy deployment

## 🚀 Quick Start

### 1. Clone Repository
```bash
git clone https://github.com/yourusername/playwright-worker.git
cd playwright-worker
```

### 2. Environment Setup
Create a `.env` file:
```env
SECRET_KEY=your_super_secret_key_here
PORT=8000
```

### 3. Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install --with-deps chromium

# Run the server
python worker.py
```

### 4. Docker Deployment
```bash
# Build image
docker build -t playwright-worker .

# Run container
docker run -p 8000:8000 -e SECRET_KEY=your_secret_key playwright-worker
```

## 📡 API Endpoints

### Authentication
All endpoints (except `/`) require authentication via `X-API-Key` header:
```bash
X-API-Key: your_secret_key_here
```

### 🏠 Health Check
```http
GET /
GET /health
```

### 📸 Screenshot
```http
POST /screenshot
Content-Type: application/json
X-API-Key: your_secret_key

{
    "url": "https://example.com",
    "full_page": true,
    "width": 1920,
    "height": 1080,
    "wait_for": "networkidle"
}
```

**Response:**
```json
{
    "success": true,
    "image_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
    "timestamp": "2024-01-01T12:00:00",
    "url": "https://example.com"
}
```

### 📄 Content Extraction
```http
POST /content
Content-Type: application/json
X-API-Key: your_secret_key

{
    "url": "https://example.com",
    "wait_for": "networkidle",
    "selector": ".main-content"
}
```

**Response:**
```json
{
    "success": true,
    "content": "<html>...</html>",
    "title": "Example Page",
    "timestamp": "2024-01-01T12:00:00",
    "url": "https://example.com"
}
```

### 🎯 Browser Actions
```http
POST /actions
Content-Type: application/json
X-API-Key: your_secret_key

{
    "url": "https://example.com",
    "actions": [
        {"type": "click", "selector": "#button1"},
        {"type": "type", "selector": "#input1", "text": "hello world"},
        {"type": "wait", "timeout": 2000},
        {"type": "wait_for_selector", "selector": ".result"},
        {"type": "scroll"}
    ],
    "screenshot_after": true
}
```

**Response:**
```json
{
    "success": true,
    "result": {
        "actions_performed": ["Clicked: #button1", "Typed 'hello world' in: #input1", ...]
    },
    "screenshot_base64": "iVBORw0KGgoAAAANSUhEUgAA...",
    "timestamp": "2024-01-01T12:00:00",
    "url": "https://example.com"
}
```

## 🔧 Configuration Options

### Screenshot Parameters
- `url` (string, required): Target webpage URL
- `full_page` (boolean, default: true): Capture full page or viewport only
- `width` (integer, default: 1920): Viewport width
- `height` (integer, default: 1080): Viewport height
- `wait_for` (string, default: "networkidle"): When to take screenshot
  - `"load"` - Wait for load event
  - `"domcontentloaded"` - Wait for DOM content loaded
  - `"networkidle"` - Wait for network to be idle

### Content Parameters
- `url` (string, required): Target webpage URL
- `wait_for` (string, default: "networkidle"): When to extract content
- `selector` (string, optional): CSS selector for specific element

### Action Types
- `{"type": "click", "selector": "#element"}` - Click element
- `{"type": "type", "selector": "#input", "text": "content"}` - Type text
- `{"type": "wait", "timeout": 1000}` - Wait for milliseconds
- `{"type": "wait_for_selector", "selector": "#element"}` - Wait for element
- `{"type": "scroll"}` - Scroll to bottom

## 🤖 Integration Examples

### Python (aiohttp)
```python
import aiohttp
import base64

async def take_screenshot(url: str):
    headers = {
        "X-API-Key": "your_secret_key",
        "Content-Type": "application/json"
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://your-worker.onrender.com/screenshot",
            json={"url": url},
            headers=headers
        ) as response:
            data = await response.json()
            
            if data["success"]:
                # Decode base64 image
                image_bytes = base64.b64decode(data["image_base64"])
                return image_bytes
            else:
                raise Exception(data["error"])
```

### Telegram Bot (aiogram)
```python
from aiogram import Bot
from aiogram.types import BufferedInputFile
import aiohttp
import base64

async def screenshot_command(message, url: str):
    # Call worker API
    image_bytes = await take_screenshot(url)
    
    # Send to Telegram
    photo = BufferedInputFile(image_bytes, filename="screenshot.png")
    await message.answer_photo(photo, caption=f"Screenshot of: {url}")
```

### JavaScript/Node.js
```javascript
const axios = require('axios');

async function takeScreenshot(url) {
    const response = await axios.post('https://your-worker.onrender.com/screenshot', {
        url: url
    }, {
        headers: {
            'X-API-Key': 'your_secret_key',
            'Content-Type': 'application/json'
        }
    });
    
    if (response.data.success) {
        return Buffer.from(response.data.image_base64, 'base64');
    } else {
        throw new Error(response.data.error);
    }
}
```

## 🚀 Deployment

### Render.com
1. Connect your GitHub repository
2. Select "Web Service"
3. Set Environment Variables:
   ```
   SECRET_KEY=your_generated_secret_key
   PORT=8000
   ```
4. Deploy automatically from Git pushes

### Railway
1. Connect GitHub repository
2. Add environment variables
3. Deploy with Docker

### Heroku
1. Create new app
2. Connect GitHub
3. Set Config Vars
4. Deploy

## 🔒 Security

- ✅ API Key authentication on all endpoints
- ✅ Secure key comparison (timing attack safe)
- ✅ No data logging or storage
- ✅ Environment variable configuration
- ✅ Docker containerization

### Generate Secret Key
Use any of these services to generate a secure API key:
- [RandomKeygen.com](https://randomkeygen.com/)
- [StrongDM API Key Generator](https://www.strongdm.com/tools/api-key-generator)
- [API-Keygen.com](https://api-keygen.com/)

## 📋 Requirements

- Python 3.11+
- FastAPI
- Playwright
- Uvicorn
- Docker (for containerized deployment)

## 🐛 Troubleshooting

### Common Issues

**"Playwright not found"**
```bash
playwright install --with-deps chromium
```

**"Port already in use"**
```bash
# Change port in environment variables
export PORT=8001
```

**"Authentication failed"**
- Check `X-API-Key` header
- Verify SECRET_KEY environment variable
- Ensure key matches exactly

### Error Responses
All endpoints return error details:
```json
{
    "success": false,
    "error": "Detailed error message",
    "timestamp": "2024-01-01T12:00:00",
    "url": "https://example.com"
}
```

## 📞 Support

- 🐛 Report issues: [GitHub Issues](https://github.com/yourusername/playwright-worker/issues)
- 📖 Documentation: This README
- 💬 Questions: Create a discussion

## 📄 License

MIT License - see LICENSE file for details.

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

---

**Made with ❤️ for web automation**