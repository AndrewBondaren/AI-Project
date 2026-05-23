pip install fastapi uvicorn httpx pydantic
pip install -r requirements.txt

# Init Backend
npm run init
# Init FrontEnd
npm run init-electron

# Launch app
npm run dev

# Upload Data
curl -X POST http://localhost:8000/api/seed/import -F "path={relative_path}/fixtures/seed.json"
curl -X POST http://localhost:8000/api/worlds/import -F "path={relative_path}/fixtures/world_test.json"

Example
curl -X POST http://localhost:8000/api/seed/import -F "path=e:/AI Project/fixtures/seed.json"
curl -X POST http://localhost:8000/api/worlds/import -F "path=e:/AI Project/fixtures/world_test.json"
curl -X POST http://localhost:8000/api/characters/import -F "path=e:/AI Project/fixtures/character_test.json"


# 1. Создать сессию
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d "{\"world_uid\": \"world-test-001\", \"character_id\": \"<uid из ответа /characters/import>\"}"

# 2. Отправить сообщение
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d "{\"session_id\": \"<session_id>\", \"llm_provider\": \"qwen\", \"model\": \"qwen3:14b\", \"meta\": {}, \"message\": \"Осмотреться вокруг\", \"request_id\": \"req-1\"}"

# 3. Запуск UI
Запустить браузерную версию: cd frontend && npm run dev:browser
Запустить с Electron: cd frontend && npm run dev:electron