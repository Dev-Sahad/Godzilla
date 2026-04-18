# 💳 Razorpay Subscription Setup Guide

Complete guide to enabling paid subscriptions for GODZILLA bot.

---

## 📋 Prerequisites

- Indian bank account
- PAN card
- Age 18+
- Phone number for verification

---

## 🚀 Step 1 — Sign up for Razorpay

1. Go to **https://razorpay.com/**
2. Click **Sign Up** (top right)
3. Enter email, password, business type
4. Verify email & phone

**Note:** You can skip activation for now and use **test mode** to develop. Activate later for real payments.

---

## 🔑 Step 2 — Get API Keys

1. Log in to **https://dashboard.razorpay.com**
2. Go to **Settings** (⚙️ bottom left) → **API Keys**
3. Click **Generate Key**
4. **Copy both:**
   - `Key ID` (starts with `rzp_test_` or `rzp_live_`)
   - `Key Secret`

⚠️ **Save the Secret somewhere safe** — you can't view it again later!

### Test vs Live:
- `rzp_test_...` — fake payments, for development (works without KYC)
- `rzp_live_...` — real payments, requires completed KYC

---

## ✅ Step 3 — Complete KYC (For Live Mode)

In Dashboard → **Complete Activation**:

**Documents needed:**
- PAN card (photo)
- Bank account details + cancelled cheque or passbook
- Business address proof
- Aadhaar OR business registration (for companies)

**Approval time:** Usually 1-2 business days.

While waiting, use **test mode** to develop.

---

## 🔗 Step 4 — Set Up Webhook

This tells Razorpay to notify your bot when a payment is successful.

### On Railway:

1. Deploy your bot (see main README)
2. In Railway → click your bot service → **Settings** → **Networking**
3. Click **Generate Domain** — you'll get a URL like `godzilla-bot-production.up.railway.app`
4. **Copy this URL** — it's your webhook base

### In Razorpay Dashboard:

1. Settings → **Webhooks** → **+ Add New Webhook**
2. **Webhook URL:** `https://YOUR-RAILWAY-URL/webhook/razorpay`
   Example: `https://godzilla-bot-production.up.railway.app/webhook/razorpay`
3. **Secret:** Create any long random string (e.g. `godzilla_webhook_secret_xyz123`)
   **Copy this — you'll need it for `.env`!**
4. **Active Events:** Check these:
   - ✅ `payment.captured`
   - ✅ `payment_link.paid`
   - ✅ `payment.failed` (optional)
5. Click **Create Webhook**

---

## 🔐 Step 5 — Configure `.env`

Add these to your `.env` file (or Railway variables):

```env
RAZORPAY_KEY_ID=rzp_test_abcd1234xyz        # From Step 2
RAZORPAY_KEY_SECRET=SecretFromStep2         # From Step 2
RAZORPAY_WEBHOOK_SECRET=godzilla_webhook_secret_xyz123   # From Step 4
```

### On Railway:
1. Click your bot service → **Variables** tab
2. Add each one as a new variable
3. Bot auto-redeploys with new config

---

## 💰 Step 6 — Set Your Price

Edit `config.py` — find the `SUBSCRIPTION_PLANS` dict:

```python
SUBSCRIPTION_PLANS = {
    "monthly": {
        "name": "💎 Monthly Premium",
        "amount": 49,           # 👈 Change this — price in ₹
        "duration_days": 30,
        "daily_limit": 100,
        "description": "Unlimited-ish downloads for 30 days",
    },
}
```

**Tips for pricing:**
- ₹29-49 → impulse buy territory
- ₹99 → standard monthly
- ₹199 → premium tier
- Start low, raise after user growth

### Add more plans:

```python
SUBSCRIPTION_PLANS = {
    "monthly": {
        "name": "💎 Monthly",
        "amount": 49,
        "duration_days": 30,
        "daily_limit": 100,
        "description": "30 days premium",
    },
    "quarterly": {
        "name": "💎 3-Month (Save 15%)",
        "amount": 125,
        "duration_days": 90,
        "daily_limit": 100,
        "description": "90 days premium",
    },
    "yearly": {
        "name": "💎 Yearly (Save 40%)",
        "amount": 349,
        "duration_days": 365,
        "daily_limit": 200,
        "description": "365 days premium",
    },
}
```

Restart bot → `/subscribe` automatically shows all plans!

---

## 🧪 Step 7 — Test It!

### Test Mode (no real money):

1. Use `rzp_test_` keys
2. In bot, send `/subscribe`
3. Click plan → get payment link
4. Open link → pay with **test card:**
   - Card: `4111 1111 1111 1111`
   - Expiry: any future date (e.g. `12/30`)
   - CVV: any 3 digits
   - OTP: `1234` or `123456`
5. Payment succeeds → bot should auto-activate premium
6. Send `/myplan` → should show Premium active

### Live Mode:

- Switch keys to `rzp_live_...` in `.env`
- Test with a small amount (₹1 payment) to yourself first!

---

## 🔧 Common Issues

### "Payment not configured" message
- Check `RAZORPAY_KEY_ID` and `RAZORPAY_KEY_SECRET` are set
- Check Railway deployment log for errors
- Restart bot

### Payment completes but premium not activated
- **Most common:** webhook URL is wrong
  - Must be `https://your-domain/webhook/razorpay`
  - Must be Railway's public URL (not localhost)
- Check webhook secret matches exactly
- Check Razorpay dashboard → Webhooks → delivery logs

### "Invalid signature" in logs
- `RAZORPAY_WEBHOOK_SECRET` doesn't match what's in Razorpay dashboard
- Regenerate in Razorpay → copy exactly → update `.env`

### Webhook not firing
- Wait — payment can take 1-2 min to confirm
- Check webhook is **active** in Razorpay dashboard
- Check subscribed events include `payment.captured` and `payment_link.paid`

### User doesn't get confirmation message
- Webhook fired but bot didn't send message
- Check bot logs for errors around that time
- Their Telegram ID must be in `notes` of the payment link (we set this automatically)

---

## 💼 Going Live Checklist

Before accepting real money:

- [ ] KYC completed on Razorpay
- [ ] Live API keys (`rzp_live_...`) in `.env`
- [ ] Webhook URL updated to production Railway URL
- [ ] Tested with a ₹1 payment successfully
- [ ] Bank account linked for withdrawals
- [ ] GST registration (if revenue > ₹20L/year)
- [ ] Terms of service + refund policy (add to `/about`)
- [ ] Privacy policy

---

## 📊 Managing Subscriptions

### As admin:

```
/premium <user_id>       — Grant premium manually
/premium <user_id> off   — Revoke premium
/stats                   — See premium user count
```

### Users can:

```
/subscribe   — Buy premium
/myplan      — Check status
/cancel      — Disable auto-renew
/plans       — See all plans
```

---

## 💡 Growth Tips

1. **Offer a free trial:** Give new users 7 days free with `/premium <user_id>` manually
2. **Referral rewards:** Invite 10 friends = 7 days free (built-in!)
3. **Limited-time discount:** Change price temporarily, announce via `/broadcast`
4. **Thank-you posts:** Post subscriber count milestones to your channel

---

## 🔒 Security Notes

- ✅ Never share `RAZORPAY_KEY_SECRET`
- ✅ Webhook signature verification is enabled (prevents fake activations)
- ✅ All payments recorded in `payments` table (audit trail)
- ❌ Don't bypass signature check, even for testing

---

**Need help?** Razorpay support is very responsive: https://razorpay.com/support

---

_Ready to make money with your bot! 💰🦖_
