# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important Rules

**NEVER CREATE GIT COMMITS** - The user manages all git operations. Do not run `git commit`, `git add`, or any git commands that modify the repository state. Only perform code changes and testing.

**ALWAYS ASK BEFORE CREATING DOCUMENTATION** - Before creating any text documents (README.md, .txt, .md files, documentation), always ask the user for permission first. Only create documentation if explicitly requested.

## Project Overview

FootageHub is a production Telegram bot that downloads media from Envato Elements, Freepik, and Motion Array, with WebPay payment integration, subscription management, and a referral system. Built with Python 3.11, aiogram 3.x, SQLAlchemy 2.x, and Playwright for browser automation.

## Development Commands

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
python -m playwright install chromium

# Run bot
python main.py
```

### Docker
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f bot

# Execute in container
docker-compose exec bot python envato_utils/test_env.py
```

### Database Migrations
```bash
# Run migrations (auto-executed on startup via db/base.py:run_migrations)
python -c "from db.base import run_migrations; import asyncio; asyncio.run(run_migrations())"

# Create new migration
alembic revision --autogenerate -m "description"
```

### Testing
```bash
# Test Envato downloader
python envato_utils/test_env.py

# Test Freepik downloader
python freepik_utils/freepik.py

# Test Motion Array downloader
python test/test_motion.py

# Test LinkProcessor (queue-based worker pool)
python test/test_link_processor.py

# WebPay integration test
python test/test_webpay.py

# Generate WebPay auth token
python test/get_webpay_token.py
```

### Cookie Management
```bash
# Convert exported cookies to Playwright format
python freepik_utils/convert_cookies.py
python envato_utils/convert_cookies.py
python motion_utils/convert_cookies.py

# Save cookies interactively (login in browser)
python envato_utils/cookie_save.py envato 1
python envato_utils/cookie_save.py freepik 1
python envato_utils/cookie_save.py motion 1

# Check authentication status
python freepik_utils/check_auth.py
python freepik_utils/check_cookies.py
```

## Architecture

### Core Components

**1. Telegram Bot (aiogram 3.x)**
- Entry point: `main.py` - orchestrates bot, scheduler, and FastAPI webhook server
- Handlers in `bot/handlers/` - each file manages specific command flows
- FSM states in `bot/state.py` - conversation flow management
- Global services container: `bot/services.py` (holds shared semaphores, LinkProcessor)

**2. Database Layer (SQLAlchemy 2.x + asyncpg)**
- Models: `db/models.py` - User, Media, Download, Payment, Subscription, ReferralReward
- CRUD: `db/*_crud.py` - async operations for each model
- Session factory: `db/session.py`
- Auto-migration: `db/base.py:run_migrations()` runs on startup

**3. Download System (Playwright + Queue Architecture)**
- **LinkProcessor** (`envato_utils/test_env.py`): Queue-based worker pool (5 workers)
  - Handles Envato, Freepik, and Motion Array downloads concurrently
  - Returns results via asyncio Futures
  - Restarts browsers every 50 requests (memory leak prevention)

- **EnvatoDownloader** (`envato_utils/envato_playwright.py`):
  - CDP (Chrome DevTools Protocol) for download URL interception
  - Cookie rotation across multiple accounts (`envato_cookies_1.json`, `envato_cookies_2.json`, etc.)
  - Supports both old (elements.envato.com) and new (app.envato.com) site formats

- **FreepikDownloader** (`freepik_utils/freepik.py`):
  - Requires Xvfb virtual display on servers (Freepik blocks headless browsers)
  - Cookie rotation with index tracking
  - URL interception for direct download links

- **MotionDownloader** (`motion_utils/motion.py`):
  - CDP network interception for `/download/direct` API endpoint
  - Cookie rotation across multiple accounts (`motion_cookies_1.json`, `motion_cookies_2.json`, etc.)
  - Stealth mode: disables `navigator.webdriver`, adds `window.chrome` object
  - Automatic button click detection (finds first visible `span:has-text('Download')`)
  - Returns direct download URL from JSON response: `data["downloadUrls"][0]`

**4. Payment Integration**
- **WebPay API** (`bot/webpay_utils.py`):
  - Automatic token refresh via username/password
  - RUB to BYN conversion (rate configured in code: ~0.033)
  - SHA1 signature for payment creation, MD5 for webhook verification
  - Two separate keys: `WEBPAY_SECRET_KEY` (password for auth) and `WEBPAY_SIGNING_KEY` (for signatures)

- **Payment Webhooks** (`bot/webhook/webpay.py`, `bot/webhook/cryptobot.py`):
  - FastAPI server runs parallel to bot (`bot/webhook/server_start.py`)
  - Validates signatures, creates subscriptions on successful payment
  - Order ID format: `USER_{user_id}_{plan_key}_{uuid}` (e.g., `USER_559268908_monthly_150_fbec74b9`)

**5. Scheduled Tasks** (`bot/schedule_tasks.py` - APScheduler)
- **03:00 UTC**: Daily credit allocation (3 credits to all users, 30 to DAILY_30 subscribers)
- **03:05 UTC**: Process MONTHLY_150 subscriptions (grant remaining credits, deactivate if exhausted)
- **03:10 UTC**: Check and deactivate expired subscriptions
- **Every 4 hours**: Database backup via pg_dump
- **Every 2 hours**: Playwright cache cleanup

### Key Patterns

**Async-First Design:**
- All code uses async/await (asyncio)
- SQLAlchemy AsyncSession for database
- Playwright async API
- APScheduler AsyncIOScheduler

**Subscription System:**
- Types: MONTHLY_50 (Lite - 50 downloads/month), MONTHLY_150 (Standard - 150 downloads/month), MONTHLY_400 (Pro - 400 downloads/month), DAILY_30 (30/day), UNLIMITED, CUSTOM
- Service scopes: ENVATO, FREEPIK, MOTION_ARRAY, ALL
- Usage tracked per subscription (total and daily counters)
- Automatic deactivation when limits exhausted or expiration date reached
- See `docs/SUBSCRIPTIONS_AND_REFERRALS.md` for detailed logic

**Referral Program:**
- Each user has unique `referral_code` (generated on first user creation)
- ReferralReward table tracks referrer → referred relationships
- Rewards have statuses: PENDING (awaiting conditions) → COMPLETED (credits granted)
- Typical flow: User A invites User B → Reward created as PENDING → User B makes purchase → Reward marked COMPLETED, credits given to User A

**Cookie Rotation:**
- Multiple cookie files per service (e.g., `envato_cookies_1.json`, `envato_cookies_2.json`)
- Index file tracks current position (`cookie_index.txt`)
- Automatic round-robin rotation to distribute rate limiting
- Falls back to legacy `envato_cookies.json` if no numbered files exist

**Error Handling:**
- Custom logger in `freepik_utils/logger.py` for centralized error reporting
- Screenshots saved on download failures (`debug_screenshots/`)
- Graceful fallback when cookies expire or providers change site structure

## Important Implementation Details

### WebPay Payment Flow
1. User clicks subscription button → `bot/handlers/payment.py`
2. Creates Payment record in database with status "pending"
3. Calls `webpay_api.create_invoice()` with order_id format: `USER_{user_id}_{plan_key}_{uuid}`
4. Returns payment URL to user
5. User pays → WebPay sends webhook to `/webpay/webhook`
6. Webhook validates signature (MD5 without secret_key for notifications)
7. Extracts user_id and plan_key from order_id: `parts = order_id.split('_')` → `plan_key = "_".join(parts[2:-1])`
8. Creates Subscription record linked to Payment
9. Updates Payment status to "success"
10. Notifies user via Telegram

**Critical WebPay Signature Details:**
- **Payment creation**: Uses SHA1 with `WEBPAY_SIGNING_KEY` included
  - Format: `seed + merchant_id + order_num + test + currency_id + total + signing_key`
- **Webhook verification**: Uses MD5 WITH signing_key at the end
  - Format: `batch_timestamp + currency_id + amount + payment_method + order_id + site_order_id + transaction_id + payment_type + rrn + signing_key`
  - **ВАЖНО**: В webhook используются ОБА поля: `order_id` (внутренний ID WebPay) и `site_order_id` (наш order_id)
- Amount formatting: Always use 2 decimal places (e.g., "19.47")
- **Keys**: `WEBPAY_SECRET_KEY` - password for auth, `WEBPAY_SIGNING_KEY` - for signatures

### Subscription Eligibility Check
Before allowing download (in `bot/handlers/download.py`):
1. Check if user has active subscription for requested service
2. Call `check_download_limit(session, subscription)` from `db/subscription_crud.py`
3. Checks:
   - Subscription is active
   - Not expired (end_date)
   - Daily limit not exceeded (if applicable)
   - Total limit not exceeded (if applicable)
4. If all checks pass, download proceeds
5. After successful download, call `increment_download_count(session, subscription_id)`

### LinkProcessor Usage
```python
# In handlers (e.g., bot/handlers/download.py)
from bot.services import BotServices

# Get shared LinkProcessor instance
link_processor = BotServices.link_processor

# Submit download job (returns Future)
future = link_processor.submit_link(url, is_freepik=True)

# Await result
result = await future  # Returns download URL or None
```

### Freepik Headless Issue
Freepik blocks headless browsers, so on production servers:
- Xvfb virtual display must be running on `:99`
- `DISPLAY=:99` environment variable required in container
- See `SERVER_SETUP.md` for Xvfb systemd service setup
- Dockerfile includes Xvfb client configuration

### Motion Array Implementation Details
Motion Array uses API-based download system with anti-bot protection:
- **API Endpoint**: `/proxy/download/v1/download/direct` returns JSON with `downloadUrls` array
- **Stealth Mode**: Required to bypass Cloudflare protection
  - `--disable-blink-features=AutomationControlled` browser arg
  - `Object.defineProperty(navigator, 'webdriver', {get: () => undefined})`
  - `window.chrome = {runtime: {}}` to mimic real Chrome
- **Button Detection**: Finds first visible `span:has-text('Download')` element
  - Multiple buttons may exist (fake/hidden ones), uses `is_visible()` check
  - Clicks with `delay=0` for fastest response
- **Network Interception**: CDP monitors all responses for `/download/direct`
  - Parses JSON: `data.get("downloadUrls")[0]` contains signed CDN URL
  - Timeout: 5 seconds (50 checks × 0.1s intervals)
- **Timeouts**: Optimized for speed (similar to Envato)
  - `goto`: 30s with `domcontentloaded` event
  - `networkidle`: 1.5s (not critical, can fail)
  - Post-load wait: 1s before button search

### Database Session Management
Always use async context manager:
```python
from db.session import get_session

async with get_session() as session:
    # Do work
    await some_crud_operation(session, ...)
    # Auto-commit on success, rollback on exception
```

## Configuration Files

### Centralized Configuration (bot/config.py)
All application configuration is centralized in `bot/config.py`. This includes:
- Environment variables loading
- File paths (PRICE_LIST_PATH, BOT_DIR, HANDLERS_DIR)
- Channel settings (CHANNEL_ID, CHANNEL_BONUS_CREDITS)
- WebPay and CryptoBot credentials
- Limits and timeouts (MAX_CONCURRENT_DOWNLOADS, BROWSER_RESTART_AFTER, DOWNLOAD_TIMEOUT_SECONDS)
- Credits and bonuses (DAILY_FREE_CREDITS, CHANNEL_BONUS_CREDITS)
- Browser settings (BROWSER_VIEWPORT_WIDTH, BROWSER_VIEWPORT_HEIGHT)

**Usage pattern:**
```python
from bot.config import PRICE_LIST_PATH, CHANNEL_ID, CHANNEL_BONUS_CREDITS
from bot.config import MAX_CONCURRENT_DOWNLOADS, BROWSER_RESTART_AFTER
from bot.config import DAILY_FREE_CREDITS
```

### Environment Variables (.env)
```env
BOT_TOKEN=                    # Telegram bot token
DATABASE_URL=                 # PostgreSQL connection string
ADMIN=                        # Admin Telegram user ID

# Channel configuration (optional, defaults in config.py)
CHANNEL_ID=@footagehub_channel           # Channel username or ID
CHANNEL_BONUS_CREDITS=2                  # Credits for channel subscription

# WebPay (Belarusian payment processor)
WEBPAY_RESOURCE_ID=           # Merchant ID
WEBPAY_API_KEY=               # Username for token refresh
WEBPAY_SECRET_KEY=            # Password for token refresh
WEBPAY_SIGNING_KEY=           # Secret key for payment signatures
WEBPAY_AUTH_TOKEN=            # Bearer token (auto-refreshed)
WEBPAY_SANDBOX=false          # true for test mode, false for production

# CryptoBot (alternative payment)
CRYPTO_BOT_API_KEY=
CRYPTO_BOT_WEBHOOK=
```

### Cookie Files Structure
Download providers use numbered cookie files for rotation:
```
envato_utils/
  ├── envato_cookies_1.json
  ├── envato_cookies_2.json
  ├── envato_cookies_3.json
  └── cookie_index.txt           # Tracks current rotation position

freepik_utils/
  ├── freepik_cookies_1.json
  └── cookie_index.txt

motion_utils/
  ├── motion_cookies_1.json
  ├── motion_cookies_2.json
  └── motion_cookie_index.txt
```

Fallback: If no numbered files exist, uses legacy single file (`envato_cookies.json`, `freepik_cookies.json`, `motion_cookies.json`)

### Subscription Plans (bot/handlers/prices_list.json)
```json
{
  "subscription_plans": {
    "monthly_50": {
      "name": "Lite",
      "price": 399.00,              // RUB (converted to BYN in API)
      "period_days": 30,
      "total_limit": 50,
      "daily_limit": null,
      "subscription_type": "MONTHLY_50"
    },
    "monthly_150": {
      "name": "Standard",
      "price": 899.00,
      "period_days": 30,
      "total_limit": 150,
      "daily_limit": null,
      "subscription_type": "MONTHLY_150"
    },
    "monthly_400": {
      "name": "Pro",
      "price": 1790.00,
      "period_days": 30,
      "total_limit": 400,
      "daily_limit": null,
      "subscription_type": "MONTHLY_400"
    }
  }
}
```

## Common Development Tasks

### Adding New Download Provider
1. Create `provider_utils/provider_playwright.py` similar to `envato_playwright.py` or `motion_utils/motion.py`
2. Implement cookie rotation and URL interception
3. Create converter: `provider_utils/convert_cookies.py` for cookie export from browser extensions
4. Add test script: `test/test_provider.py` for standalone testing
5. Add handler in `bot/handlers/download.py`
6. Add FSM state in `bot/state.py`
7. Update LinkProcessor in `envato_utils/test_env.py` to support new provider
8. Add service type to `ServiceType` enum in `db/models.py`

**Example**: Motion Array implementation (`motion_utils/motion.py`) demonstrates:
- CDP network interception for API endpoints
- Stealth mode configuration
- Cookie rotation with index tracking
- Automatic visible button detection
- Clean class-based structure with `__aenter__`/`__aexit__`
- Statistics tracking (success/fail counts, timing)

### Modifying Payment Plans
1. Update `bot/handlers/prices_list.json` with new plan
2. Add subscription type to `SubscriptionType` enum in `db/models.py`
3. Create Alembic migration if enum changed
4. Update handlers in `bot/handlers/payment.py` to offer new plan
5. Update webhook parsing in `bot/webhook/webpay.py` if plan_key format changes

### Debugging Download Issues
1. Check browser screenshots in `envato_utils/debug_screenshots/`, `freepik_utils/debug_screenshots/`, or `motion_utils/debug_screenshots/`
2. Run standalone tests: 
   - `python envato_utils/test_env.py`
   - `python freepik_utils/freepik.py`
   - `python test/test_motion.py`
3. Verify cookies are valid: 
   - `python freepik_utils/check_auth.py`
   - For Motion Array: open browser with `python envato_utils/cookie_save.py motion 1` and verify login
4. Check if site selectors changed (common with Envato/Freepik/Motion Array redesigns)
5. For Freepik: ensure Xvfb is running and `DISPLAY=:99` is set
6. For Motion Array: 
   - Verify `/download/direct` endpoint is being intercepted
   - Check that button selector `span:has-text('Download')` finds visible elements
   - Ensure stealth mode is working (no `navigator.webdriver` detection)

### Updating WebPay Integration
- Payment signature uses `WEBPAY_SIGNING_KEY`, not `WEBPAY_SECRET_KEY`
- Webhook signature is MD5, payment creation is SHA1
- Test with sandbox first: `WEBPAY_SANDBOX=true` in .env
- Use `test/get_webpay_token.py` to manually refresh auth token if needed

## Project-Specific Conventions

- All database operations use async CRUD functions from `db/*_crud.py`
- Never use raw SQL queries; use SQLAlchemy ORM
- Download handlers use LinkProcessor (global queue), not direct Playwright calls
- Payment webhooks must validate signatures before processing
- User roles: `user` (default), `admin`, `manager`, `partner` (affects command access)
- Subscription types are case-sensitive enums (e.g., `MONTHLY_150`, not `monthly_150`)
- Order IDs for payments always follow format: `USER_{user_id}_{plan_key}_{uuid}`
- Currency displayed to users: RUB; currency sent to WebPay: BYN (conversion factor in code)
- **Configuration centralization**: Always import constants from `bot/config.py` (PRICE_LIST_PATH, CHANNEL_ID, etc.), never hardcode paths or values in handlers
- **Download providers**: Use consistent structure across providers (Envato, Freepik, Motion Array):
  - Class-based with `__aenter__`/`__aexit__` for resource management
  - Cookie rotation with `get_next_cookie_file()` and index tracking
  - Statistics tracking (`success_count`, `fail_count`, `total_time`)
  - Main API function format: `get_{provider}_direct_download_url(url)`
  - Emojis for output: 🚀 (start), ✅ (success), ❌ (failure), ⚠️ (warning), 🔄 (rotation), ⏱️ (time), 📊 (statistics)

## Troubleshooting

**"Cannot open display :99"**
- Xvfb not running or `DISPLAY` env var not set
- Check: `sudo systemctl status xvfb`
- Fix: `sudo systemctl start xvfb` and ensure `DISPLAY=:99` in docker-compose.yml

**"Playwright browser not found"**
- Browsers not installed in container
- Fix: `docker-compose exec bot python -m playwright install chromium`

**WebPay signature errors**
- Verify using correct key: `WEBPAY_SIGNING_KEY` for payments, not `WEBPAY_SECRET_KEY`
- Check amount formatting (always 2 decimals: "19.47")
- Webhook signature excludes secret_key (uses MD5, not SHA1)

**Download fails with "button not found"**
- Site redesign changed selectors
- Check current selector in `envato_playwright.py`, `freepik.py`, or `motion.py`
- Update to universal selector (e.g., `button:has-text('Скачать')`, `button:has-text('Download')`, or `span:has-text('Download')`)
- For Motion Array: use `span:has-text('Download')` as button contains icon + span

**Subscription not created after payment**
- Check webhook logs for signature validation errors
- Verify order_id parsing: `plan_key = "_".join(parts[2:-1])`
- Ensure plan_key exists in `prices_list.json`