# Zoom Unofficial Community Skill

A community-built [Clawdbot](https://github.com/clawdbot/clawdbot) skill for interacting with Zoom's REST API — manage meetings, recordings, team chat, AI meeting summaries, and more.

> ⚠️ **Unofficial** — This skill is not affiliated with or endorsed by Zoom Video Communications.

## Features

- **Meetings** — List, create, update, delete, and view meeting details
- **Recordings** — List, download, and delete cloud recordings
- **AI Summaries** — Retrieve AI Companion meeting summaries
- **Team Chat** — Send messages, DMs, list channels and contacts
- **Users** — View profiles and list account users
- **Phone** — View call logs (requires Zoom Phone)

## Quick Start

### 1. Install the skill

```bash
clawdhub install zoom-unofficial-community-skill
```

Or clone manually:
```bash
git clone https://github.com/tanchunsiong/zoom-unofficial-community-skill.git skills/zoom
```

### 2. Install dependencies

```bash
pip3 install requests PyJWT --break-system-packages
```

### 3. Create a Zoom Server-to-Server OAuth App

1. Go to https://marketplace.zoom.us/
2. Click **Develop** → **Build App**
3. Choose **Server-to-Server OAuth**
4. Note your **Account ID**, **Client ID**, and **Client Secret**
5. Add the scopes you need (see [Scopes](#scopes) below)
6. Activate the app

### 4. Configure

Add to your `.env` file:

```env
ZOOM_ACCOUNT_ID=your_account_id
ZOOM_CLIENT_ID=your_client_id
ZOOM_CLIENT_SECRET=your_client_secret
ZOOM_USER_EMAIL=you@example.com
```

`ZOOM_USER_EMAIL` tells the S2S app which user to act as. Defaults to `me` if unset.

## Usage

```bash
# Your profile
python3 scripts/zoom.py users me

# List upcoming meetings
python3 scripts/zoom.py meetings list

# Schedule a meeting
python3 scripts/zoom.py meetings create --topic "Standup" --start "2025-01-28T10:00:00" --duration 30

# Update meeting settings
python3 scripts/zoom.py meetings update <id> --duration 60 --join-before-host true --auto-recording cloud

# List cloud recordings
python3 scripts/zoom.py recordings list --from "2025-01-01" --to "2025-01-31"

# Download recordings
python3 scripts/zoom.py recordings download <meeting_id> --output ~/Downloads

# AI meeting summaries
python3 scripts/zoom.py summary list
python3 scripts/zoom.py summary get <meeting_uuid>

# Send a Team Chat DM
python3 scripts/zoom.py chat dm user@example.com "Hey!"

# Send to a channel
python3 scripts/zoom.py chat send <channel_id> "Hello team!"

# List chat channels
python3 scripts/zoom.py chat channels
```

See [SKILL.md](SKILL.md) for full command reference.

## Scopes

Add only the scopes you need in your Zoom Marketplace app:

| Feature | Scopes |
|---|---|
| Users | `user:read:admin` |
| Meetings | `meeting:read:admin`, `meeting:write:admin` |
| Recordings | `recording:read:admin`, `recording:write:admin` |
| Team Chat | `chat_channel:read:admin`, `chat_message:read:admin`, `chat_message:write:admin` |
| Contacts | `contact:read:admin` |
| AI Summaries | `meeting_summary:read:admin` |
| Phone | `phone:read:admin` |

If you get a scope error, the CLI will tell you exactly which scope to add and link you to the Zoom Marketplace.

## Error Handling

- **Scope errors** — Clear message with link to add the missing scope
- **Rate limits** — Automatic retry with backoff on 429 responses
- **Missing params** — Validates required parameters before calling the API
- **Feature not enabled** — Helpful hint when a Zoom feature isn't available on your plan

## Authentication Details

See [references/AUTH.md](references/AUTH.md) for a detailed guide on setting up Server-to-Server OAuth.

## Contributing

Issues and PRs welcome at [github.com/tanchunsiong/zoom-unofficial-community-skill](https://github.com/tanchunsiong/zoom-unofficial-community-skill).

## License

MIT
