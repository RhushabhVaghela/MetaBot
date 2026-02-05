#!/bin/bash
set -e

echo "🚀 MegaBot Entrypoint Starting..."

# Check if memU is mounted and needs installation
if [ -d "/app/external_repos/memU" ] && [ -f "/app/external_repos/memU/pyproject.toml" ]; then
    echo "📦 Found real memU. Checking for installation..."
    if ! python -c "import memu" &> /dev/null; then
        echo "⚙️ Installing real memU from source..."
        cd /app/external_repos/memU
        pip install -e .
        cd /app
    else
        echo "✅ memU already installed."
    fi
else
    echo "⚠️ Real memU not found in /app/external_repos/memU. Using dummy/fallback mode."
fi

echo "🎬 Starting MegaBot Orchestrator..."
exec python core/orchestrator.py
