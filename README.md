# VkusVill Sale Monitor

Sends a Telegram message when VkusVill posts 40%+ discounts. Runs 24/7 on Railway (free tier).

## Deploy to Railway (free, ~5 min)

### 1. Get your Telegram credentials

1. Open Telegram → search **@BotFather** → send `/newbot` → follow prompts → copy the **bot token**
2. Send any message to your new bot
3. Open `https://api.telegram.org/botYOUR_TOKEN/getUpdates` in a browser
4. Copy the `chat.id` number from the JSON response

### 2. Push to GitHub

```bash
git init
git add .
git commit -m "VkusVill monitor"
# Create a new repo on github.com, then:
git remote add origin https://github.com/YOUR_USERNAME/vkusvill-monitor.git
git push -u origin main
```

### 3. Deploy on Railway

1. Go to [railway.app](https://railway.app) → sign up free with GitHub
2. Click **New Project** → **Deploy from GitHub repo** → select your repo
3. Go to your service → **Variables** tab → add:

| Variable | Value |
|---|---|
| `TELEGRAM_TOKEN` | your bot token (e.g. `123456:ABCdef...`) |
| `TELEGRAM_CHAT_ID` | your chat ID (e.g. `123456789`) |
| `MIN_DISCOUNT` | `40` (or whatever threshold you want) |
| `CHECK_INTERVAL_MINUTES` | `15` (how often to check) |

4. Railway auto-deploys. Check the **Logs** tab — you should see "VkusVill monitor started!"
5. You'll also get a Telegram confirmation message.

## That's it!

The monitor runs 24/7. When a 40%+ sale appears, you get a Telegram message with the product names and direct links. When the sale ends, it resets so you'll be alerted again next time.
