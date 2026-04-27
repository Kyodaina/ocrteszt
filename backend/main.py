from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.main_state import processing_service, state_service, ws_hub
from backend.routes.api import router as api_router

app = FastAPI(title="Local OCR + Semantic Analysis")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@app.on_event("startup")
async def startup_event() -> None:
    await processing_service.start_worker()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await ws_hub.connect(websocket)
    await websocket.send_json({"kind": "snapshot", "payload": state_service.snapshot()})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_hub.disconnect(websocket)


app.mount("/output", StaticFiles(directory="output"), name="output")
