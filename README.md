# 🦖 GODZILLA BOT v3.0.0 — ULTRA EDITION

The most powerful Telegram media downloader bot — now with database, admin panel, referrals, favorites, batch downloads, quality selector, and Discord integration.

**Developer:** Sxhd
**Community:** SHA COMMUNITY

---

## ✨ What's New in v3.0.0

- 🗄️ **PostgreSQL Database** — all user data persists
- 👨‍💼 **Admin System** — stats, broadcast, ban/unban, premium
- 🎬 **Quality Selector** — 360p / 720p / 1080p / Best
- 📦 **Batch Downloads** — send up to 5 links at once
- 🖼️ **Thumbnail Extractor** — grab video covers
- 📚 **Download History** — last 10 downloads per user
- ⭐ **Favorites System** — save links for later
- 🎁 **Referral Program** — +5 daily downloads per friend
- 📊 **Daily Limits** — 10 free / unlimited premium
- 🔔 **Discord Webhook** — real-time alerts to your server
- 🛠️ **Utility Tools** — QR code, URL shortener, translator
- 📡 **Multi-Platform** — YouTube, Instagram, TikTok, Twitter/X, Facebook, Pinterest, Reddit, SoundCloud

---

## 📌 All Commands

### 👤 User Commands
| Command | Description |
|---------|-------------|
| `/start` | Welcome + register |
| `/help` | Full command list |
| `/info` | Live bot stats |
| `/about` | About developer |
| `/ping` | Check speed |
| `/history` | Your last 10 downloads |
| `/favorites` | Saved links |
| `/fav <url>` | Save a link |
| `/unfav <id>` | Remove favorite |
| `/referral` | Your referral link |
| `/limit` | Daily usage |
| `/quality` | Set default quality |
| `/thumb <url>` | Get thumbnail |

### 🛠 Utility Commands
| Command | Description |
|---------|-------------|
| `/qr <text>` | Generate QR code |
| `/short <url>` | Shorten URL |
| `/tr <text>` | Quick translate |
| `/tr es <text>` | Translate to Spanish |

### 👨‍💼 Admin Commands
| Command | Description |
|---------|-------------|
| `/admin` | Admin help menu |
| `/stats` | Bot statistics |
| `/broadcast <msg>` | Message all users |
| `/ban <user_id>` | Ban user |
| `/unban <user_id>` | Unban user |
| `/logs` | Recent activity |
| `/premium <id> [on/off]` | Grant/revoke premium |

---

## 📂 Project Structure

```
godzilla_v3/
├── bot.py                          # Main entry point
├── config.py                       # Settings
├── requirements.txt                # Dependencies
├── .env.example                    # Env template
├── .gitignore
├── railway.json                    # Railway deploy config
├── nixpacks.toml                   # Installs ffmpeg, postgres libs
├── Procfile
├── database/
│   ├── __init__.py
│   ├── models.py                   # SQLAlchemy models
│   └── helpers.py                  # DB functions
├── handlers/
│   ├── __init__.py
│   ├── user_commands.py            # User-facing
│   ├── admin_commands.py           # Admin-only
│   ├── download_handler.py         # Downloads + callbacks
│   └── utility_commands.py         # QR, translate, shortener
└── utils/
    ├── __init__.py
    ├── downloader.py               # yt-dlp engine
    └── discord_webhook.py          # Discord alerts
```

---

## 🚀 Termux Setup (Local Testing)

### Step 1 — Install Termux
From **F-Droid**: https://f-droid.org/en/packages/com.termux/

### Step 2 — Install packages
```bash
pkg update && pkg upgrade -y
pkg install python ffmpeg git unzip nano postgresql libjpeg-turbo -y
```

### Step 3 — Enable storage
```bash
termux-setup-storage
```

### Step 4 — Extract the bot
```bash
cp ~/storage/downloads/godzilla_v3.zip ~/
cd ~ && unzip godzilla_v3.zip
cd godzilla_v3
```

### Step 5 — Install Python dependencies
```bash
pip install -r requirements.txt
```
⚠️ `psycopg2-binary` may fail on Termux. If so, use SQLite only (no change needed — default).

### Step 6 — Get your Telegram ID
Search **@userinfobot** on Telegram → send any message → it replies with your ID.

### Step 7 — Get bot token
Search **@BotFather** → `/newbot` → pick name & username → copy token.

### Step 8 — Set up `.env`
```bash
cp .env.example .env
nano .env
```
Fill in:
```
BOT_TOKEN=your_bot_token_here
ADMIN_IDS=your_telegram_id_here
DATABASE_URL=sqlite:///godzilla.db
DISCORD_WEBHOOK_URL=
GEMINI_API_KEY=
```
Save: `Ctrl+X` → `Y` → `Enter`

### Step 9 — Run!
```bash
python bot.py
```

You should see:
```
✅ Database initialized
✅ Command menu registered with Telegram
🦖 GODZILLA v3.0.0 is online!
```

---

## ☁️ Deploy to Railway.app (24/7 FREE Hosting)

### Step 1 — Push code to GitHub

```bash
cd ~/godzilla_v3
git init
git add .
git commit -m "GODZILLA v3.0.0 Ultra Edition"
git branch -M main
```

Create a **Private** repo on https://github.com/new named `GODZILLA`, then:
```bash
git remote add origin https://github.com/SxhdSha/GODZILLA.git
git push -u origin main
```

If Git asks for a password, use a **Personal Access Token**:
GitHub → Settings → Developer settings → Personal access tokens → Generate new token (classic) → check `repo` → Generate → use as password.

### Step 2 — Create Railway project

1. Go to https://railway.app → log in with GitHub
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your `GODZILLA` repo
4. Railway starts building — wait for first deploy (~3 min)

### Step 3 — Add PostgreSQL database

1. In your Railway project, click **+ New** (top right)
2. Select **Database** → **PostgreSQL**
3. Railway creates the DB and auto-connects it

Railway automatically injects a `DATABASE_URL` variable into your bot service. No manual config needed! ✨

### Step 4 — Link the database to your bot

1. Click your **bot service** (not the Postgres one)
2. Go to **Variables** tab
3. Click **+ New Variable** → **Add Reference**
4. Pick `DATABASE_URL` from the Postgres service
5. Railway adds it automatically

### Step 5 — Add your env variables

Still in the **Variables** tab of your bot service, add:

| Variable | Value |
|----------|-------|
| `BOT_TOKEN` | Your BotFather token |
| `ADMIN_IDS` | Your Telegram ID (get from @userinfobot) |
| `DISCORD_WEBHOOK_URL` | Discord webhook URL (optional) |
| `GEMINI_API_KEY` | Gemini API key (optional, for Phase 2) |

⚠️ Do NOT manually set `DATABASE_URL` — it's auto-linked from the Postgres service.

### Step 6 — Redeploy

Railway auto-redeploys after variable changes. Check **Deployments** → **View Logs** for:
```
🦖 GODZILLA v3.0.0 is online!
```

### Step 7 — Test on Telegram!

Send `/start`, `/help`, `/stats` — everything should work. 🎉

---

## 🔔 Setting Up Discord Webhook (Optional)

Get real-time alerts when users join, download, or errors occur.

1. Open your Discord server
2. Go to a channel → **⚙️ Edit Channel** → **Integrations**
3. Click **Webhooks** → **New Webhook**
4. Name it `GODZILLA Alerts`
5. Click **Copy Webhook URL**
6. Paste it as `DISCORD_WEBHOOK_URL` in your `.env` (local) or Railway variables (production)

You'll get embeds like:
- 👤 New user joined
- ✅ Download success
- ❌ Download failed
- 🛠 Admin actions (ban, broadcast, etc.)

---

## 🧪 Test Checklist

After deploying, test these in Telegram:

- [ ] `/start` — welcome message appears
- [ ] `/info` — shows live uptime & stats
- [ ] Send a YouTube link → buttons appear
- [ ] Click **🎬 Video** → quality buttons appear
- [ ] Click **720p** → video downloads
- [ ] `/history` — shows your download
- [ ] `/fav <url>` then `/favorites` — saves & lists
- [ ] `/referral` — shows your referral link
- [ ] `/limit` — shows daily usage bar
- [ ] `/qr hello` — sends a QR code image
- [ ] `/tr es hello world` — translates to Spanish
- [ ] `/stats` (admin) — shows bot statistics
- [ ] `/broadcast Hello!` (admin) — messages all users

---

## 🐛 Troubleshooting

**❌ `BOT_TOKEN not set`**
Check `.env` file has `BOT_TOKEN=your_actual_token` (no quotes, no spaces).

**❌ `psycopg2` install fails on Termux**
Use SQLite for local testing. Change `.env`:
```
DATABASE_URL=sqlite:///godzilla.db
```
PostgreSQL works fine on Railway.

**❌ Admin commands say "Admin only"**
You didn't add your Telegram ID to `ADMIN_IDS`. Get it from @userinfobot and add to `.env` or Railway variables.

**❌ Downloads fail on Railway**
Check logs for the actual error. Common ones:
- Instagram blocks Railway IPs sometimes
- File over 50MB → use lower quality
- ffmpeg missing → verify `nixpacks.toml` is in the repo

**❌ Database error on Railway**
Make sure you:
1. Created the PostgreSQL service
2. Added a `DATABASE_URL` **reference** variable (not plain text)

**❌ Bot doesn't respond after deploy**
- Check Railway logs
- Verify token is correct
- Try `drop_pending_updates=True` is in `bot.py` (already set)

---

## 🔐 Security

- ✅ Keep `.env` in `.gitignore` (already done)
- ✅ Use **Private** GitHub repo
- ✅ Never share your bot token or Gemini key
- ✅ Rotate token via @BotFather → `/revoke` if leaked
- ✅ Admin IDs should be people you fully trust — they can broadcast to all users

---

## 💰 Railway Free Tier Usage

- Railway gives **$5 free credit/month**
- Bot alone uses ~$2/month if running 24/7
- Bot + PostgreSQL uses ~$3-4/month
- Hobby Plan ($5/month) = unlimited if you go over

**Tips to save credits:**
- Don't enable high-CPU features
- Let Railway sleep your service (auto after 1hr idle)
- Monitor usage in **Settings → Usage**

---

## 🗺️ Roadmap — Phase 2 (Coming Soon)

- 🤖 **AI Features** — `/ai`, `/summarize`, `/transcribe` (Gemini)
- 🌐 **Web Admin Panel** — Flask dashboard with login
- 📊 **Live Charts** — download stats over time
- 🎨 **Media Tools** — trim, gif, compress
- 📧 **Email login** for web panel

Just say "Continue to Phase 2" whenever you're ready!

---

## 📜 Credits

- 💻 **Developer:** @Dev-Sahad
- 🏠 **Community:** SHA COMMUNITY
- 🧠 **AI Assistance:** Anthropic Claude
- 🔧 **Libraries:** python-telegram-bot, yt-dlp, SQLAlchemy, aiohttp
- ☁️ **Hosting:** Railway.app

---

_🦖 GODZILLA v3.0.0 — King of Bots_
_Always Online. Always Ready._
