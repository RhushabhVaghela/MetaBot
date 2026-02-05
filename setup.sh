#!/bin/bash
echo "Setting up MegaBot environment..."

# Install Python dependencies
pip install -r requirements.txt

# Install UI dependencies
cd ui
npm install
cd ..

echo "Setup complete. To start MegaBot:"
echo "1. Start OpenClaw gateway: cd '/mnt/d/Agents and other repos/openclaw' && npm run gateway:dev"
echo "2. Start MegaBot Orchestrator: python core/orchestrator.py"
echo "3. Start MegaBot UI: cd ui && npm run dev"
