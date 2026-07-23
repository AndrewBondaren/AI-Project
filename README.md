pip install fastapi uvicorn httpx pydantic

# Install project for dev
1. python -m venv .venv
2. 
Windows:
.venv\Scripts\activate
Linux/Mac:
source .venv/bin/activate
3. pip install -r requirements.txt

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
curl -X POST http://localhost:8000/api/worlds/world-test-001/map/import -F "path=e:/AI Project/fixtures/map_cells_ironhold.json"

All:
curl -X POST http://localhost:8000/api/worlds/import -F "path=e:/AI Project/fixtures/world_test.json"


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

TEST fixtures
# L0 bake only (no entry/L2 inside bake)
python backend/scripts/initialize_world.py --fixture fixtures/world_test_gen.json
# optional: separate entry job after bake
python backend/scripts/initialize_world.py --fixture fixtures/world_test_gen.json --entry
# optional debug cap: --max-tiles 16
# full world_bounds: --mode full

python backend/scripts/initialize_world.py --fixture fixtures/world_test_gen.json --mode full

# light → full on ONE world (L0 only; does not remap uid)
python backend/scripts/light_and_full_bake.py --fixture fixtures/world_test_gen.json
# report: .local/map-render/{world_uid}/light-and-full/
#   light-and-full-latest.log|.json
#   light-bake-render-latest.log  (ASCII after light)
#   full-bake-render-latest.log   (ASCII after full)


python backend/scripts/light_and_full_bake.py --fixture fixtures/world_test_gen_003.json
python backend/scripts/detailed_bake.py --world-uid world-test-003 --scope wilderness --gx -2 --gy -2

