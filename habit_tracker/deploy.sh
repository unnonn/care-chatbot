#!/usr/bin/env bash
# One-shot Fly.io deploy script for the habit tracker.
# Usage: cd habit_tracker && ./deploy.sh
#
# Prerequisites:
#   1. flyctl installed:  curl -L https://fly.io/install.sh | sh
#   2. Logged in:         fly auth login
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v fly >/dev/null 2>&1; then
  echo "Error: flyctl not found. Install with:"
  echo "  curl -L https://fly.io/install.sh | sh"
  exit 1
fi

if ! fly auth whoami >/dev/null 2>&1; then
  echo "Not logged in. Running 'fly auth login'..."
  fly auth login
fi

APP_NAME="${FLY_APP_NAME:-}"

# If app doesn't exist yet, prompt for a unique name and create it
if [[ -z "$APP_NAME" ]]; then
  CURRENT_APP=$(grep -E '^app *= *' fly.toml | sed -E 's/.*"([^"]+)".*/\1/')
  if ! fly status -a "$CURRENT_APP" >/dev/null 2>&1; then
    read -rp "Choose a globally-unique Fly app name (e.g. habit-tracker-yourname): " APP_NAME
    if [[ -z "$APP_NAME" ]]; then
      echo "App name required."
      exit 1
    fi
    sed -i.bak -E "s/^app *=.*/app = \"$APP_NAME\"/" fly.toml
    rm -f fly.toml.bak
    fly apps create "$APP_NAME" --org personal
  else
    APP_NAME="$CURRENT_APP"
  fi
fi

# Create volume for SQLite if missing
if ! fly volumes list -a "$APP_NAME" 2>/dev/null | grep -q "habit_data"; then
  echo "Creating 1GB volume 'habit_data' in nrt (Tokyo)..."
  fly volumes create habit_data --region nrt --size 1 --yes -a "$APP_NAME"
fi

# Prompt for Resend API key if not already set
if ! fly secrets list -a "$APP_NAME" 2>/dev/null | grep -q "RESEND_API_KEY"; then
  echo ""
  echo "Set up email notifications? (Resend API key from https://resend.com)"
  read -rp "RESEND_API_KEY (press Enter to skip): " RESEND_KEY
  if [[ -n "${RESEND_KEY:-}" ]]; then
    fly secrets set RESEND_API_KEY="$RESEND_KEY" -a "$APP_NAME"
  fi
  read -rp "RESEND_FROM (e.g. \"Habit <you@yourdomain.com>\", Enter to use default): " RESEND_FROM
  if [[ -n "${RESEND_FROM:-}" ]]; then
    fly secrets set RESEND_FROM="$RESEND_FROM" -a "$APP_NAME"
  fi
fi

echo ""
echo "Deploying..."
fly deploy -a "$APP_NAME"

URL="https://${APP_NAME}.fly.dev"
echo ""
echo "✓ Deploy complete."
echo "  Open on your iPhone Safari:  $URL"
echo "  Then: Share button → 'ホーム画面に追加'"
