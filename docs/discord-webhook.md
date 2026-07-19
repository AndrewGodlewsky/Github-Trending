# Creating your Discord alert webhook

The daily pipeline posts a message to Discord **only when a run fails**, so you find out without checking logs. A "webhook URL" is just a private address Discord gives you that drops a message into one channel — no bot, no login, nothing to maintain.

You need the **Manage Webhooks** permission in the server (you have it automatically on a server you created).

## Steps

1. **Pick a channel** for the alerts. Either use an existing one or make a new one — e.g. right-click a category → *Create Channel* → name it `github-trending-alerts`.
2. Hover the channel and click the **⚙️ gear** (*Edit Channel*).
3. In the left menu, open **Integrations**.
4. Click **Webhooks** → **New Webhook** (or **Create Webhook**).
5. Click the webhook that appears. Give it a name like **Trending Pipeline** (this is what shows as the sender). Optionally set an avatar.
6. Click **Copy Webhook URL**. It looks like:
   ```
   https://discord.com/api/webhooks/1234567890/AbCdEf...longtoken...
   ```
7. Click **Save Changes**.

## Wire it in

Open `Github-Trending/.env` and set:

```
ALERT_WEBHOOK_URL=https://discord.com/api/webhooks/1234567890/AbCdEf...
```

> ⚠️ Treat this URL like a password — anyone who has it can post to that channel. It lives only in `.env`, which is gitignored.

## Test it

```bash
uv run python tools/test_alert.py
```

You should see a **✅ github-trending: webhook connected** message appear in your Discord channel within a second or two. If you get an error instead, double-check the URL was copied whole.
