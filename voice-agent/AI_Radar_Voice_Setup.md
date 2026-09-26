# AI Radar Voice Agent — Setup Guide

A voice agent that lives inside your AI Radar Google Docs. You tap a mic in the doc,
ask a question out loud ("any urgent fixes today?", "what's trending on Hugging Face?",
"what should I upgrade in the Shaastra chatbot?"), and it answers out loud — grounded
ONLY in that day's content of your two docs:

- **AI Radar — Daily AI News Log**
- **AI Radar — Project Model Upgrade Tracker**

No server, no deployment, no monthly cost. It runs on:
- Chrome's built-in speech recognition + speech synthesis (free, in-browser)
- Gemini API free tier (uses `gemini-3.8-flash` — the same upgrade your tracker recommends)

## Install (once, ~2 minutes)

1. Open the **AI Radar — Daily AI News Log** Google Doc (installing in this one doc is
   enough — the agent reads BOTH docs regardless of which doc it's opened from).
2. Menu: **Extensions → Apps Script**.
3. In the default `Code.gs`: select all, delete, and paste the full contents of
   `AI_Radar_Voice_Agent.gs`.
4. In the Apps Script editor left sidebar, click **+** next to Files → **HTML**.
   Name it exactly `Sidebar` (Apps Script will make it `Sidebar.html`). Paste the full
   contents of `AI_Radar_Voice_Sidebar.html` into it.
5. Press **Ctrl+S** (save), then **reload the Google Doc tab** in your browser.
6. A new menu **🎙 AI Radar Voice** now appears in the doc's menu bar.

## First use

1. Click **🎙 AI Radar Voice → Set Gemini API key…** and paste a key from
   https://aistudio.google.com/apikey (free tier is enough). The key is stored in your
   Google account's script properties — it is never written into the document.
2. Click **🎙 AI Radar Voice → Open voice agent**. The sidebar opens on the right.
3. Allow microphone access when Chrome asks.
4. Tap the red mic button and speak. The agent transcribes you, thinks, answers out
   loud, and then **automatically starts listening again** — so you can have a
   back-and-forth conversation. Tap the mic (now ⏹) to stop.

## Notes and tips

- **Browser:** Chrome on desktop is required for voice input/output (it uses the Web
  Speech API). In other browsers, use the "type your question" box — you'll still get
  the spoken answer wherever speech synthesis works.
- **Language:** the sidebar has an English (India) / English (US) / Hindi selector for
  both recognition and the spoken reply.
- **"That day's docs":** every morning the cron pipeline prepends the newest dated
  section to the news log; the voice agent automatically uses the newest `##`-dated
  section plus the full tracker, so it always answers about *today*.
- **Updating the script later:** just re-open Extensions → Apps Script, edit, save,
  reload the doc.
- **Privacy:** questions and doc text go to the Gemini API under your own key.
  Nothing is stored anywhere else; the API key lives in your script properties.

## Troubleshooting

| Problem | Fix |
|---|---|
| "No API key set" | Menu → Set Gemini API key… |
| Mic error: not-allowed | Click the lock/tune icon in Chrome's address bar → allow microphone → reload |
| Nothing happens on mic tap | Use Chrome desktop; check the browser isn't muted |
| "Voice input is not supported" | Your browser lacks the Web Speech API — use the text box, or open in Chrome |
| Gemini API error 400/429 | Check the key is valid / free-tier quota reset (per-minute limits) |
