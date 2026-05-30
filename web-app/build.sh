#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔══════════════════════════════════════════╗"
echo "║  Lyra Knowledge Base — Build & Package   ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found!"
    echo "   Please install Node.js >= 18: https://nodejs.org/"
    echo "   Or run ./setup.sh first."
    exit 1
fi

NODE_VERSION=$(node -e "console.log(process.version.split('.')[0].replace('v',''))")
if [ "$NODE_VERSION" -lt 18 ]; then
    echo "❌ Node.js >= 18 required (found v$(node --version))"
    exit 1
fi
echo "✅ Node.js $(node --version)"

# Check pnpm
if ! command -v pnpm &> /dev/null; then
    echo "❌ pnpm not found! Run ./setup.sh first."
    exit 1
fi
echo "✅ pnpm $(pnpm --version)"

# Check dependencies
if [ ! -d "node_modules" ]; then
    echo ""
    echo "📦 Dependencies not found, running install..."
    pnpm install
fi

# Build
echo ""
echo "🔨 Building static site..."
pnpm build

if [ $? -ne 0 ]; then
    echo "❌ Build failed!"
    exit 1
fi

# Package
echo ""
echo "📦 Packaging dist/..."

TIMESTAMP=$(date +%Y%m%d)
OUTPUT_NAME="lyra-kb-${TIMESTAMP}"
OUTPUT_DIR="$SCRIPT_DIR/release"
OUTPUT_ZIP="${OUTPUT_DIR}/${OUTPUT_NAME}.tar.gz"

mkdir -p "$OUTPUT_DIR"

# Create a serve script inside dist
cat > "dist/serve.sh" << 'SERVE_EOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "╔══════════════════════════════════════════╗"
echo "║  Lyra Knowledge Base — Local Server      ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Starting server at http://localhost:8080"
echo "Press Ctrl+C to stop."
echo ""

# Try python3 first, then python, then npx serve
if command -v python3 &> /dev/null; then
    open "http://localhost:8080" 2>/dev/null || xdg-open "http://localhost:8080" 2>/dev/null || true
    python3 -m http.server 8080
elif command -v python &> /dev/null; then
    open "http://localhost:8080" 2>/dev/null || xdg-open "http://localhost:8080" 2>/dev/null || true
    python -m http.server 8080
elif command -v npx &> /dev/null; then
    open "http://localhost:8080" 2>/dev/null || xdg-open "http://localhost:8080" 2>/dev/null || true
    npx --yes serve -s . -l 8080
else
    echo "❌ Neither Python nor Node.js found."
    echo "   Please open index.html directly or install Python/Node.js"
    exit 1
fi
SERVE_EOF
chmod +x "dist/serve.sh"

# Create tar.gz
tar -czf "$OUTPUT_ZIP" -C dist .

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║  ✅ Build & Package complete!            ║"
echo "╠══════════════════════════════════════════╣"
echo "║                                          ║"
echo "║  Output: release/${OUTPUT_NAME}.tar.gz   ║"
echo "║                                          ║"
echo "║  Usage:                                  ║"
echo "║  1. Extract anywhere                     ║"
echo "║  2. Run ./serve.sh (needs Python/Node)   ║"
echo "║  3. Or open index.html directly          ║"
echo "║                                          ║"
echo "╚══════════════════════════════════════════╝"

# Show file size
SIZE=$(du -h "$OUTPUT_ZIP" | cut -f1)
echo ""
echo "📏 Package size: $SIZE"
