#!/bin/zsh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WORKSPACE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="$WORKSPACE_DIR/bureau-test-chambers-portal-release"

rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR/data"
mkdir -p "$OUTPUT_DIR/downloads"

cp "$SCRIPT_DIR/server.py" "$OUTPUT_DIR/server.py"
cp "$SCRIPT_DIR/index.html" "$OUTPUT_DIR/index.html"
cp "$SCRIPT_DIR/app.js" "$OUTPUT_DIR/app.js"
cp "$SCRIPT_DIR/styles.css" "$OUTPUT_DIR/styles.css"
cp "$SCRIPT_DIR/.env.example" "$OUTPUT_DIR/.env.example"
cp "$SCRIPT_DIR/.gitignore" "$OUTPUT_DIR/.gitignore"
cp "$SCRIPT_DIR/Procfile" "$OUTPUT_DIR/Procfile"
cp "$SCRIPT_DIR/DEPLOY_PUBLIC.md" "$OUTPUT_DIR/DEPLOY_PUBLIC.md"
cp "$SCRIPT_DIR/render.yaml" "$OUTPUT_DIR/render.yaml"
cp "$SCRIPT_DIR/start_portal.command" "$OUTPUT_DIR/start_portal.command"
cp "$SCRIPT_DIR/README.md" "$OUTPUT_DIR/README.md"
touch "$OUTPUT_DIR/data/.gitkeep"
touch "$OUTPUT_DIR/downloads/.gitkeep"

echo "Created standalone portal package at:"
echo "$OUTPUT_DIR"
echo ""
echo "Next:"
echo "1. Review the files in the release folder."
echo "2. Push that folder to its own GitHub repository."
echo "3. Follow DEPLOY_PUBLIC.md to deploy it."
