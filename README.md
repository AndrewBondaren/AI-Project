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

TEST fixtures (API)

# 0. Импорт мира из фикстуры
curl.exe -X POST http://localhost:8000/api/worlds/import -F "path=e:/AI Project/fixtures/world_test_gen.json"

# 1. Bake L0
# light — только тайлы с локациями
curl.exe -X POST "http://localhost:8000/api/worlds/world-test-003/map/pack/bake?mode=light" --max-time 600
# full — весь world_bounds + шов мира + topology районов/ворот
curl.exe -X POST "http://localhost:8000/api/worlds/world-test-003/map/pack/bake?mode=full" --max-time 600 -w "\nHTTP_CODE:%{http_code}\nTIME_S:%{time_total}\n"
# preview: какие тайлы войдут в L0 (без записи)
curl.exe "http://localhost:8000/api/worlds/world-test-003/map/bootstrap-tiles?scope=full"
# прогресс/полнота pack
curl.exe "http://localhost:8000/api/worlds/world-test-003/map/loading-progress"

# 2. Инициализация города (C11/C24 packing)
# generate-settlement = packing поселения поверх готового pack (light/full).
# Требует C23 topology (делает full_bake). Без якоря — очередь всех
# незапакованных районов до complete; уже упакованные районы пропускаются
# (packed_district_uids в manifest). Якорь = ровно один район:
#   district_uid — канонический uid района (named_locations)
#   at_x + at_y  — world-fine координаты, резолвер мапит на район (spawn-кейс)
# Оба якоря сразу → 422. Нет topology → 409. Результат дозаписывается
# кадрами в тот же locations/l.{uid}.settlement.zst.

# список локаций — взять location_uid
curl.exe "http://localhost:8000/api/worlds/world-test-003/locations"

# весь город (все районы до complete)
curl.exe -X POST "http://localhost:8000/api/worlds/world-test-003/locations/{location_uid}/generate-settlement?skip_if_initialized=true" --max-time 1800

# один район по uid
curl.exe -X POST "http://localhost:8000/api/worlds/world-test-003/locations/{location_uid}/generate-settlement?district_uid={district_uid}" --max-time 600

# один район по координатам (spawn-якорь)
curl.exe -X POST "http://localhost:8000/api/worlds/world-test-003/locations/{location_uid}/generate-settlement?at_x=1500&at_y=3000" --max-time 600

# все поселения разом
curl.exe -X POST "http://localhost:8000/api/worlds/world-test-003/generate-settlements?all=1" --max-time 1800

# или через detailed_bake: L2 terrain локации + C11 если settlement-like
curl.exe -X POST "http://localhost:8000/api/worlds/world-test-003/map/pack/bake?mode=detailed&scope=location&location_uid={location_uid}" --max-time 1800
# detailed_bake wilderness одного макро-тайла (опц. grade mill/paint)
curl.exe -X POST "http://localhost:8000/api/worlds/world-test-003/map/pack/bake?mode=detailed&scope=wilderness&tile_gx=-2&tile_gy=-2&grade_mill=true&grade_paint=true" --max-time 1800

# 3. Render pack (ASCII внутри JSON-ответа)
curl.exe "http://localhost:8000/api/worlds/world-test-003/map/render-world-grid"
curl.exe "http://localhost:8000/api/worlds/world-test-003/map/render-world-tile-grids"
curl.exe "http://localhost:8000/api/worlds/world-test-003/map/render-location-grids"
curl.exe "http://localhost:8000/api/worlds/world-test-003/map/render-wilderness-tile-grid?gx=-2&gy=-2"
curl.exe "http://localhost:8000/api/worlds/world-test-003/locations/{location_uid}/render-grid"



