# Chat UI config

The chat UI (ChatRaw) is run as part of the root Docker stack. This folder holds **config only** — no separate docker-compose, no custom UI code. ChatRaw is a lightweight, OpenAI-compatible chat front-end (~60MB memory; much smaller image than Open WebUI).

## Setup (one-time)

**Option A – Configure via script (recommended)**  
ChatRaw has no env vars for API URL; we configure it via its API so the connection is saved in the project:

1. From **repo root**: `docker compose up -d`
2. Set your LM Studio model ID in `.env`: `CHATRAW_DEFAULT_MODEL_ID=<model-id>` (the name LM Studio shows for the loaded model).
3. Run: `.\ui\scripts\configure-chatraw.ps1`
4. Open **http://localhost:8080** — the default chat model is already set (API URL `http://api:8000/openapi/v1`).

**Option B – Configure in the UI**  
After opening **http://localhost:8080**: Settings → Model Settings → set **API Base URL** to `http://api:8000/openapi/v1`, **Model ID** to your model name, then Verify and Save. If the API runs on the host instead of Docker, use `http://host.docker.internal:8000/openapi/v1`.

## Running the stack

From the **repo root**:

```powershell
docker compose up -d
```

Open the UI at **http://localhost:8080**. Settings and chat history are stored in the `chatraw_data` volume.
