"""
Test script for American Eagle scraper
Tests with limited products to verify everything works
"""

import asyncio
from scraper import AmericanEagleScraper
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_scraper():
    """Test the scraper with limited products."""
    import os
    
    logger.info("="*60)
    logger.info("TESTING AMERICAN EAGLE SCRAPER")
    logger.info("="*60)
    
    # Supabase credentials from environment variables or fallback to defaults
    SUPABASE_URL = os.getenv('SUPABASE_URL', "https://yqawmzggcgpeyaaynrjk.supabase.co")
    SUPABASE_KEY = os.getenv('SUPABASE_KEY', "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlxYXdtemdnY2dwZXlhYXlucmprIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NTAxMDkyNiwiZXhwIjoyMDcwNTg2OTI2fQ.XtLpxausFriraFJeX27ZzsdQsFv3uQKXBBggoz6P4D4")
    
    # Test with just 3 products
    category_urls = [
        "https://www.ae.com/us/en/c/men/mens?pagetype=clp",
    ]
    
    logger.info("Initializing scraper...")
    scraper = AmericanEagleScraper(SUPABASE_URL, SUPABASE_KEY)
    
    logger.info("Starting test scrape (limited to 3 products)...")
    await scraper.run(category_urls, max_products_per_category=3)
    
    logger.info("="*60)
    logger.info("TEST COMPLETE")
    logger.info(f"Successfully processed: {len(scraper.scraped_urls)} products")
    logger.info(f"Failed: {len(scraper.failed_urls)} products")
    logger.info("="*60)
    
    # Show what was scraped
    if scraper.scraped_urls:
        logger.info("\nSuccessfully scraped products:")
        for url in list(scraper.scraped_urls)[:5]:
            logger.info(f"  [OK] {url}")
    
    if scraper.failed_urls:
        logger.info("\nFailed products:")
        for url in list(scraper.failed_urls)[:5]:
            logger.info(f"  [FAIL] {url}")


if __name__ == "__main__":
    asyncio.run(test_scraper())

