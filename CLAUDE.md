# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

A LINE Messaging webhook bot for マグチグループ (Maguchi Group) that answers employees' eldercare (介護) questions. The entire app lives in `main.py`: FastAPI receives LINE webhooks, forwards user text to the Anthropic API with a fixed Japanese system prompt, and replies via LINE's Messaging API.

## Commands

Install deps and run locally:

```bash
pip install -r requirements.txt
uvicorn main:app --reload          # local dev (default port 8000)
uvicorn main:app --host 0.0.0.0 --port $PORT   # production (matches Procfile)
```

Required env vars (see `.env.example`): `LINE_CHANNEL_SECRET`, `LINE_CHANNEL_ACCESS_TOKEN`, `ANTHROPIC_API_KEY`. They are read at import time with `os.environ[...]`, so missing values crash on startup.

There are no tests, linters, or build steps configured.

## Architecture

Request flow: `POST /webhook` → verify `X-Line-Signature` via `WebhookHandler.handle` → handler dispatches `MessageEvent` with `TextMessageContent` → `handle_message` calls `claude.messages.create` synchronously → reply sent via `MessagingApi.reply_message` using the event's `reply_token`.

Two details that matter when editing:

- **No conversation memory.** Each user turn is sent to Claude as a fresh single-message conversation. Adding history requires external storage (LINE webhooks are stateless and the process may run multiple replicas).
- **Sync handler inside async route.** `handle_message` is registered as a sync callback on `WebhookHandler` but is invoked from the async `/webhook` route via `handler.handle(...)`. The Anthropic call blocks the event loop. If you need concurrency, run the handler in a threadpool or switch to async clients.

`GET /` is a health check.

## Conventions

- Uses `line-bot-sdk` **v3** (`linebot.v3.*`). Do not mix in v2-style imports (`linebot.LineBotApi`, `linebot.WebhookHandler` at the top-level package) — they coexist in the same package and silently behave differently.
- The Anthropic model is pinned to `claude-sonnet-4-6` in `main.py`. Keep model IDs current per repo policy; do not invent marketing names.
- `SYSTEM_PROMPT` (Japanese) defines the bot's persona and **hard constraints**: no medical/legal/financial advice, no diagnosis, no collecting personal info, and every reply must end with one of the two prescribed referral lines (地域包括支援センター or 福利厚生担当窓口). Edits to the prompt should preserve these guardrails.
- Deployment target is a PaaS that injects `$PORT` (Heroku-style `Procfile`).
