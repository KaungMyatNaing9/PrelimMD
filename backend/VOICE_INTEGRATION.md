# Voice STT — Integration Guide

## How it works (big picture)

```
Browser mic
  → audio chunks over WebSocket
    → backend bridges to Deepgram live API
      → Deepgram detects pause (300ms silence)
        → fires final transcript
          → backend calls LLM (your code goes here)
            → sends response back to browser
```

---

## For the Frontend 

### 1. Open a WebSocket connection

```js
const ws = new WebSocket("ws://localhost:8000/voice/stream")
```

### 2. Stream mic audio

```js
const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
const recorder = new MediaRecorder(stream, { mimeType: "audio/webm;codecs=opus" })

recorder.ondataavailable = (e) => {
  if (e.data.size > 0 && ws.readyState === WebSocket.OPEN) {
    e.data.arrayBuffer().then(buf => ws.send(buf))
  }
}

recorder.start(250) // send a chunk every 250ms
```

### 3. Handle messages from the server

```js
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data)

  if (msg.type === "partial") {
    // Person still speaking — show live text in gray
    // { type: "partial", transcript: "...", confidence: 0.95 }
  }

  if (msg.type === "final") {
    // Pause detected — full utterance + LLM response ready
    // { type: "final", transcript: "...", confidence: 0.99, llm_response: "..." }
  }

  if (msg.type === "error") {
    // { type: "error", message: "..." }
  }
}
```

### 4. Stop recording

```js
recorder.stop()
stream.getTracks().forEach(t => t.stop())
ws.close()
```

> **Working example:** `backend/test_stream.html` is a complete browser implementation you can copy from. Run it with `python3 -m http.server 8080` from the backend folder.

---

## For the AI/LLM integration

Find `_call_llm()` in `backend/app/services/voice_service.py` and replace the placeholder body:

```python
async def _call_llm(transcript: str) -> str:
    # TODO:— replace this with your real LLM call
    return f"[LLM placeholder] Received utterance: {transcript}"
```

- receives one complete utterance (a sentence — fires on each pause)
- must return a string (the AI's reply)
- is `async` so you can `await` inside it

**Example with OpenAI:**

```python
async def _call_llm(transcript: str) -> str:
    response = await openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a medical intake assistant..."},
            {"role": "user", "content": transcript},
        ]
    )
    return response.choices[0].message.content
```

The return value gets sent to the browser as `llm_response` in every `final` message.

---

## Environment setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add DEEPGRAM_API_KEY
uvicorn app.main:app --reload
```

---

## Quick test checklist

- [ ] Backend running on port 8000
- [ ] Open `http://localhost:8080/test_stream.html`
- [ ] Click Start → speak → see partial text → pause → see final + LLM response
