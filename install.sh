#!/bin/bash
# Integration script for SearXNG into Hermes Agent

set -e

echo "🔎 SearXNG Integration for Hermes Agent"
echo "========================================"

# Configuration
HERMES_DIR="${HERMES_DIR:-/home/spirit/Projects/AI_Agents/hermes-agent}"
SOURCE_DIR="/home/spirit/projects/search/searxng_integration"
TARGET_DIR="$HERMES_DIR/tools/searxng_integration"

echo ""
echo "📁 Directories:"
echo "  Source: $SOURCE_DIR"
echo "  Target: $TARGET_DIR"

# Check source exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "❌ Error: Source directory not found: $SOURCE_DIR"
    exit 1
fi

# Check hermes-agent exists
if [ ! -d "$HERMES_DIR" ]; then
    echo "❌ Error: Hermes Agent not found at: $HERMES_DIR"
    echo "   Set HERMES_DIR environment variable to correct path"
    exit 1
fi

# Create target directory
echo ""
echo "📂 Creating integration directory..."
mkdir -p "$TARGET_DIR"

# Copy files
echo "📋 Copying integration files..."
cp -r "$SOURCE_DIR"/* "$TARGET_DIR/"

# Install dependencies
echo ""
echo "📦 Installing dependencies..."
if [ -f "$HERMES_DIR/requirements.txt" ]; then
    # Add dependencies to hermes requirements
    echo "" >> "$HERMES_DIR/requirements.txt"
    echo "# SearXNG Integration" >> "$HERMES_DIR/requirements.txt"
    cat "$SOURCE_DIR/../requirements.txt" >> "$HERMES_DIR/requirements.txt"
fi

# Create __init__.py if needed
if [ ! -f "$TARGET_DIR/__init__.py" ]; then
    touch "$TARGET_DIR/__init__.py"
fi

echo ""
echo "✅ Integration complete!"
echo ""
echo "📖 Next steps:"
echo "   1. Edit ~/.hermes/config.yaml and add:"
echo "      web:"
echo "        backend: searxng"
echo ""
echo "   2. Optional configuration:"
echo "      searxng:"
echo "        request_interval: 3.0"
echo "        daily_limit: 500"
echo "        auto_discover: true"
echo ""
echo "   3. Restart Hermes Agent"
echo ""
echo "   4. Verify with: hermes tools"
echo ""
echo "🧪 Run test:"
echo "   cd $HERMES_DIR && python -m searxng_integration.searxng_tools"
