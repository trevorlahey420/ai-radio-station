#!/bin/bash
# ============================================================
# Radio Free Gonzo — One-command setup script
# Run this after cloning the repo on a fresh Ubuntu machine
# Usage: bash setup.sh
# ============================================================

set -e  # stop on any error

echo ""
echo "================================================"
echo "  Radio Free Gonzo — Setup"
echo "================================================"
echo ""

# ── Step 1: System update ─────────────────────────────────
echo "[1/6] Updating system packages..."
sudo apt-get update -qq

# ── Step 2: Install Docker ────────────────────────────────
echo "[2/6] Installing Docker..."
sudo apt-get install -y -qq docker.io docker-compose-plugin curl git

# ── Step 3: Add user to docker group ─────────────────────
echo "[3/6] Configuring Docker permissions..."
sudo usermod -aG docker "$USER"

# ── Step 4: Create .env from example ─────────────────────
echo "[4/6] Setting up .env file..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo ""
  echo "  *** ACTION REQUIRED ***"
  echo "  Your .env file has been created."
  echo "  You must add your API keys before launching."
  echo ""
  echo "  Open it with:  nano .env"
  echo ""
  echo "  Required:"
  echo "    OPENAI_API_KEY=sk-..."
  echo "    ICECAST_PASSWORD=your-password"
  echo ""
else
  echo "  .env already exists, skipping."
fi

# ── Step 5: Create outputs directory ─────────────────────
echo "[5/6] Creating output directories..."
mkdir -p outputs/audio_cache

# ── Step 6: Done ──────────────────────────────────────────
echo "[6/6] Setup complete!"
echo ""
echo "================================================"
echo "  Next steps:"
echo ""
echo "  1. Add your API keys:"
echo "     nano .env"
echo ""
echo "  2. (Optional) Edit your music taste:"
echo "     nano config/preferences.yaml"
echo ""
echo "  3. Launch the station:"
echo "     newgrp docker"
echo "     docker compose up -d"
echo ""
echo "  4. Open the web player:"
echo "     http://localhost:8080"
echo ""
echo "  5. Check logs:"
echo "     docker compose logs -f radio"
echo "================================================"
echo ""
