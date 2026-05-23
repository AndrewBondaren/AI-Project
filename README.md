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