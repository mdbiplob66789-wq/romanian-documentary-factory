#!/usr/bin/env bash
set -euo pipefail

REPO="mdbiplob66789-wq/romanian-documentary-factory"

echo "== Install rclone + GitHub CLI =="
if ! command -v brew >/dev/null 2>&1; then
  echo "Homebrew is required: https://brew.sh"
  exit 1
fi
brew install rclone gh

echo
echo "== Google Drive authorization =="
echo "Create an rclone remote named exactly: gdrive"
echo "Choose Google Drive, accept the default client ID/secret, scope 1 (full access), and authorize in the browser."
rclone config

echo
if ! rclone listremotes | grep -qx 'gdrive:'; then
  echo "Remote gdrive: was not found. Run this script again and create it with the exact name gdrive."
  exit 1
fi

echo "== GitHub authorization =="
gh auth status >/dev/null 2>&1 || gh auth login

CONFIG_PATH="${HOME}/.config/rclone/rclone.conf"
if [[ ! -s "$CONFIG_PATH" ]]; then
  echo "rclone config not found at $CONFIG_PATH"
  exit 1
fi

SECRET_VALUE="$(base64 < "$CONFIG_PATH" | tr -d '\n')"
printf '%s' "$SECRET_VALUE" | gh secret set RCLONE_CONFIG_BASE64 --repo "$REPO"

echo
echo "DONE. GitHub Actions can now upload one final MP4 directly to Google Drive."
echo "Destination: My Drive / URME_RECI_FINAL_YOUTUBE.mp4"
echo "You can now run the Render documentary workflow from GitHub Actions."
