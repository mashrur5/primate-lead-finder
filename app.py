import requests
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse

from config import EXPORT_FILE, OLLAMA_MODEL, OLLAMA_URL, PORT
from pipeline import run_pipeline
from storage.seen import get_seen_count, reset_seen


app = FastAPI(title="Primate Lead Pipeline")


@app.get("/")
def root():
    return {
        "name": "Primate Lead Pipeline",
        "endpoints": {
            "pipeline": "/api/pipeline?sources=yc,github&batches=W25,S24,W24&max=15&model=llama3",
            "seen": "/api/seen",
            "status": "/api/status",
            "download": "/download/leads",
        },
    }


@app.get("/api/pipeline")
def pipeline_stream(request: Request):
    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(run_pipeline(request.query_params), media_type="text/event-stream", headers=headers)


@app.get("/api/seen")
def seen_count():
    return {"count": get_seen_count()}


@app.post("/api/seen/reset")
def reset_seen_route():
    reset_seen()
    return {"ok": True}


@app.get("/download/leads")
def download_leads():
    if not EXPORT_FILE.exists():
        return JSONResponse({"error": "Run the pipeline first."}, status_code=404)
    return FileResponse(EXPORT_FILE, filename="primate_leads.xlsx", media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@app.get("/api/status")
def status():
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=3)
        response.raise_for_status()
        models = [model.get("name") for model in response.json().get("models", []) if model.get("name")]
        return {"ok": True, "models": models}
    except requests.RequestException:
        return JSONResponse({"ok": False, "error": "Ollama not running", "defaultModel": OLLAMA_MODEL}, status_code=503)


if __name__ == "__main__":
    print()
    print(f"Primate Lead Pipeline running at http://localhost:{PORT}")
    print("Sources: YC + GitHub + Product Hunt")
    print(f"Ollama: {OLLAMA_URL} | Model: {OLLAMA_MODEL}")
    print()
    uvicorn.run("app:app", host="0.0.0.0", port=PORT)
