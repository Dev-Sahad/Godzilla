# 🌐 Admin Web Panel Setup Guide

Full control panel for GODZILLA — manage plans, users, payments, broadcasts, and settings from any browser.

---

## ✨ What you can do from the web panel

- 📊 **Dashboard** — Live stats: users, downloads, revenue (today & all-time)
- 💎 **Plans** — Create/edit/delete subscription plans (changes apply instantly to bot)
- 👥 **Users** — Search, ban, unban, grant premium with custom durations
- 💳 **Payments** — View all transactions, filter by status
- 📢 **Broadcast** — Send announcements to all/premium/free users
- 📋 **Logs** — Filter activity by level (info/warning/error)
- ⚙️ **Settings** — Maintenance mode, welcome message, support contact
- 🔐 **Change Password** — Secure your admin account

---

## 🚀 First-Time Setup

### Step 1 — Add environment variables on Railway

In your Railway project → your bot service → **Variables** tab:

```
ADMIN_WEB_USER=admin
ADMIN_WEB_PASS=godzilla123
FLASK_SECRET_KEY=paste-a-long-random-string-here
```

**Generate a secure secret key:**
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### Step 2 — Generate Railway public domain

1. Railway → your bot service → **Settings** tab → **Networking**
2. Click **Generate Domain**
3. Copy the URL (e.g. `https://godzilla-bot-production.up.railway.app`)

### Step 3 — Set `WEB_PANEL_URL`

Back in **Variables** tab, add:
```
WEB_PANEL_URL=https://YOUR-URL-FROM-STEP-2
```

⚠️ No trailing slash!

Railway auto-redeploys after you add variables.

### Step 4 — Update Razorpay webhook

If you already set up Razorpay, update the webhook URL:

1. Razorpay Dashboard → Settings → Webhooks
2. Edit existing webhook
3. New URL: `https://YOUR-URL/webhook/razorpay`
4. Save

(Both the bot webhook and admin panel share the same Flask app and port now.)

### Step 5 — Access your panel!

Open in browser: `https://YOUR-URL/login`

**Login with:**
- Username: `admin`
- Password: `godzilla123`

**🔒 IMPORTANT:** Go to top-right **key icon** → **Change Password** immediately!

---

## 📱 Accessing from Telegram Bot

As an admin, just send `/admin_panel` in the bot:

```
🛠 GODZILLA Admin Control Panel

Access the full web dashboard to manage:
▫️ Subscription plans (edit prices live!)
▫️ User accounts (ban, premium, search)
▫️ Payments & revenue
▫️ Broadcasts
▫️ Activity logs
▫️ Bot settings

🔐 Login with your admin credentials.

[🔐 Open Admin Panel]   ← button opens web URL
```

Regular users won't see this command — only Telegram IDs in `ADMIN_IDS` can use it.

---

## 💎 Managing Subscription Plans (The Main Feature)

### Creating a plan

1. Admin panel → **Plans** (left sidebar)
2. Click **+ New Plan**
3. Fill in:
   - **Key:** unique identifier (lowercase, e.g. `monthly`, `yearly`, `lifetime`)
   - **Name:** Display name (e.g. `💎 Monthly Premium`)
   - **Amount:** Price in ₹ (e.g. `49`)
   - **Duration:** Days (e.g. `30` for monthly, `365` for yearly)
   - **Daily Limit:** Max downloads per day for this plan
   - **Description:** Shown to users
   - **Active:** Toggle ON to show in `/subscribe`
   - **Sort Order:** Lower = shown higher in list (1 = top)
4. Click **Save Plan**

✨ **Changes apply instantly** — next time someone runs `/subscribe`, they see the new plans!

### Example: Multi-tier pricing

Create 3 plans:
- **Weekly** — ₹19, 7 days, 50/day
- **Monthly** — ₹49, 30 days, 100/day
- **Yearly** — ₹399 (17% discount), 365 days, 200/day

Users will see all 3 buttons in `/subscribe`!

### Limited-time offer?

Just lower the **Amount** on an existing plan — saves instantly. Change back later.

---

## 👥 Managing Users

### Search & filter

1. Admin panel → **Users**
2. Search by name, username, or Telegram ID
3. Filter: All / Premium / Free / Banned

### User actions (on user detail page)

- **Ban/Unban** — Prevent user from using bot
- **Grant Premium** — Give X days of premium (custom duration)
- **Revoke Premium** — End premium immediately

Everything you do here updates the bot instantly.

---

## 📢 Broadcasting

1. Admin panel → **Broadcast**
2. Select target: All / Premium / Free
3. Type message (supports Markdown: `*bold*`, `_italic_`, `[link](url)`)
4. Click **Send Broadcast**
5. Confirm

Bot sends to every eligible user with rate limiting (~20 msgs/sec). See status in **Recent Broadcasts** panel.

---

## ⚙️ Settings

### Maintenance Mode

Turn ON when updating the bot. Users get your custom message instead of normal responses.

### Welcome Message

Override the default `/start` message with your own (supports Markdown).

### Support Contact

Shown in `/help` — change to your own username.

---

## 🔐 Security Best Practices

1. **Change default password immediately** after first login
2. **Use a strong `FLASK_SECRET_KEY`** — at least 32 random chars
3. **Keep `ADMIN_WEB_PASS` in Railway env vars**, never commit to GitHub
4. **Check `/logout` works** — always log out on shared devices
5. **Monitor logs** — check for failed login attempts

### If you forget password:

1. Railway → Variables → update `ADMIN_WEB_PASS` to new value
2. Database → delete the `admin_users` row (via Railway's PostgreSQL query tool)
3. Restart bot → new default admin is created with the new password

---

## 🧪 Testing Locally (Termux)

The web panel works locally too! Just:

1. Set `.env` → `WEB_PANEL_URL=http://localhost:8080`
2. Run `python bot.py`
3. Open browser on phone → `http://localhost:8080/login`

⚠️ Razorpay webhook won't work locally (needs public HTTPS) — use test mode manual activation via `/premium` command.

---

## 🐛 Troubleshooting

**Panel shows "BuildError" or "not found"**
- Flask templates folder is missing — make sure `web/templates/` exists in deploy
- Check logs for Python import errors

**Can't log in**
- Check `ADMIN_WEB_USER` and `ADMIN_WEB_PASS` in Railway env vars
- Check bot logs — first-run creates admin from those env vars
- If you changed env vars, the new admin won't be created (only on first run) — manually delete admin_users table

**"Session expired" after every click**
- `FLASK_SECRET_KEY` is changing between restarts (using default)
- Set it to a fixed random string in Railway env vars

**Plans not showing in bot after creating**
- Make sure `is_active` is checked when creating
- Try `/subscribe` in bot — it reads from DB every time

**Broadcast fails**
- Check bot service is running
- Some users may have blocked the bot (normal — shows as "Failed" count)

**Revenue shows ₹0**
- Only `status='paid'` payments count — pending orders don't show
- Webhook must be working for payments to be marked paid

---

## 📊 Quick Access URLs

Once deployed, these are your admin URLs:

| Page | URL |
|------|-----|
| Login | `/login` |
| Dashboard | `/admin/dashboard` |
| Plans | `/admin/plans` |
| Users | `/admin/users` |
| Payments | `/admin/payments` |
| Broadcast | `/admin/broadcast` |
| Logs | `/admin/logs` |
| Settings | `/admin/settings` |
| Change Password | `/admin/change-password` |

---

## 💡 Pro Tips

1. **Bookmark** the login page on your phone's home screen for 1-tap access
2. **Set up 2 admins** — share with co-admin by creating more `AdminUser` rows (requires DB access for now)
3. **Use maintenance mode** during Railway deploys
4. **Monitor dashboard** daily to spot trends and growth

---

_🦖 Now you control the beast from anywhere._
