# 💳 UPI Manual Payment Setup Guide

GODZILLA now supports **direct UPI payments** with UTR verification.

**How it works:**
- User pays to your UPI ID
- User sends UTR (transaction ID) to bot
- You approve with 1 tap → premium activates

✅ Zero fees • ✅ Full control • ✅ Works without KYC • ✅ Money straight to your bank

---

## 📋 What You Need

1. **A UPI ID** — e.g. `sahad@okhdfcbank`, `sahad@paytm`, `9876543210@upi`
2. **Your UPI QR code image** — saved as PNG
3. **Admin Telegram ID** in `ADMIN_IDS`

---

## 🚀 Step 1 — Get Your UPI ID

### Option A — From your bank app
- SBI: `yourname@sbi`
- HDFC: `yourname@hdfcbank` or `@okhdfcbank`
- ICICI: `yourname@okicici`
- Check your bank app → UPI section

### Option B — From GPay/PhonePe
- **GPay:** Open app → tap your profile → **Bank Account** → copy UPI ID
- **PhonePe:** Profile → **My BHIM UPI ID**
- **Paytm:** Profile → **UPI settings**

---

## 🚀 Step 2 — Get Your QR Code Image

### From GPay:
1. Open GPay → tap your profile photo
2. Tap **QR code** at top
3. Tap **Share** → **Save image** (or screenshot)

### From PhonePe:
1. Open PhonePe → **My QR**
2. Tap **Share** → **Download**

### From Paytm:
1. Open Paytm → **Profile** → **My UPI ID & QR**
2. **Save QR**

**Save the file as `upi_qr.png`** — you'll upload this to your bot.

---

## 🚀 Step 3 — Add QR to Your Bot

### Locally in Termux:
```bash
cd ~/godzilla_v3/web/static/
# Copy your QR image here
cp ~/storage/downloads/upi_qr.png .
ls
# Should show: upi_qr.png
```

### On Railway (after deploy):
1. Put `upi_qr.png` in `web/static/` folder of your GitHub repo
2. Commit & push:
   ```bash
   git add web/static/upi_qr.png
   git commit -m "Add UPI QR code"
   git push
   ```
3. Railway auto-redeploys

---

## 🚀 Step 4 — Configure Environment Variables

### Locally (`.env` file):
```env
UPI_ID=sahad@okhdfcbank
UPI_NAME=GODZILLA
UPI_QR_FILENAME=upi_qr.png
```

### On Railway:
Variables tab → add:
- `UPI_ID` = `sahad@okhdfcbank`
- `UPI_NAME` = `GODZILLA`
- `UPI_QR_FILENAME` = `upi_qr.png`

Railway auto-redeploys after adding vars.

---

## 🚀 Step 5 — Test It!

### As a user:
1. Send `/subscribe` to bot
2. Pick a plan
3. Bot sends QR + UPI ID + amount
4. Pay ₹49 (or whatever plan costs) to that UPI
5. Copy 12-digit UTR from your UPI app
6. Send UTR to bot

### As admin:
1. Check your Telegram — you'll get a notification:
   ```
   💰 NEW PAYMENT REQUEST
   
   Request ID: #1
   User: @testuser
   Plan: Monthly Premium
   Amount: ₹49
   UTR: 123456789012
   
   [✅ Approve]  [❌ Reject]
   ```
2. Open your UPI app → verify ₹49 was received
3. Match the UTR → tap **Approve**
4. User automatically gets premium activated

---

## 📋 Admin Commands

| Command | What it does |
|---------|--------------|
| `/pending` | Show all pending payment requests |
| `/approve <id>` | Approve a request (use request_id or user_id) |
| `/reject <id>` | Reject a request |
| `/premium <user_id> <days>` | Manually grant premium without payment |

**Examples:**
```
/approve 5           → Approves request #5
/approve 123456789   → Approves user's latest pending request
/reject 7            → Rejects request #7
/pending             → Lists all waiting requests
```

---

## 🛡 How to Verify UTR in Your UPI App

### GPay:
1. Open GPay → tap your profile
2. Tap **Show transaction history**
3. Find the ₹49 credit
4. Tap it → **UPI Transaction ID** is the UTR

### PhonePe:
1. Open PhonePe → **History**
2. Find the credit entry
3. Tap → **UPI Ref. No.** = UTR

### Paytm:
1. **Passbook** → find the credit
2. Tap → **UPI Ref ID** = UTR

### Bank SMS:
- SBI: `UTR Ref no. 12345678901 credited...`
- HDFC: `UPI Ref: 12345678901`

**Match the 12 digits** with what the user sent. If matches → Approve.

---

## 🚨 Fraud Prevention Tips

### The bot protects you automatically:
- ✅ **Duplicate UTR detection** — same UTR can't be reused
- ✅ **Rate limit** — max 3 pending requests per user
- ✅ **Format validation** — only accepts 12-digit numbers
- ✅ **Audit log** — all approvals logged in database

### You should verify:
1. **Amount matches exactly** — user says ₹49, check you got ₹49 (not ₹40 or ₹4.9)
2. **UTR matches** — cross-check the 12 digits with your UPI app
3. **Date matches** — payment should be very recent (within hours)
4. **If unsure** → Reject and ask for screenshot

### Red flags to reject:
- ❌ UTR not found in your UPI app
- ❌ Wrong amount received
- ❌ Screenshot looks photoshopped
- ❌ User has been rejected multiple times
- ❌ UTR from a weird date (too old)

---

## 💡 Pro Tips

1. **Check payments in batches** — set aside 10 min at noon and 8 PM
2. **Create a Telegram channel** for payment logs (forward notifications there)
3. **Respond fast** — users are more likely to request refund if slow
4. **Thank users after approval** — bot does this automatically with a nice message

---

## 🔄 Flow Summary

```
User                Bot                 You
 |                   |                   |
 | /subscribe        |                   |
 |------------------>|                   |
 |                   |                   |
 | picks plan        |                   |
 |------------------>| creates deeplink  |
 |<------------------| QR + UPI ID       |
 |                   |                   |
 | pays via UPI app  |                   |
 |                   |                   |
 | sends UTR         |                   |
 |------------------>| validates UTR     |
 |                   |------------------>| notifies with
 |                   |                   |  Approve/Reject buttons
 |                   |                   |
 |                   |                   | You verify in UPI app
 |                   |                   | Tap [Approve]
 |                   |<------------------|
 |<------------------| "Premium activated!"
 |                   |                   |
```

---

## 🐛 Troubleshooting

**Bot says "Payments not configured"**
→ `UPI_ID` not set in env vars. Add it.

**QR image not showing**
→ File not at `web/static/upi_qr.png` OR wrong filename in `UPI_QR_FILENAME`

**Admin not getting notifications**
→ Your Telegram ID not in `ADMIN_IDS`. Add it (comma-separated if multiple).

**User says UTR is 15 digits**
→ Some banks show extra prefix. Tell them to take the last 12 digits only. Or you can edit the UTR regex in `handlers/manual_payment.py`.

**"UTR already submitted"**
→ User is trying to reuse a UTR. Genuine payments have unique UTRs. Reject.

**Want to see all past payments?**
→ Admin web panel → **Payments** tab (future update: show manual payments too)

---

## 💼 When to Switch to Razorpay

Manual UPI is great for starting but consider Razorpay once you have:
- 20+ payments per day (manual approval gets tiring)
- You want auto-renewal (manual doesn't support)
- You're making ₹20+L/year (GST invoices needed)

Switching is easy — just set `RAZORPAY_KEY_ID` & `RAZORPAY_KEY_SECRET` in env vars.

---

_🦖 Manual. Simple. Powerful._
