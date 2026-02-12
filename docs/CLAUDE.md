# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Important Rules

**NEVER CREATE GIT COMMITS** - The user manages all git operations. Do not run `git commit`, `git add`, or any git commands that modify the repository state. Only perform code changes and testing.

**ALWAYS ASK BEFORE CREATING DOCUMENTATION** - Before creating any text documents (README.md, .txt, .md files, documentation), always ask the user for permission first. Only create documentation if explicitly requested.

## TODO: Technical Debt

### Pre-commit Hooks & Type Safety
**Status**: mypy temporarily disabled in `.pre-commit-config.yaml`

**Issue**: 383 type errors found across 59 files when mypy was enabled.

**Tasks**:
1. Re-enable mypy in `.pre-commit-config.yaml` by uncommenting lines 46-58
2. Fix type errors systematically:
   - AsyncSession iteration issues (`has no attribute "__aiter__"`)
   - Column type mismatches (passing `Column[int]` instead of `int`)
   - Missing type annotations
   - Incompatible assignments
   - Missing return statements
   - Unreachable code warnings
3. Add missing stub packages for proper type checking
4. Ensure all handlers, services, and repositories have proper type hints

**Priority**: Medium - Code works but lacks type safety guarantees

**Files with most errors**:
- `media_bot/handlers/referral.py` (10 errors)
- `media_bot/handlers/channel_check.py` (5 errors)
- `media_bot/handlers/manager.py` (8 errors)
- `media_bot/handlers/download/*.py` (multiple files, ~40 errors total)

**Common patterns to fix**:
- Use `user.id` instead of `user_id` column when passing to repository methods
- Add proper type annotations to variables (e.g., `rewards_by_type: Dict[str, int] = {}`)
- Fix AsyncSession usage in async context managers
- Resolve unreachable code after return statements

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

**Perpetual Credits System:**
- Pay-as-you-go credits that never expire (несгораемые загрузки)
- Purchase 3-90 credits at 30 RUB per credit
- No database migration needed - uses existing `User.credits` field
- Integrated with WebPay payment system
- Payment flow uses FSM state: `PerpetualCreditsFlow.waiting_for_quantity`
- Order ID format: `USER_{user_id}_perpetual_credits_{quantity}_{uuid}`
- plan_key format: `perpetual_credits_{quantity}` (e.g., `perpetual_credits_10`)
- After successful payment, credits are added directly to user's balance
- Users with active subscriptions can still purchase perpetual credits
- Implementation in `media_bot/handlers/perpetual_credits.py`

**i18n (Internationalization):**
- Supported languages: `ru` (default), `en`
- Language stored in `User.username` field (DB). Not a real username — repurposed for lang code
- Priority: `User.username` (DB) → Telegram `language_code[:2]` → `"ru"` (fallback)
- All user-facing strings in `media_bot/handlers/messages.py`
- Russian texts — module-level constants (e.g., `MAIN_MENU = "..."`), English — `_TRANSLATIONS["en"]` dict
- `msg(key, lang)` function returns text: if `lang == "ru"` → `globals()[key]`, else → `_TRANSLATIONS[lang][key]` with ru fallback
- `I18nMiddleware` (`media_bot/middlewares/i18n.py`) reads `user.username`, injects `data["lang"]`
- All handlers accept `lang: str = "ru"` parameter (injected by middleware)
- `/lang` command (`media_bot/handlers/lang.py`) — inline buttons to switch language, saves to `user.username`
- Adding new language: add code to `SUPPORTED_LANGUAGES`, add `_TRANSLATIONS["xx"]` dict, add button in `lang.py`
- When creating new user in `/start`: `username=lang` is set from middleware-detected language
- **Usage in handlers**: `msg("CONSTANT_NAME", lang)` instead of bare `CONSTANT_NAME`; for `.format()`: `msg("KEY", lang).format(...)`
- `REFERRAL_TRIGGER_NAMES` is a dict, not a string — `msg()` returns the dict for the right language

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

**For Subscriptions:**
1. User clicks subscription button → `media_bot/handlers/payment.py`
2. Creates Payment record in database with status "pending"
3. Calls `webpay_api.create_invoice()` with order_id format: `USER_{user_id}_{plan_key}_{uuid}`
4. Returns payment URL to user
5. User pays → WebPay sends webhook to `/webpay/webhook`
6. Webhook validates signature (MD5 without secret_key for notifications)
7. Extracts user_id and plan_key from order_id: `parts = order_id.split('_')` → `plan_key = "_".join(parts[2:-1])`
8. Creates Subscription record linked to Payment
9. Updates Payment status to "success"
10. Notifies user via Telegram

**For Perpetual Credits:**
1. User clicks "💎 Купить поштучно" button → `media_bot/handlers/perpetual_credits.py`
2. Bot sets FSM state `PerpetualCreditsFlow.waiting_for_quantity`
3. User sends message with quantity (validated: 3-90)
4. Creates Payment record with `plan_key = "perpetual_credits_{quantity}"`
5. Creates WebPay invoice with order_id: `USER_{user_id}_perpetual_credits_{quantity}_{uuid}`
6. User pays → Webhook receives notification
7. Webhook detects `plan_key.startswith("perpetual_credits_")`
8. Calls `handle_perpetual_credits_purchase()` instead of subscription creation
9. Adds credits directly to `user.credits += quantity`
10. Marks payment as successful, sends notification

**Critical WebPay Signature Details:**
- **Payment creation**: Uses SHA1 with `WEBPAY_SIGNING_KEY` included
  - Format: `seed + merchant_id + order_num + test + currency_id + total + signing_key`
- **Webhook verification**: Uses MD5 WITH signing_key at the end
  - Format: `batch_timestamp + currency_id + amount + payment_method + order_id + site_order_id + transaction_id + payment_type + rrn + signing_key`
  - **ВАЖНО**: В webhook используются ОБА поля: `order_id` (внутренний ID WebPay) и `site_order_id` (наш order_id)
- Amount formatting: Always use 2 decimal places (e.g., "19.47")
- **Keys**: `WEBPAY_SECRET_KEY` - password for auth, `WEBPAY_SIGNING_KEY` - for signatures

### Payment Menu Logic (media_bot/handlers/payment.py)

The `send_price_menu()` function has **two distinct branches** based on subscription status:

**Branch 1: User has active subscription**
- Shows message: "✅ У вас активная подписка!"
- Displays subscription details (type, end date, available credits)
- Shows **only** "💎 Купить поштучно" button
- Prevents purchasing second subscription while first is active
- Users can still buy perpetual credits to supplement their subscription

**Branch 2: User has no active subscription**
- Shows all subscription tier buttons:
  - `Lite · 50 шт · 399 ₽/мес`
  - `Standard · 150 шт · 899 ₽/мес ⭐️`
  - `Pro · 400 шт · 1790 ₽/мес`
- Separator button (non-clickable): `─────────── или ───────────`
  - Uses `callback_data='separator_ignore'` to prevent interaction
- Shows "💎 Купить поштучно" button at bottom
- Menu message displays cost-per-file calculations (~8₽, ~6₽, ~4.5₽)

**Implementation pattern:**
```python
async def send_price_menu(message_or_callback, lang: str = "ru"):
    user_id = message_or_callback.from_user.id

    # Check active subscription
    async for session in get_session():
        subscription_repo = SubscriptionRepository(session)
        active_subscription = await subscription_repo.get_active_by_user_id(user.id)

        if active_subscription:
            # Branch 1: Show only perpetual credits option
            # All messages via msg("KEY", lang)
            return

    # Branch 2: Show all subscription tiers + perpetual credits
```

### Subscription Eligibility Check
Before allowing download (in `media_bot/handlers/download.py`):
1. Check if user has active subscription for requested service
2. Call `check_download_limit(session, subscription)` from `shared/db/repositories.py`
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

### Subscription Plans (media_bot/handlers/prices_list.json)
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
  },
  "perpetual_credits": {
    "price_per_credit": 30,         // RUB per credit
    "minimum_quantity": 3,          // Min purchase: 90 RUB
    "maximum_quantity": 90          // Max purchase: 2700 RUB
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

### Purchasing Perpetual Credits (FSM Flow)

The perpetual credits purchase uses FSM (Finite State Machine) for user interaction:

**Handler**: `media_bot/handlers/perpetual_credits.py`
**State**: `PerpetualCreditsFlow.waiting_for_quantity` (defined in `media_bot/state.py`)

**Flow:**
1. User clicks "💎 Купить поштучно" → `show_perpetual_credits_menu()`
2. Bot displays prompt with pricing info, sets FSM state
3. User sends message with quantity (e.g., "10")
4. `process_quantity_input()` validates via `validate_quantity_input()`:
   - Checks if integer
   - Min: 3 credits (90 RUB)
   - Max: 90 credits (2700 RUB)
5. If invalid → sends error message, keeps FSM state active
6. If valid → creates WebPay invoice, saves Payment record
7. Shows confirmation message with payment button
8. Clears FSM state with `await state.clear()`
9. After payment → webhook calls `handle_perpetual_credits_purchase()`
10. Credits added: `user.credits += quantity`
11. Notification sent to user

**Key validation function:**
```python
def validate_quantity_input(text: str) -> Tuple[bool, int, str]:
    """Returns (is_valid, quantity, error_message)"""
    config = load_perpetual_credits_config()
    try:
        quantity = int(text.strip())
    except ValueError:
        return False, 0, PERPETUAL_CREDITS_INVALID_INPUT

    if quantity < config["minimum_quantity"]:
        return False, quantity, PERPETUAL_CREDITS_INVALID_QUANTITY

    if quantity > config["maximum_quantity"]:
        return False, quantity, f"❌ Максимум {config['maximum_quantity']} загрузок"

    return True, quantity, ""
```

**Configuration loading:**
```python
def load_perpetual_credits_config():
    """Loads from media_bot/handlers/prices_list.json"""
    from media_bot.config import PRICE_LIST_PATH
    with open(PRICE_LIST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
        config = data.get("perpetual_credits", {})
        return {
            "price_per_credit": config.get("price_per_credit", 30),
            "minimum_quantity": config.get("minimum_quantity", 3),
            "maximum_quantity": config.get("maximum_quantity", 90),
        }
```

### Modifying Payment Plans

**For Subscription Plans:**
1. Update `media_bot/handlers/prices_list.json` with new plan
2. Add subscription type to `SubscriptionType` enum in `shared/db/models.py`
3. Create Alembic migration if enum changed
4. Update handlers in `media_bot/handlers/payment.py` to offer new plan
5. Update message templates in `media_bot/handlers/messages.py` (Russian constant + `_TRANSLATIONS["en"]`)
6. Update webhook parsing in `media_bot/webhook/webpay.py` if plan_key format changes

**For Perpetual Credits:**
1. Update `media_bot/handlers/prices_list.json` → `perpetual_credits` section
2. Change `price_per_credit`, `minimum_quantity`, or `maximum_quantity`
3. Update message templates in `media_bot/handlers/messages.py` (Russian constant + `_TRANSLATIONS["en"]`)
4. No database migration needed - uses existing `User.credits` field

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

**Webhook Detection for Perpetual Credits** (`media_bot/webhook/webpay.py`):
```python
# After extracting plan_key from order_id
if plan_key and plan_key.startswith("perpetual_credits_"):
    # Handle perpetual credits purchase (no subscription creation)
    await handle_perpetual_credits_purchase(session, user_id, order_id, plan_key)
    return Response(content='{"code": 200}', status_code=200)

# Otherwise, handle subscription creation
```

**Handler function:**
```python
async def handle_perpetual_credits_purchase(session, user_id, order_id, plan_key):
    """
    Processes perpetual credits payment without creating subscription.

    Args:
        plan_key: Format "perpetual_credits_{quantity}" (e.g., "perpetual_credits_10")
    """
    # Extract quantity from plan_key
    quantity = int(plan_key.split("_")[-1])

    # Get user and payment
    user = await user_repo.get_by_telegram_id(user_id)
    payment = await payment_repo.get_by_invoice_id(order_id)

    # Prevent duplicate processing
    if payment.status == "success":
        logger.info(f"✅ [WEBPAY] Payment {order_id} already processed")
        return

    # Add credits directly to user
    user.credits += quantity
    await session.commit()

    # Mark payment as successful
    await payment_repo.mark_success(order_id)

    # Send notification
    message = PERPETUAL_CREDITS_PURCHASED.format(
        quantity=quantity,
        total_credits=user.credits
    )
    await BotServices.bot.send_message(chat_id=user_id, text=message, ...)
```

## Project-Specific Conventions

- All database operations use async CRUD functions from `shared/db/repositories.py`
- Never use raw SQL queries; use SQLAlchemy ORM
- Download handlers use LinkProcessor (global queue), not direct Playwright calls
- Payment webhooks must validate signatures before processing
- User roles: `user` (default), `admin`, `manager`, `partner` (affects command access)
- Subscription types are case-sensitive enums (e.g., `MONTHLY_150`, not `monthly_150`)
- Order IDs for payments always follow format: `USER_{user_id}_{plan_key}_{uuid}`
- Currency displayed to users: RUB; currency sent to WebPay: BYN (conversion factor in code)
- **Configuration centralization**: Always import constants from `media_bot/config.py` (PRICE_LIST_PATH, CHANNEL_ID, etc.), never hardcode paths or values in handlers
- **i18n**: Never use bare message constants in handlers. Always use `msg("KEY", lang)`. All handler functions must accept `lang: str = "ru"` parameter. New user-facing strings must be added both as Russian constant and in `_TRANSLATIONS["en"]`. `User.username` field stores language code (`"ru"` / `"en"`), not the actual Telegram username
- **Perpetual Credits System**:
  - plan_key format: `perpetual_credits_{quantity}` (e.g., `perpetual_credits_10`)
  - No separate database table - uses `User.credits` field
  - Validation: 3-90 credits per purchase
  - Price: 30 RUB per credit (configured in `prices_list.json`)
  - FSM state: `PerpetualCreditsFlow.waiting_for_quantity`
  - Webhook detects pattern with `plan_key.startswith("perpetual_credits_")`
  - Credits added directly: `user.credits += quantity` (no subscription created)
  - Users with active subscriptions can still buy perpetual credits
- **Payment Menu Logic**:
  - Check active subscription first in `send_price_menu()`
  - If active subscription exists: show only "💎 Купить поштучно" button
  - If no subscription: show all subscription tiers + perpetual credits button
  - Separator button uses `callback_data='separator_ignore'` (non-clickable)
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

**Perpetual credits not added after payment**
- Check if webhook detects `plan_key.startswith("perpetual_credits_")`
- Verify `handle_perpetual_credits_purchase()` is called instead of subscription creation
- Check payment status - if already "success", it won't process again (prevents duplicates)
- Verify quantity extraction: `quantity = int(plan_key.split("_")[-1])`
- Check `User.credits` was incremented: `user.credits += quantity`
- Ensure notification message uses `PERPETUAL_CREDITS_PURCHASED` template
