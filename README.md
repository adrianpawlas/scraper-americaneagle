# American Eagle Product Scraper

A comprehensive scraper for American Eagle products that extracts product information, generates image embeddings using SigLIP, and stores everything in Supabase.

## Features

- ✅ Scrapes all products from American Eagle category pages
- ✅ Handles infinite scroll to load all products
- ✅ Extracts comprehensive product data (title, price, images, description, sizes, etc.)
- ✅ Generates 768-dimensional image embeddings using `google/siglip-base-patch16-384`
- ✅ Stores products in Supabase with automatic upsert (updates existing, inserts new)
- ✅ Robust error handling and retry logic
- ✅ Comprehensive logging
- ✅ Rate limiting to be respectful to the website
- ✅ GitHub Actions workflow for automated daily runs

## Requirements

- Python 3.8+
- Supabase account and database
- Internet connection

## Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install Playwright browsers:**
   ```bash
   playwright install chromium
   ```

3. **Configure Supabase credentials:**
   
   **For local runs:** Set environment variables or edit `scraper.py`:
   ```bash
   export SUPABASE_URL="your-supabase-url"
   export SUPABASE_KEY="your-supabase-key"
   ```
   
   **For GitHub Actions:** Add secrets in repository settings:
   - `SUPABASE_URL`
   - `SUPABASE_KEY`

## Usage

### Local Usage

**Full scrape:**
```bash
python scraper.py
```

**Test mode (limited to 5 products):**
```bash
python scraper.py --test
```

**Or use the test script:**
```bash
python test_scraper.py
```

### GitHub Actions

The scraper runs automatically:
- **Daily at midnight UTC** (via cron schedule)
- **Manually** via GitHub Actions UI (Workflow Dispatch)

To trigger manually:
1. Go to Actions tab in GitHub
2. Select "Scrape American Eagle Products"
3. Click "Run workflow"

**Note:** The workflow has a 12-hour timeout limit.

## Configuration

Edit the `main()` function in `scraper.py` to:
- Change category URLs to scrape
- Modify Supabase credentials (or use environment variables)
- Adjust rate limiting delays

Example:
```python
category_urls = [
    "https://www.ae.com/us/en/c/men/mens?pagetype=clp",
    "https://www.ae.com/us/en/c/women/womens?pagetype=clp",  # Add women's products
]
```

## Database Schema

The scraper stores data in the `products` table with the following fields:

- `id` - SHA256 hash of product URL (primary key)
- `source` - Always "scraper"
- `product_url` - Full URL to the product page
- `affiliate_url` - NULL (not used)
- `image_url` - URL to the main product image
- `brand` - Always "American Eagle"
- `title` - Product name/title
- `description` - Product description (if available)
- `category` - Product category from breadcrumbs
- `gender` - MAN, WOMAN, or OTHER
- `price` - Product price as float
- `currency` - USD, EUR, GBP, etc.
- `size` - Available sizes (comma-separated)
- `second_hand` - Always FALSE
- `embedding` - 768-dim vector from SigLIP model
- `metadata` - JSON string with additional data
- `created_at` - Timestamp of when product was imported

## How It Works

1. **Category Scraping**: Uses Playwright to load category pages and handle infinite scroll
2. **Product Extraction**: Visits each product page and extracts data using multiple selector strategies
3. **Image Embedding**: Downloads product images and generates embeddings using HuggingFace's SigLIP model
4. **Database Storage**: Upserts products to Supabase (updates if exists, inserts if new)

## Logging

The scraper creates a `scraper.log` file with detailed logs of all operations. Check this file for:
- Successfully scraped products
- Failed extractions
- Embedding generation status
- Database operations

In GitHub Actions, logs are uploaded as artifacts and retained for 7 days.

## Performance

- **Rate Limiting**: 1 second delay between products, 3 seconds between categories
- **Infinite Scroll**: Automatically detects when all products are loaded
- **Error Handling**: Continues processing even if individual products fail
- **Progress Tracking**: Shows progress bar for product processing
- **Timeout**: 12-hour limit for GitHub Actions runs

## Troubleshooting

### Playwright browser not found
```bash
playwright install chromium
```

### Model download issues
The first run will download the SigLIP model (~500MB). Ensure you have:
- Stable internet connection
- Sufficient disk space
- Write permissions in the cache directory

### Supabase connection errors
- Verify your Supabase URL and API key
- Check that the `products` table exists with the correct schema
- Ensure the service role key has write permissions
- For GitHub Actions, verify secrets are set correctly

### Image embedding failures
- Check internet connection for image downloads
- Verify image URLs are accessible
- Check available memory (model requires ~2GB RAM)

### GitHub Actions failures
- Check workflow logs in Actions tab
- Verify secrets are set correctly
- Ensure timeout is sufficient (12 hours default)
- Check if Playwright browsers installed correctly

## Notes

- The scraper respects rate limits with delays between requests
- Products are upserted based on `(source, product_url)` unique constraint
- Failed products are logged but don't stop the scraper
- The first run will be slower due to model download
- GitHub Actions runs have a 12-hour timeout limit

## License

This scraper is for educational and personal use only. Please respect American Eagle's terms of service and robots.txt.
