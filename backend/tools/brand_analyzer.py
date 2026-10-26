"""Brand Analyzer Tool - Crawls websites and analyzes brand identity using Gemini."""

import os
import asyncio
import json
from typing import Dict, Any, Optional
from bs4 import BeautifulSoup

# Lazy import for playwright to avoid blocking at module load
_playwright = None


async def _get_playwright():
    """Lazy load playwright."""
    global _playwright
    if _playwright is None:
        from playwright.async_api import async_playwright
        _playwright = async_playwright
    return _playwright


async def fetch_dynamic_content(url: str, max_chars: int = 15000) -> str:
    """
    Uses a headless browser to fetch the text content of a dynamic website.
    Useful for sites that rely on JavaScript to render content.

    Args:
        url: The URL to visit.
        max_chars: Maximum characters to return (to save tokens).

    Returns:
        Cleaned text content from the website.
    """
    print(f"🤖 Crawling: {url} ...")

    async_playwright = await _get_playwright()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        page = await context.new_page()

        try:
            # Try different wait strategies for resilience
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                # Wait a bit more for dynamic content
                await asyncio.sleep(2)
            except Exception:
                # Fallback: just load the page
                await page.goto(url, timeout=30000)
                await asyncio.sleep(3)

            content = await page.content()

            soup = BeautifulSoup(content, 'html.parser')

            # Remove noise elements
            for element in soup(["script", "style", "nav", "footer", "iframe", "noscript"]):
                element.decompose()

            text = soup.get_text(separator=' ', strip=True)

            return text[:max_chars]

        except Exception as e:
            return f"Error fetching site: {str(e)}"
        finally:
            await browser.close()


# Response schema for structured output
BRAND_ANALYSIS_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "brand_name": {
            "type": "OBJECT",
            "properties": {
                "english": {"type": "STRING"},
                "chinese": {"type": "STRING"}
            }
        },
        "brand_type": {
            "type": "OBJECT",
            "properties": {
                "industry": {"type": "STRING"},
                "niche": {"type": "STRING"},
                "target_audience": {"type": "STRING"}
            }
        },
        "description": {
            "type": "OBJECT",
            "properties": {
                "core_value": {"type": "STRING"},
                "key_products": {"type": "ARRAY", "items": {"type": "STRING"}},
                "summary": {"type": "STRING"}
            }
        },
        "visual_style": {
            "type": "OBJECT",
            "properties": {
                "colors": {"type": "ARRAY", "items": {"type": "STRING"}},
                "font_style_inference": {"type": "STRING"},
                "overall_vibe": {"type": "STRING"}
            }
        },
        "marketing": {
            "type": "OBJECT",
            "properties": {
                "hot_keywords": {"type": "ARRAY", "items": {"type": "STRING"}},
                "hot_products": {"type": "ARRAY", "items": {"type": "STRING"}},
                "promotion_slogans": {"type": "ARRAY", "items": {"type": "STRING"}}
            }
        }
    },
    "required": ["brand_name", "brand_type", "description", "visual_style", "marketing"]
}


async def analyze_brand_async(url: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyze a brand website and extract brand identity information.

    Args:
        url: The brand website URL to analyze.
        api_key: Gemini API key (per-site credential); falls back to env vars.

    Returns:
        Dictionary containing brand analysis results.
    """
    import google.generativeai as genai

    # Configure API
    api_key = api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {"success": False, "error": "GOOGLE_API_KEY or GEMINI_API_KEY not set"}

    genai.configure(api_key=api_key)

    # Initialize model with JSON response
    # Use gemini-1.5-flash or gemini-2.0-flash for faster response
    model = genai.GenerativeModel(
        model_name='gemini-2.0-flash',
        generation_config={
            "response_mime_type": "application/json",
            "response_schema": BRAND_ANALYSIS_SCHEMA
        }
    )

    # Step 1: Fetch website content
    website_data = await fetch_dynamic_content(url)

    if website_data.startswith("Error"):
        return {"success": False, "error": website_data}

    # Step 2: Build analysis prompt
    prompt = f"""
    You are a Brand Expert Agent.
    I have scraped the content of a website for you.

    Analyze the following text content from {url} and extract the brand identity details.

    Extract:
    1. Brand name (English and Chinese if available)
    2. Brand type (industry, niche, target audience)
    3. Description (core value, key products, summary)
    4. Visual style (colors mentioned, font style inference, overall vibe)
    5. Marketing (hot keywords, hot products, promotion slogans)

    WEBSITE CONTENT:
    {website_data}
    """

    # Step 3: Generate analysis
    print("🧠 Analyzing brand with Gemini...")
    try:
        response = await model.generate_content_async(prompt)
        result = json.loads(response.text)
        return {"success": True, "data": result, "url": url}
    except Exception as e:
        return {"success": False, "error": f"Analysis failed: {str(e)}"}


def analyze_brand_sync(url: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Synchronous wrapper for brand analysis.

    Args:
        url: The brand website URL to analyze.
        api_key: Gemini API key (per-site credential); falls back to env vars.

    Returns:
        Dictionary containing brand analysis results.
    """
    try:
        # Check if we're already in an async context
        loop = asyncio.get_running_loop()
        # If we get here, there's a running loop - use nest_asyncio or thread
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, analyze_brand_async(url, api_key))
            return future.result(timeout=120)  # 2 minute timeout
    except RuntimeError:
        # No running loop, safe to use asyncio.run
        return asyncio.run(analyze_brand_async(url, api_key))


# For testing
if __name__ == "__main__":
    test_url = "https://www.nanhairich.com.tw/"
    result = analyze_brand_sync(test_url)
    print("\n" + "="*50)
    print("RESULT:")
    print("="*50)
    print(json.dumps(result, indent=2, ensure_ascii=False))
