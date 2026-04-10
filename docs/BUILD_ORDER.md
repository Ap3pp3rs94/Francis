1) (Optional) Services:
   docker compose -f infra/docker/compose.yaml up -d

2) Python:
   uv venv
   uv pip install -e .
   python -m francis api
   python -m francis daemon

3) UI:
   cd apps/chat_ui
   npm install
   npm run dev
