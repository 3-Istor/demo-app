"""Modern Hybrid Cloud Demo App - FastAPI + PostgreSQL"""
import os
import socket
from datetime import datetime
from typing import Optional
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

app = FastAPI(title="Hybrid Cloud Demo", version="2.0")

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5000")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "postgres")
DB_NAME = os.getenv("DB_NAME", "postgres")


class Message(BaseModel):
    """Message model for user submissions"""
    content: str = Field(..., min_length=1, max_length=500)
    author: str = Field(default="Anonymous", max_length=50)


class SystemStatus(BaseModel):
    """System status response model"""
    web_ip: str
    db_leader_ip: Optional[str]
    total_hits: int
    db_status: str
    messages_count: int


def get_db():
    """Get database connection with timeout"""
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        dbname=DB_NAME,
        connect_timeout=2
    )
    conn.autocommit = True
    return conn


def ensure_tables(cur):
    """Ensure database schema exists"""
    cur.execute("""
        CREATE TABLE IF NOT EXISTS hits (
            id SERIAL PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            author VARCHAR(50) DEFAULT 'Anonymous',
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    """)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/status")
def get_status() -> SystemStatus:
    app_ip = socket.gethostbyname(socket.gethostname())
    try:
        conn = get_db()
        cur = conn.cursor()
        ensure_tables(cur)
        cur.execute("INSERT INTO hits DEFAULT VALUES;")
        cur.execute("SELECT COUNT(*) FROM hits;")
        hits = cur.fetchone()[0]
        cur.execute("SELECT inet_server_addr();")
        db_leader_ip = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM messages;")
        msg_count = cur.fetchone()[0]
        conn.close()

        return SystemStatus(
            web_ip=app_ip,
            db_leader_ip=str(db_leader_ip) if db_leader_ip else None,
            total_hits=hits,
            db_status="connected",
            messages_count=msg_count
        )
    except Exception as e:
        return SystemStatus(
            web_ip=app_ip,
            db_leader_ip=None,
            total_hits=0,
            db_status=f"Failover: {str(e)[:60]}",
            messages_count=0
        )


@app.get("/api/messages")
def get_messages(limit: int = 20):
    try:
        conn = get_db()
        cur = conn.cursor()
        ensure_tables(cur)
        cur.execute("SELECT author, content, created_at FROM messages ORDER BY created_at DESC LIMIT %s", (limit,))
        messages = [{"author": row[0], "content": row[1], "created_at": row[2].isoformat()} for row in cur.fetchall()]
        conn.close()
        return {"messages": messages}
    except Exception:
        return {"messages": []}


@app.post("/api/messages")
def post_message(message: Message):
    try:
        conn = get_db()
        cur = conn.cursor()
        ensure_tables(cur)
        cur.execute("INSERT INTO messages (author, content) VALUES (%s, %s) RETURNING id;", (message.author, message.content))
        msg_id = cur.fetchone()[0]
        conn.close()
        return {"id": msg_id, "status": "posted"}
    except Exception:
        raise HTTPException(status_code=503, detail="DB Unavailable")


@app.get("/", response_class=HTMLResponse)
def index():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Hybrid Cloud Demo</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
            transition: all 0.8s ease;
        }
        
        /* SUBTLE FAILOVER STYLE */
        body.failover-mode {
            background: linear-gradient(135deg, #374151 0%, #111827 100%);
        }
        
        .failover-banner {
            display: none;
            background: #fff7ed;
            color: #9a3412;
            padding: 12px;
            border-radius: 8px;
            text-align: center;
            margin-bottom: 20px;
            border: 1px solid #fdba74;
            font-weight: bold;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }
        body.failover-mode .failover-banner { display: block; }
        
        .container { max-width: 1100px; margin: 0 auto; }
        .header { text-align: center; color: white; margin-bottom: 30px; }
        .header h1 { font-size: 2.2em; text-shadow: 0 2px 4px rgba(0,0,0,0.2); }
        
        .cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .card { 
            background: white; border-radius: 12px; padding: 20px; 
            box-shadow: 0 4px 20px rgba(0,0,0,0.1); 
            transition: all 0.5s ease;
            border: 2px solid transparent;
        }
        
        /* Highlight only the DB card during failover */
        body.failover-mode .db-card {
            border-color: #f97316;
            box-shadow: 0 0 15px rgba(249, 115, 22, 0.4);
            animation: borderPulse 2s infinite;
        }
        
        .status-badge { display: inline-block; padding: 4px 12px; border-radius: 20px; font-size: 0.8em; font-weight: bold; margin-top: 8px; }
        .status-ok { background: #dcfce7; color: #166534; }
        .status-error { background: #fee2e2; color: #991b1b; }
        
        .metric { font-size: 2em; font-weight: bold; color: #4f46e5; margin: 5px 0; }
        .label { color: #6b7280; font-size: 0.8em; text-transform: uppercase; font-weight: 600; }
        .ip-display { font-family: monospace; background: #f3f4f6; padding: 8px; border-radius: 6px; margin: 8px 0; font-size: 1em; }
        
        .message-section { background: white; border-radius: 12px; padding: 25px; box-shadow: 0 4px 20px rgba(0,0,0,0.1); }
        .message-form { display: flex; flex-direction: column; gap: 12px; margin-bottom: 25px; }
        input, textarea { padding: 10px; border: 1px solid #d1d5db; border-radius: 6px; }
        button { 
            background: #4f46e5; color: white; border: none; padding: 10px; 
            border-radius: 6px; font-weight: bold; cursor: pointer; 
        }
        button:disabled { background: #9ca3af; cursor: not-allowed; }
        
        .messages-list { max-height: 300px; overflow-y: auto; }
        .message-item { background: #f9fafb; padding: 12px; border-radius: 8px; margin-bottom: 8px; border-left: 4px solid #4f46e5; }
        .message-author { font-weight: bold; color: #4f46e5; font-size: 0.9em; }
        .message-time { font-size: 0.75em; color: #9ca3af; }

        @keyframes borderPulse {
            0% { border-color: #f97316; }
            50% { border-color: #fdba74; }
            100% { border-color: #f97316; }
        }
        
        .footer { text-align: center; color: rgba(255,255,255,0.8); margin-top: 30px; font-size: 0.85em; line-height: 1.6; }
        body.failover-mode .footer { color: #9ca3af; }
    </style>
</head>
<body>
    <div class="container">
        <div class="failover-banner" id="failover-banner">
            ⚠️ DATABASE FAILOVER IN PROGRESS - ELECTING NEW LEADER...
        </div>

        <div class="header">
            <h1>🚀 Hybrid Cloud Demo</h1>
            <p style="opacity: 0.9;">AWS + OpenStack Resilience Test</p>
        </div>
        
        <div class="cards">
            <div class="card">
                <div class="label">☁️ Web Server (AWS)</div>
                <div class="ip-display" style="color: #2563eb;" id="web-ip">Loading...</div>
                <div class="status-badge status-ok">Active</div>
            </div>
            
            <div class="card db-card">
                <div class="label">🐘 DB Leader (OpenStack)</div>
                <div class="ip-display" style="color: #059669;" id="db-ip">Loading...</div>
                <div class="status-badge" id="db-status">Checking...</div>
            </div>
            
            <div class="card">
                <div class="label">📊 Metrics</div>
                <div style="display: flex; gap: 20px;">
                    <div><div class="metric" id="hits">0</div><div class="label">Hits</div></div>
                    <div><div class="metric" id="msg-count">0</div><div class="label">Msgs</div></div>
                </div>
            </div>
        </div>
        
        <div class="message-section">
            <form class="message-form" id="msg-form">
                <div style="display: grid; grid-template-columns: 1fr 2fr; gap: 10px;">
                    <input type="text" id="author" placeholder="Name" maxlength="50">
                    <input type="text" id="content" placeholder="Type a message..." maxlength="500" required>
                </div>
                <button type="submit" id="submit-btn">Post to Database</button>
            </form>
            <div class="messages-list" id="messages"></div>
        </div>
        
        <div class="footer">
            <p>🔄 Automatic refresh every 3 seconds</p>
            <p><i>Failover test: Stop a DB node to trigger Patroni leader election (~15s)</i></p>
        </div>
    </div>
    
    <script>
        let isFailover = false;

        async function updateStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                
                document.getElementById('web-ip').textContent = data.web_ip;
                document.getElementById('db-ip').textContent = data.db_leader_ip || 'N/A';
                document.getElementById('hits').textContent = data.total_hits;
                document.getElementById('msg-count').textContent = data.messages_count;
                
                const statusEl = document.getElementById('db-status');
                const submitBtn = document.getElementById('submit-btn');

                if (data.db_status === 'connected') {
                    isFailover = false;
                    document.body.classList.remove('failover-mode');
                    statusEl.textContent = 'CONNECTED';
                    statusEl.className = 'status-badge status-ok';
                    submitBtn.disabled = false;
                } else {
                    isFailover = true;
                    document.body.classList.add('failover-mode');
                    statusEl.textContent = 'FAILOVER';
                    statusEl.className = 'status-badge status-error';
                    submitBtn.disabled = true;
                }
            } catch (e) { console.error(e); }
        }
        
        async function loadMessages() {
            if (isFailover) return;
            try {
                const res = await fetch('/api/messages');
                const data = await res.json();
                const container = document.getElementById('messages');
                
                if (data.messages.length === 0) {
                    container.innerHTML = '<p style="text-align: center; color: #9ca3af;">No messages yet</p>';
                    return;
                }
                
                container.innerHTML = data.messages.map(msg => `
                    <div class="message-item">
                        <div class="message-author">${msg.author}</div>
                        <div style="margin: 4px 0;">${msg.content}</div>
                        <div class="message-time">${new Date(msg.created_at).toLocaleTimeString()}</div>
                    </div>
                `).join('');
            } catch (e) { console.error(e); }
        }
        
        document.getElementById('msg-form').addEventListener('submit', async (e) => {
            e.preventDefault();
            const author = document.getElementById('author').value || 'Anonymous';
            const content = document.getElementById('content').value;
            try {
                const res = await fetch('/api/messages', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ author, content })
                });
                if (res.ok) {
                    document.getElementById('content').value = '';
                    loadMessages();
                    updateStatus();
                }
            } catch (e) { alert("DB Error"); }
        });
        
        updateStatus(); loadMessages();
        setInterval(() => { updateStatus(); loadMessages(); }, 3000);
    </script>
</body>
</html>
"""