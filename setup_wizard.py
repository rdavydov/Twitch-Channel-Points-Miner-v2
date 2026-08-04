"""
setup_wizard.py – Minimal Flask setup server.

Started by main.py when neither settings.json nor run.py is found (e.g. because
Dokploy / Docker single-file mounts didn't work).  Serves a plain web page that
lets you paste either a settings.json blob or a run.py blob, saves it to disk,
then re-execs the process so main.py finds the config on the next boot.
"""

import hmac
import json
import os
import sys
import threading

# Suppress Flask startup banner
os.environ.setdefault("WERKZEUG_RUN_MAIN", "false")

from flask import Flask, Response, request

_SETUP_PORT = int(os.environ.get("SETUP_PORT", os.environ.get("ANALYTICS_PORT", "5005")))
# Bind host is configurable so the wizard need not be exposed on all interfaces.
# Defaults to 0.0.0.0 for container/Dokploy bootstrap compatibility.
_SETUP_HOST = os.environ.get("SETUP_HOST", "0.0.0.0")
# Optional shared secret. When set, the save endpoint (which can write an
# arbitrary run.py that is later executed) requires a matching X-Setup-Token
# header, closing the unauthenticated-RCE window while no config exists.
_SETUP_TOKEN = os.environ.get("SETUP_TOKEN", "").strip()

_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Twitch Miner – Setup</title>
<style>
  *,*::before,*::after{box-sizing:border-box;}
  :root{
    --bg:#11111b;--surface:#1e1e2e;--border:#45475a;
    --accent:#cba6f7;--text:#cdd6f4;--muted:#9da2b8;
    --green:#a6e3a1;--yellow:#f9e2af;--red:#f38ba8;
  }
  html,body{margin:0;padding:0;background:var(--bg);color:var(--text);
    font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
    min-height:100vh;display:flex;align-items:center;justify-content:center;}
  .card{background:var(--surface);border:1px solid var(--border);border-radius:10px;
    padding:2rem;max-width:720px;width:94%;box-shadow:0 8px 32px rgba(0,0,0,.5);}
  h1{margin:0 0 .3rem;font-size:1.4rem;color:var(--accent);}
  .sub{color:var(--muted);font-size:.85rem;margin-bottom:1.5rem;}
  .tabs{display:flex;gap:.5rem;margin-bottom:1rem;}
  .tab{padding:.4rem .9rem;border-radius:6px;border:1px solid var(--border);
    background:transparent;color:var(--muted);cursor:pointer;font-size:.85rem;transition:.15s;}
  .tab.active{background:var(--accent);color:#11111b;border-color:var(--accent);font-weight:600;}
  label{display:block;font-size:.8rem;color:var(--muted);margin-bottom:.35rem;}
  textarea{width:100%;height:340px;background:#181825;color:var(--text);
    border:1px solid var(--border);border-radius:6px;padding:.6rem .75rem;
    font-family:'Fira Code','Cascadia Code',monospace;font-size:.8rem;
    resize:vertical;outline:none;transition:.15s;}
  textarea:focus{border-color:var(--accent);}
  .btn{display:inline-flex;align-items:center;gap:.4rem;padding:.55rem 1.2rem;
    border-radius:6px;border:none;font-size:.9rem;font-weight:600;cursor:pointer;
    background:var(--accent);color:#11111b;transition:.15s;}
  .btn:hover{filter:brightness(1.1);}
  .btn:disabled{opacity:.45;cursor:default;}
  #status{margin-top:.9rem;min-height:1.4rem;font-size:.85rem;padding:.4rem .6rem;
    border-radius:5px;display:none;}
  #status.ok{display:block;background:rgba(166,227,161,.15);color:var(--green);border:1px solid var(--green);}
  #status.err{display:block;background:rgba(243,139,168,.15);color:var(--red);border:1px solid var(--red);}
  #status.info{display:block;background:rgba(203,166,247,.13);color:var(--accent);border:1px solid var(--accent);}
  .hint{font-size:.75rem;color:var(--muted);margin-top:.4rem;}
</style>
</head>
<body>
<div class="card">
  <h1>🔧 Twitch Miner – First-Time Setup</h1>
  <p class="sub">No configuration file was found (settings.json / run.py mount may have failed).
  Paste your config below and click <b>Save &amp; Start</b> — the miner will boot automatically.</p>

  <div class="tabs">
    <button class="tab active" onclick="setMode('json')">settings.json</button>
    <button class="tab" onclick="setMode('runpy')">run.py</button>
  </div>

  <label id="ta-label">Paste settings.json content</label>
  <textarea id="ta" placeholder='{"username": "your_twitch_name", ...}'></textarea>
  <p class="hint" id="hint">JSON format — same as <code>settings.json</code>.
    Copy from your local <code>settings.json</code> or the config editor.</p>

  <button class="btn" onclick="save()" id="savebtn">💾 Save &amp; Start</button>
  <div id="status"></div>
</div>

<script>
var mode = 'json';
function setMode(m) {
  mode = m;
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  event.target.classList.add('active');
  if (m === 'json') {
    document.getElementById('ta-label').textContent = 'Paste settings.json content';
    document.getElementById('ta').placeholder = '{"username": "your_twitch_name", ...}';
    document.getElementById('hint').innerHTML = 'JSON format — same as <code>settings.json</code>.';
  } else {
    document.getElementById('ta-label').textContent = 'Paste run.py content';
    document.getElementById('ta').placeholder = 'from TwitchChannelPointsMiner import TwitchChannelPointsMiner\\n...';
    document.getElementById('hint').innerHTML = 'Legacy <code>run.py</code> — will be converted to settings.json automatically.';
  }
}
function setStatus(cls, msg) {
  var el = document.getElementById('status');
  el.className = cls; el.textContent = msg;
}
function save() {
  var text = document.getElementById('ta').value.trim();
  if (!text) { setStatus('err', 'Nothing to save — textarea is empty.'); return; }
  if (mode === 'json') {
    try { JSON.parse(text); } catch(e) { setStatus('err', 'Invalid JSON: ' + e.message); return; }
  }
  var btn = document.getElementById('savebtn');
  btn.disabled = true;
  setStatus('info', 'Saving…');
  var _tok = new URLSearchParams(window.location.search).get('token') || '';
  var _url = '/api/setup/save' + (_tok ? ('?token=' + encodeURIComponent(_tok)) : '');
  fetch(_url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({mode: mode, content: text})
  }).then(r => r.json()).then(data => {
    if (data.ok) {
      setStatus('ok', '✅ Saved! Miner is starting — this page will become the dashboard in a few seconds…');
      setTimeout(() => { window.location.href = '/'; }, 5000);
    } else {
      setStatus('err', '❌ ' + (data.error || 'Unknown error'));
      btn.disabled = false;
    }
  }).catch(e => { setStatus('err', '❌ Network error: ' + e); btn.disabled = false; });
}
</script>
</body>
</html>
"""


def run_setup_wizard():
    """
    Start a blocking Flask setup server.  Returns only after the user submits a
    valid config, at which point the process re-execs itself so main.py can pick
    up the newly written file.
    """
    app = Flask(__name__)

    # Suppress all Flask/Werkzeug request logs
    import logging
    logging.getLogger("werkzeug").setLevel(logging.ERROR)

    _ready = threading.Event()

    @app.route("/")
    def index():
        return Response(_HTML, mimetype="text/html")

    @app.route("/api/setup/save", methods=["POST"])
    def setup_save():
        try:
            if _SETUP_TOKEN:
                provided = (request.headers.get("X-Setup-Token", "")
                            or request.args.get("token", "")).strip()
                if not hmac.compare_digest(provided, _SETUP_TOKEN):
                    return {"ok": False, "error": "Unauthorized"}, 401
            body = request.get_json(force=True, silent=True) or {}
            mode = body.get("mode", "json")
            content = body.get("content", "").strip()

            if not content:
                return {"ok": False, "error": "Content is empty"}

            if mode == "json":
                # Validate JSON
                try:
                    json.loads(content)
                except json.JSONDecodeError as e:
                    return {"ok": False, "error": f"Invalid JSON: {e}"}
                os.makedirs("settings", exist_ok=True)
                dest = "settings/settings.json"
                with open(dest, "w", encoding="utf-8") as fh:
                    fh.write(content)
            elif mode == "runpy":
                os.makedirs("settings", exist_ok=True)
                dest = "settings/run.py"
                with open(dest, "w", encoding="utf-8") as fh:
                    fh.write(content)
            else:
                return {"ok": False, "error": f"Unknown mode: {mode}"}

            print(f"[setup] Config saved to {dest} — restarting…")
            # Signal the main thread to restart after a tiny delay
            t = threading.Timer(1.0, _do_restart)
            t.daemon = True
            t.start()

            return {"ok": True, "file": dest}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    @app.route("/health")
    def health():
        return {"status": "setup-wizard"}

    def _do_restart():
        """Re-exec this process so main.py picks up the new config file."""
        os.execv(sys.executable, [sys.executable] + sys.argv)

    print(f"[setup] No config found. Setup wizard running at http://{_SETUP_HOST}:{_SETUP_PORT}/")
    print(f"[setup] Open the URL in your browser, paste settings.json or run.py, and click Save & Start.")
    if _SETUP_TOKEN:
        print("[setup] Auth enabled — append ?token=<SETUP_TOKEN> to the URL.")
    elif _SETUP_HOST == "0.0.0.0":
        print("[setup] WARNING: wizard is unauthenticated and bound to 0.0.0.0. "
              "It can write/execute an arbitrary run.py. Set SETUP_TOKEN and/or "
              "SETUP_HOST=127.0.0.1 if the port is network-reachable.")
    app.run(host=_SETUP_HOST, port=_SETUP_PORT, threaded=True, debug=False, use_reloader=False)
