# AI Radar Voice Agent — Setup Guide (v3)

A voice agent for your AI Radar Google Docs. You tap a mic, ask a question out
loud ("any urgent fixes today?", "what's trending on Hugging Face?", "what
should I upgrade in the Shaastra chatbot?"), and it answers out loud — grounded
ONLY in that day's content of your two docs:

- **AI Radar — Daily AI News Log**
- **AI Radar — Project Model Upgrade Tracker**

## How it works (and why the popup exists)

Google Apps Script sidebars run inside a sandboxed cross-origin iframe
(`*.googleusercontent.com`), and Chrome blocks microphone access from that
iframe — **no permission setting on your side can change this**. That's why
tapping the mic in the old sidebar always said "Mic error: not-allowed".

So the agent is split in two:

```
🎙 Voice popup (separate window)   ← mic + spoken answers — top-level page, mic works
        ↕ postMessage
📄 Sidebar (inside the doc)        ← bridge: calls the server code (Gemini + doc reading)
```

Keep the sidebar open while the popup is in use. The API key never leaves your
Google account (script properties, server-side).

## Install (once, ~2 minutes)

1. Open the **AI Radar — Daily AI News Log** Google Doc (installing in this
   one doc is enough — the agent reads BOTH docs regardless of which doc it's
   opened from).
2. Menu: **Extensions → Apps Script**.
3. In the default `Code.gs`: select all, delete, and paste the full contents of
   `AI_Radar_Voice_Agent.gs`.
4. Make sure the project has these two HTML files (left sidebar → **+** next to
   Files → **HTML**; the name is what matters, Apps Script adds `.html` itself):
   - `Sidebar` — paste the contents of `AI_Radar_Voice_Sidebar.html`
   - `Popup` — paste the contents of `AI_Radar_Voice_Popup.html`
5. Press **Ctrl+S** (save), then **reload the Google Doc tab** in your browser.
6. A new menu **🎙 AI Radar Voice** now appears in the doc's menu bar.

## First use

1. Click **🎙 AI Radar Voice → Set Gemini API key…** and paste a key from
   https://aistudio.google.com/apikey (free tier is enough).
2. Click **🎙 AI Radar Voice → Open voice agent**. The sidebar opens.
3. In the sidebar, tap **🎙 Start voice conversation**. A small voice window
   pops up. If Chrome asks about the microphone, choose **Allow**.
4. Tap the red mic and speak. The agent transcribes you, thinks, answers out
   loud in the popup, and then **automatically listens again** — so you can
   have a back-and-forth conversation. Tap the mic (now ⏹) to stop.
5. Typed questions also work — directly in the sidebar or in the popup.

## Notes and tips

- **Browser:** Chrome on desktop (voice input uses the Web Speech API).
- **Popups must be allowed** for the doc — if the voice window doesn't appear,
  allow popups via the icon in Chrome's address bar and tap the button again.
- **Keep the sidebar open** while the popup is in use — it's the bridge to the
  server code. Closing it disconnects the popup.
- **Language:** English (India) / English (US) / Hindi selector for both
  recognition and the spoken reply.
- **"That day's docs":** every morning the pipeline prepends the newest dated
  section to the news log; the voice agent automatically uses the newest
  `##`-dated section plus the full tracker, so it always answers about *today*.
- **Privacy:** questions and doc text go to the Gemini API under your own key.
  Nothing is stored anywhere else.

## Troubleshooting

| Problem | Fix |
|---|---|
| "Mic error: not-allowed" in the popup | Click the mic/tune icon at the left of the popup's address bar → Microphone → Allow, then tap the mic again. If there's no icon, close the popup, reopen it, and choose Allow when Chrome asks |
| Old "Mic error: not-allowed" in the sidebar | That's the old version — replace all three files (Code.gs, Sidebar, Popup) with the current ones; voice no longer runs in the sidebar |
| "Popup blocked" | Allow popups for the page (icon in the address bar), tap Start voice again |
| "The AI Radar sidebar was closed" (in popup) | Reopen 🎙 AI Radar Voice → Open voice agent in the doc, then use the popup |
| "No API key set" | Menu → Set Gemini API key… |
| Nothing happens on mic tap | Use Chrome desktop; check the browser/system isn't muted |
| "Voice input is not supported" | Your browser lacks the Web Speech API — use the text box, or open in Chrome |
| Gemini API error 400/429 | Check the key is valid / free-tier quota reset (per-minute limits) |
