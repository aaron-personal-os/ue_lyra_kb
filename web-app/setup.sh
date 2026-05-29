#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔══════════════════════════════════════════╗"
echo "║  Lyra Knowledge Base — Setup             ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found!"
    echo "   Please install Node.js >= 18: https://nodejs.org/"
    exit 1
fi

NODE_VERSION=$(node -e "console.log(process.version.split('.')[0].replace('v',''))")
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Node.js >= 18 required (found v$(node --version))"
    echo "   Download: https://nodejs.org/"
    exit 1
fi
echo "✅ Node.js $(node --version)"

# Check/Install pnpm
if ! command -v pnpm &> /dev/null; then
    echo "📦 Installing pnpm..."
    npm install -g pnpm
fi
echo "✅ pnpm $(pnpm --version)"

# Install dependencies
echo ""
echo "📦 Installing project dependencies..."
pnpm install

# Install dev-only terminal-server dependencies (ADR-0003).
# This is best-effort: failure here only disables the embedded terminal,
# the knowledge base itself still works.
echo ""
echo "📦 Installing terminal-server dependencies (dev-only)..."
if (cd terminal-server && pnpm install); then
    echo "✅ terminal-server ready"
else
    echo "⚠️  terminal-server install failed — embedded terminal will be unavailable."
    echo "   Knowledge base will still work normally."
fi

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  ✅ Setup complete!                      ║"
echo "║  Run: ./start.sh                         ║"
echo "╚══════════════════════════════════════════╝"
