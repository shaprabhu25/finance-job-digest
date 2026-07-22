# Finance Job Digest — Setup (≈15 min, phone-friendly)

A daily Telegram digest of finance roles in Bangalore / remote, from company ATS
boards + YC companies. Free forever. Everything below is done on **your own**
Telegram + GitHub accounts.

> You'll paste exactly **3 secret values** into GitHub. Nothing else is manual.
> Do all of this in a **phone browser** (github.com) — the GitHub *app* alone
> can't create repos or add secrets.

---

## Part 1 — Telegram (get 2 values)

1. Open Telegram → search **@BotFather** → **Start**.
2. Send `/newbot`. Pick a name, and a username ending in `bot`.
3. BotFather replies with a **token** like `8123456:AAH...`. → this is **`TELEGRAM_BOT_TOKEN`**.
4. Open your new bot and send it `hi` (a bot can't message you until you message it first).
5. Search **@userinfobot** → **Start**. It replies with your numeric **Id**. → this is **`TELEGRAM_CHAT_ID`**.

## Part 2 — GitHub (get 1 value + create the repo)

6. Create a **GitHub account** (github.com) if you don't have one.
7. Get the code: open the template repo link you were given → **Use this template** →
   **Create a new repository** (private is fine). All the code is now in *your* repo.
8. Create a **PAT** (fixes the 60-day auto-disable): github.com → your avatar → **Settings**
   → **Developer settings** → **Personal access tokens** → **Fine-grained tokens** →
   **Generate new token**. Repository access: only your new repo. Permissions:
   **Contents → Read and write**. Generate, copy it. → this is **`GH_PAT`**.

## Part 3 — Add the 3 secrets

9. Your repo → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**.
   Add all three (name must match exactly):
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
   - `GH_PAT`

## Part 4 — Turn it on

10. **Actions** tab → if prompted, enable workflows.
11. **Seed the company list**: Actions → **Seed Companies** → **Run workflow**. Wait a few
    minutes — it fills `companies.csv` with hundreds of YC companies. (Re-run anytime to add more.)
12. **Test**: Actions → **Daily Digest** → **Run workflow** → tick **dry_run** → Run.
    Open the run log; you should see finance cards being built. (Dry-run doesn't send.)
13. **Go live**: run **Daily Digest** again with dry_run **unticked** → cards arrive in Telegram. ✅

It now runs **every day at 8:00 AM IST** automatically.

---

## Daily use (all in Telegram)

- `/add <careers-url>` — watch a company (paste any careers page URL)
- `/list` — show the watchlist
- `/remove <name>` — stop watching
- `/suggest` — recently-funded companies; `/add` any that interest you

## Tuning (optional, edit in GitHub's web editor)

- **Experience band**: `filters.py` → `YOE_MIN_OK` / `YOE_MAX_OK`
- **Roles**: `filters.py` → `_INCLUDE` / `_EXCLUDE`
- **Schedule**: `.github/workflows/digest.yml` → `cron`
- **Daily card cap**: repo variable `DAILY_CAP` (default 40)

## If something's off

- **No messages?** Make sure you messaged your bot once (step 4) and the 3 secret
  names match exactly. Run Daily Digest with dry_run to see logs without sending.
- **A company won't resolve?** `/add` its **direct** board URL (jobs.lever.co/x,
  boards.greenhouse.io/x, jobs.ashbyhq.com/x) instead of its homepage.
