# GitHub Actions Setup Guide

## Setting Up Secrets

For the GitHub Actions workflow to work, you need to add the following secrets to your repository:

1. Go to your repository on GitHub: `https://github.com/adrianpawlas/scraper-americaneagle`
2. Click on **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret** and add:

### Required Secrets:

- **Name:** `SUPABASE_URL`
  - **Value:** `https://yqawmzggcgpeyaaynrjk.supabase.co`

- **Name:** `SUPABASE_KEY`
  - **Value:** `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlxYXdtemdnY2dwZXlhYXlucmprIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc1NTAxMDkyNiwiZXhwIjoyMDcwNTg2OTI2fQ.XtLpxausFriraFJeX27ZzsdQsFv3uQKXBBggoz6P4D4`

## Workflow Features

### Automatic Schedule
- Runs every day at **midnight UTC** (00:00 UTC)
- To change the schedule, edit `.github/workflows/scrape.yml` and modify the cron expression

### Manual Trigger
- Go to **Actions** tab
- Select **"Scrape American Eagle Products"** workflow
- Click **"Run workflow"** button
- Click **"Run workflow"** to start

### Timeout
- The workflow has a **12-hour timeout** (720 minutes)
- If scraping takes longer, the workflow will be cancelled
- You can adjust this in `.github/workflows/scrape.yml` by changing `timeout-minutes: 720`

## Monitoring Runs

1. Go to **Actions** tab to see workflow runs
2. Click on a run to see detailed logs
3. Logs are also saved as artifacts for 7 days
4. Download logs from the **Artifacts** section after a run completes

## Troubleshooting

### Workflow fails immediately
- Check that secrets are set correctly
- Verify Supabase credentials are valid
- Check workflow logs for specific error messages

### Workflow times out
- The scraper might be processing too many products
- Consider adding more category URLs gradually
- Increase timeout if needed (max 6 hours for free tier, 12 hours for paid)

### Playwright installation fails
- This is usually handled automatically
- Check logs for specific browser installation errors

### Model download fails
- First run downloads ~500MB model
- Ensure GitHub Actions has sufficient time/resources
- Model is cached for subsequent runs

