"""
American Eagle Product Scraper
Scrapes all products from American Eagle, generates image embeddings, and stores in Supabase.
"""

import asyncio
import json
import logging
import re
import time
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright, Page, Browser
from supabase import create_client, Client
from transformers import AutoProcessor, AutoModel
from PIL import Image
import torch
from tqdm import tqdm

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class ImageEmbedder:
    """Handles image embedding generation using SigLIP model."""
    
    def __init__(self):
        logger.info("Loading SigLIP model (google/siglip-base-patch16-384)...")
        self.processor = AutoProcessor.from_pretrained("google/siglip-base-patch16-384")
        self.model = AutoModel.from_pretrained("google/siglip-base-patch16-384")
        self.model.eval()
        logger.info("Model loaded successfully")
    
    def generate_embedding(self, image_url: str) -> Optional[List[float]]:
        """
        Generate 768-dim embedding from image URL.
        
        Args:
            image_url: URL of the product image
            
        Returns:
            768-dimensional embedding vector or None if failed
        """
        try:
            # Download image
            response = requests.get(image_url, timeout=30, stream=True, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            response.raise_for_status()
            
            # Load and process image
            image = Image.open(response.raw).convert('RGB')
            
            # Process image and generate embedding
            inputs = self.processor(images=image, return_tensors="pt")
            
            with torch.no_grad():
                outputs = self.model.get_image_features(**inputs)
                # Normalize to get unit vector
                embedding = torch.nn.functional.normalize(outputs, dim=-1)
                embedding_list = embedding[0].cpu().numpy().tolist()
            
            # Ensure it's 768 dimensions
            if len(embedding_list) != 768:
                logger.warning(f"Embedding dimension mismatch: {len(embedding_list)} != 768")
                return None
            
            return embedding_list
            
        except Exception as e:
            logger.error(f"Error generating embedding for {image_url}: {str(e)}")
            return None


class SupabaseClient:
    """Handles Supabase database operations."""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        self.supabase: Client = create_client(supabase_url, supabase_key)
        logger.info("Connected to Supabase")
    
    def upsert_product(self, product_data: Dict) -> bool:
        """
        Insert or update product in Supabase.
        
        Args:
            product_data: Dictionary containing product information
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Prepare data for Supabase
            supabase_data = {
                'id': product_data['id'],
                'source': product_data.get('source', 'scraper'),
                'product_url': product_data['product_url'],
                'affiliate_url': product_data.get('affiliate_url'),
                'image_url': product_data['image_url'],
                'brand': product_data.get('brand', 'American Eagle'),
                'title': product_data['title'],
                'description': product_data.get('description'),
                'category': product_data.get('category'),
                'gender': product_data.get('gender'),
                'price': product_data.get('price'),
                'currency': product_data.get('currency', 'USD'),
                'size': product_data.get('size'),
                'second_hand': product_data.get('second_hand', False),
                'embedding': product_data.get('embedding'),
                'metadata': json.dumps(product_data.get('metadata', {})) if product_data.get('metadata') else None,
                'created_at': datetime.now().isoformat()
            }
            
            # Upsert (insert or update on conflict)
            # Note: Supabase handles upsert based on primary key or unique constraint
            # The unique constraint is on (source, product_url)
            result = self.supabase.table('products').upsert(
                supabase_data
            ).execute()
            
            if not result.data:
                logger.warning(f"No data returned from upsert for {product_data.get('product_url')}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error upserting product {product_data.get('product_url')}: {str(e)}")
            return False


class AmericanEagleScraper:
    """Main scraper class for American Eagle products."""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        self.base_url = "https://www.ae.com"
        self.supabase_client = SupabaseClient(supabase_url, supabase_key)
        self.embedder = ImageEmbedder()
        self.scraped_urls: Set[str] = set()
        self.failed_urls: Set[str] = set()
        
    def generate_product_id(self, product_url: str) -> str:
        """Generate unique ID from product URL."""
        return hashlib.sha256(product_url.encode()).hexdigest()
    
    async def scroll_and_load_products(self, page: Page, max_scrolls: int = 50, max_products: Optional[int] = None) -> List[str]:
        """
        Scroll page to load all products via infinite scroll.
        
        Args:
            page: Playwright page object
            max_scrolls: Maximum number of scroll attempts
            
        Returns:
            List of product URLs found
        """
        product_urls = []
        last_height = 0
        scroll_attempts = 0
        no_change_count = 0
        
        logger.info("Starting to scroll and load products...")
        
        while scroll_attempts < max_scrolls:
            # Scroll to bottom
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)  # Wait for content to load
            
            # Get current height
            current_height = await page.evaluate("document.body.scrollHeight")
            
            # Extract product URLs from current view
            current_urls = await page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('a[href*="/p/"]'));
                    return links.map(link => link.href).filter(href => href.includes('/p/'));
                }
            """)
            
            # Add unique URLs
            for url in current_urls:
                if url not in product_urls:
                    product_urls.append(url)
                    # Stop if we've reached max products limit
                    if max_products and len(product_urls) >= max_products:
                        logger.info(f"Reached max products limit: {max_products}")
                        break
            
            # Check if we've reached max products or bottom
            if max_products and len(product_urls) >= max_products:
                break
            
            # Check if we've reached the bottom
            if current_height == last_height:
                no_change_count += 1
                if no_change_count >= 3:
                    logger.info("Reached end of page (no more content loading)")
                    break
            else:
                no_change_count = 0
            
            last_height = current_height
            scroll_attempts += 1
            
            if scroll_attempts % 10 == 0:
                logger.info(f"Scrolled {scroll_attempts} times, found {len(product_urls)} products so far...")
        
        logger.info(f"Finished scrolling. Found {len(product_urls)} unique product URLs")
        return list(set(product_urls))  # Remove duplicates
    
    async def extract_product_data(self, page: Page, product_url: str) -> Optional[Dict]:
        """
        Extract product data from product detail page.
        
        Args:
            page: Playwright page object
            product_url: URL of the product page
            
        Returns:
            Dictionary with product data or None if failed
        """
        try:
            await page.goto(product_url, wait_until='domcontentloaded', timeout=90000)
            await asyncio.sleep(3)  # Wait for dynamic content
            
            # Extract data using JavaScript
            product_data = await page.evaluate("""
                () => {
                    const data = {};
                    
                    // Title - multiple selectors
                    const titleSelectors = [
                        'h1[data-testid="product-title"]',
                        'h1.product-title',
                        'h1[class*="ProductTitle"]',
                        'h1[class*="product-title"]',
                        '[data-testid="product-name"]',
                        '.product-name',
                        'h1'
                    ];
                    for (const selector of titleSelectors) {
                        const el = document.querySelector(selector);
                        if (el && el.textContent.trim()) {
                            data.title = el.textContent.trim();
                            break;
                        }
                    }
                    
                    // Price
                    const priceEl = document.querySelector('[data-testid="product-price"], .product-price, [class*="price"]');
                    if (priceEl) {
                        const priceText = priceEl.textContent.trim();
                        const priceMatch = priceText.match(/[0-9,]+\.?[0-9]*/);
                        data.price_text = priceMatch ? priceMatch[0].replace(',', '') : '';
                    }
                    
                    // Currency
                    const currencyMatch = document.body.textContent.match(/\$|USD|EUR|GBP/);
                    data.currency = currencyMatch ? (currencyMatch[0] === '$' ? 'USD' : currencyMatch[0]) : 'USD';
                    
                    // Image URL
                    let imgEl = document.querySelector('img[data-testid="product-image"], img.product-image, img[class*="product-image"], .product-image img');
                    if (!imgEl) {
                        // Try to find any large product image
                        const images = Array.from(document.querySelectorAll('img'));
                        imgEl = images.find(img => {
                            const src = img.src || img.getAttribute('data-src') || '';
                            return src.includes('product') || (src.includes('ae.com') && (src.includes('.jpg') || src.includes('.png')));
                        });
                    }
                    data.image_url = imgEl ? (imgEl.src || imgEl.getAttribute('data-src') || '') : '';
                    
                    // Description
                    const descEl = document.querySelector('[data-testid="product-description"], .product-description, [class*="description"]');
                    data.description = descEl ? descEl.textContent.trim() : '';
                    
                    // Sizes
                    const sizeSelectors = [
                        '[data-testid*="size"]',
                        'button[class*="size"]',
                        '.size-selector button',
                        '[class*="SizeSelector"] button'
                    ];
                    const sizeButtons = [];
                    for (const selector of sizeSelectors) {
                        const buttons = document.querySelectorAll(selector);
                        if (buttons.length > 0) {
                            sizeButtons.push(...Array.from(buttons));
                            break;
                        }
                    }
                    data.sizes = sizeButtons.map(btn => btn.textContent.trim()).filter(s => s && s.length < 10);
                    
                    // Category
                    const breadcrumb = Array.from(document.querySelectorAll('[class*="breadcrumb"] a, nav[aria-label*="breadcrumb"] a'));
                    data.category = breadcrumb.length > 0 ? breadcrumb[breadcrumb.length - 1].textContent.trim() : '';
                    
                    // Gender from URL
                    const path = window.location.pathname.toLowerCase();
                    if (path.includes('/women/') || path.includes('/womens')) {
                        data.gender = 'WOMAN';
                    } else if (path.includes('/men/') || path.includes('/mens')) {
                        data.gender = 'MAN';
                    } else {
                        data.gender = 'OTHER';
                    }
                    
                    // Metadata
                    const breadcrumbs = Array.from(document.querySelectorAll('[class*="breadcrumb"] a, nav[aria-label*="breadcrumb"] a')).map(b => b.textContent.trim());
                    data.metadata = {
                        'url': window.location.href,
                        'breadcrumbs': breadcrumbs
                    };
                    
                    return data;
                }
            """)
            
            # Validate required fields
            if not product_data.get('title'):
                logger.warning(f"No title found for {product_url}")
                return None
            
            if not product_data.get('image_url'):
                logger.warning(f"No image found for {product_url}")
                return None
            
            # Parse price
            price = None
            if product_data.get('price_text'):
                try:
                    price = float(product_data['price_text'])
                except:
                    # Try regex extraction as fallback
                    price_text = product_data.get('price_text', '')
                    price_match = re.search(r'(\d+\.?\d*)', price_text)
                    if price_match:
                        price = float(price_match.group(1))
            
            # Get full image URL
            image_url = product_data.get('image_url', '')
            if image_url:
                if not image_url.startswith('http'):
                    image_url = urljoin(self.base_url, image_url)
                if not image_url.startswith('http'):
                    logger.warning(f"Invalid image URL: {image_url}")
                    return None
            
            # Prepare final product data
            product_id = self.generate_product_id(product_url)
            
            result = {
                'id': product_id,
                'source': 'scraper',
                'product_url': product_url,
                'affiliate_url': None,
                'image_url': image_url,
                'brand': 'American Eagle',
                'title': product_data.get('title', '').strip(),
                'description': product_data.get('description', '').strip() if product_data.get('description') else None,
                'category': product_data.get('category', '').strip() if product_data.get('category') else None,
                'gender': product_data.get('gender', 'OTHER'),
                'price': price,
                'currency': product_data.get('currency', 'USD'),
                'size': ', '.join(product_data.get('sizes', [])) if product_data.get('sizes') else None,
                'second_hand': False,
                'metadata': product_data.get('metadata', {})
            }
            
            # Generate embedding if we have an image
            if image_url:
                logger.info(f"Generating embedding for: {result['title'][:50]}...")
                embedding = self.embedder.generate_embedding(image_url)
                if embedding:
                    result['embedding'] = embedding
                    logger.info(f"[OK] Generated embedding ({len(embedding)} dims)")
                else:
                    logger.warning(f"Failed to generate embedding for {product_url}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error extracting product data from {product_url}: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return None
    
    async def scrape_category(self, category_url: str, browser: Browser, max_products: Optional[int] = None):
        """
        Scrape all products from a category page.
        
        Args:
            category_url: URL of the category page
            browser: Playwright browser instance
        """
        logger.info(f"Scraping category: {category_url}")
        
        page = await browser.new_page()
        
        try:
            await page.goto(category_url, wait_until='networkidle', timeout=60000)
            await asyncio.sleep(3)  # Initial wait
            
            # Get all product URLs by scrolling
            product_urls = await self.scroll_and_load_products(page, max_products=max_products)
            
            logger.info(f"Found {len(product_urls)} products in category")
            
            # Process each product
            for product_url in tqdm(product_urls, desc="Processing products"):
                if product_url in self.scraped_urls:
                    continue
                
                try:
                    # Extract product data
                    product_data = await self.extract_product_data(page, product_url)
                    
                    if product_data and product_data.get('title'):
                        # Save to Supabase
                        success = self.supabase_client.upsert_product(product_data)
                        
                        if success:
                            self.scraped_urls.add(product_url)
                            logger.info(f"[OK] Saved: {product_data['title']}")
                        else:
                            self.failed_urls.add(product_url)
                            logger.error(f"[FAIL] Failed to save: {product_url}")
                    else:
                        logger.warning(f"[FAIL] Failed to extract data from: {product_url}")
                        self.failed_urls.add(product_url)
                    
                    # Rate limiting
                    await asyncio.sleep(1)
                    
                except Exception as e:
                    logger.error(f"Error processing {product_url}: {str(e)}")
                    self.failed_urls.add(product_url)
                    await asyncio.sleep(2)
            
        finally:
            await page.close()
    
    async def run(self, category_urls: List[str], max_products_per_category: Optional[int] = None):
        """
        Run the scraper for given category URLs.
        
        Args:
            category_urls: List of category page URLs to scrape
        """
        logger.info("Starting American Eagle scraper...")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            try:
                for category_url in category_urls:
                    await self.scrape_category(category_url, browser, max_products=max_products_per_category)
                    await asyncio.sleep(3)  # Wait between categories
                
            finally:
                await browser.close()
        
        # Summary
        logger.info("\n" + "="*50)
        logger.info("SCRAPING COMPLETE")
        logger.info(f"Successfully scraped: {len(self.scraped_urls)} products")
        logger.info(f"Failed: {len(self.failed_urls)} products")
        if self.failed_urls:
            logger.info("Failed URLs:")
            for url in list(self.failed_urls)[:10]:  # Show first 10
                logger.info(f"  - {url}")


async def main():
    """Main entry point."""
    import sys
    import os
    
    # Check if running in test mode
    TEST_MODE = '--test' in sys.argv or 'test' in sys.argv
    MAX_PRODUCTS = 5 if TEST_MODE else None  # Limit to 5 products in test mode
    
    # Supabase credentials from environment variables or fallback to defaults
    SUPABASE_URL = os.getenv('SUPABASE_URL', "https://yqawmzggcgpeyaaynrjk.supabase.co")
    SUPABASE_KEY = os.getenv('SUPABASE_KEY', "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlxYXdtemdnY2dwZXlhYXlucmprIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NTAxMDkyNiwiZXhwIjoyMDcwNTg2OTI2fQ.XtLpxausFriraFJeX27ZzsdQsFv3uQKXBBggoz6P4D4")
    
    # Category URLs to scrape
    category_urls = [
        "https://www.ae.com/us/en/c/men/mens?pagetype=clp",
        # Add more category URLs here if needed
        # "https://www.ae.com/us/en/c/women/womens?pagetype=clp",
    ]
    
    if TEST_MODE:
        logger.info("="*50)
        logger.info("RUNNING IN TEST MODE - Limited to 5 products")
        logger.info("="*50)
    
    scraper = AmericanEagleScraper(SUPABASE_URL, SUPABASE_KEY)
    await scraper.run(category_urls, max_products_per_category=MAX_PRODUCTS)


if __name__ == "__main__":
    asyncio.run(main())

