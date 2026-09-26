/**
 * AI RADAR — VOICE AGENT (Google Apps Script, container-bound)
 * ------------------------------------------------------------
 * Gives you a "🎙 AI Radar Voice" menu inside this Google Doc.
 * The sidebar listens to your question with your microphone,
 * answers it using TODAY'S content of both AI Radar docs
 * (Daily News Log + Project Model Upgrade Tracker), and speaks
 * the answer back. After every answer it re-listens automatically.
 *
 * SETUP (2 minutes):
 *   1. In the doc: Extensions → Apps Script.
 *   2. Delete everything in the default Code.gs and paste this file in.
 *   3. Click + next to "Files" → HTML → name it exactly: Sidebar
 *      then paste the contents of AI_Radar_Voice_Sidebar.html in it.
 *   4. Save (Ctrl+S), then reload the Google Doc tab.
 *   5. First use: menu 🎙 AI Radar Voice → "Set Gemini API key…"
 *      (free key from aistudio.google.com/apikey — stored securely in
 *      your Google account's script properties, never inside the doc).
 *
 * Requires Chrome desktop for voice input/output. A text box is
 * included as fallback. See AI_Radar_Voice_Setup.md for details.
 */

var NEWS_DOC_ID = '1E_cJ53dGq1a1AQ4YEBhLzbDtcGFwZwTwVHYfzxCyguA';
var TRACKER_DOC_ID = '1NEyBKO0ig9Jx-M28scfEZHAkmsj0Uryv2LrGNk6A848';
var GEMINI_MODEL = 'gemini-3.8-flash';

function onOpen() {
  DocumentApp.getUi()
    .createMenu('🎙 AI Radar Voice')
    .addItem('Open voice agent', 'showSidebar')
    .addItem('Set Gemini API key…', 'promptApiKey')
    .addToUi();
}

function onInstall(e) {
  onOpen();
}

function showSidebar() {
  var html = HtmlService.createHtmlOutputFromFile('Sidebar').setTitle('AI Radar Voice');
  DocumentApp.getUi().showSidebar(html);
}

function promptApiKey() {
  var ui = DocumentApp.getUi();
  var res = ui.prompt(
    '🎙 AI Radar Voice',
    'Paste your Google AI Studio (Gemini) API key.\nGet one free at aistudio.google.com/apikey',
    ui.ButtonSet.OK_CANCEL
  );
  if (res.getSelectedButton() === ui.Button.OK && res.getResponseText()) {
    PropertiesService.getUserProperties().setProperty('GEMINI_API_KEY', res.getResponseText().trim());
    ui.alert('API key saved. It is stored in your account\u2019s script properties — never in the document itself. You can now use the voice agent.');
  }
}

/**
 * Builds the context the agent answers from:
 * today's (newest) dated section of the news log + the full tracker.
 */
function getDocsContext() {
  var newsFull = DocumentApp.openById(NEWS_DOC_ID).getBody().getText();
  var tracker = DocumentApp.openById(TRACKER_DOC_ID).getBody().getText();

  // Newest daily entry = from the FIRST "## " heading to the next "## " heading.
  var lines = newsFull.split('\n');
  var started = false;
  var out = [];
  for (var i = 0; i < lines.length; i++) {
    if (/^##\s/.test(lines[i])) {
      if (started) break; // reached the next (older) day's heading
      started = true;
    }
    if (started) out.push(lines[i]);
  }
  var todayNews = out.join('\n').trim();

  return { todayNews: todayNews, tracker: tracker };
}

/**
 * Called from the sidebar with the user's (spoken or typed) question.
 * Returns a concise, speakable answer grounded in today's docs.
 */
function ask(question) {
  var key = PropertiesService.getUserProperties().getProperty('GEMINI_API_KEY');
  if (!key) {
    return 'No API key set yet. Open the AI Radar Voice menu and choose Set Gemini API key.';
  }

  var ctx;
  try {
    ctx = getDocsContext();
  } catch (err) {
    return 'I could not read the AI Radar docs: ' + err.message;
  }

  var systemPrompt =
    'You are the AI Radar voice assistant. The user asks spoken questions about their daily AI Radar docs. ' +
    'Answer using ONLY the context below. Be concise: two to four spoken sentences, plain language, ' +
    'no markdown, no lists, no emojis, no URLs unless asked. If the answer is not in the context, ' +
    'say so briefly and suggest opening the doc directly.\n\n' +
    '=== TODAY\u2019S AI RADAR NEWS ENTRY ===\n' + ctx.todayNews + '\n\n' +
    '=== PROJECT MODEL UPGRADE TRACKER ===\n' + ctx.tracker;

  var payload = {
    system_instruction: { parts: [{ text: systemPrompt }] },
    contents: [{ role: 'user', parts: [{ text: question }] }],
    generationConfig: { temperature: 0.3, maxOutputTokens: 300 }
  };

  var resp = UrlFetchApp.fetch(
    'https://generativelanguage.googleapis.com/v1beta/models/' + GEMINI_MODEL +
      ':generateContent?key=' + encodeURIComponent(key),
    {
      method: 'post',
      contentType: 'application/json',
      payload: JSON.stringify(payload),
      muteHttpExceptions: true
    }
  );

  var code = resp.getResponseCode();
  var body = {};
  try { body = JSON.parse(resp.getContentText()); } catch (e) {}

  if (code !== 200) {
    return 'Gemini API error ' + code + ': ' + (body.error && body.error.message ? body.error.message : 'unknown error');
  }

  var cand = body.candidates && body.candidates[0];
  var parts = cand && cand.content && cand.content.parts;
  var text = parts ? parts.map(function (p) { return p.text || ''; }).join('') : '';
  return text || 'I could not generate an answer.';
}
