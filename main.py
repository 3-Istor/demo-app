"""Modern Hybrid Cloud Demo App - FastAPI + PostgreSQL"""
import os
import socket
from datetime import datetime
from typing import Optional
import psycopg2
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
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


def init_db():
    """Initialize database tables"""
    try:
        conn = get_db()
        cur = conn.cursor()
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
        conn.close()
    except Exception:
        pass


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    init_db()


@app.get("/health")
def health():
    """Health check endpoint"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/status")
def get_status() -> SystemStatus:
    """Get current system status"""
    app_ip = socket.gethostbyname(socket.gethostname())

    try:
        conn = get_db()
        cur = conn.cursor()

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
            db_status=f"failover: {str(e)[:50]}",
            messages_count=0
        )


@app.get("/api/messages")
def get_messages(limit: int = 20):
    """Get recent messages"""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT author, content, created_at 
            FROM messages 
            ORDER BY created_at DESC 
            LIMIT %s
        """, (limit,))
        messages = [
            {
                "author": row[0],
                "content": row[1],
                "created_at": row[2].isoformat()
            }
            for row in cur.fetchall()
        ]
        conn.close()
        return {"messages": messages}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB unavailable: {e}")


@app.post("/api/messages")
def post_message(message: Message):
    """Post a new message"""
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO messages (author, content) VALUES (%s, %s) RETURNING id;",
            (message.author, message.content)
        )
        msg_id = cur.fetchone()[0]
        conn.close()
        return {"id": msg_id, "status": "posted"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB unavailable: {e}")


@app.get("/", response_class=HTMLResponse)
def index():
    """Main page with modern UI"""
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
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
            color: #333;
        }
        
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .header {
            text-align: center;
            color: white;
            margin-bottom: 30px;
            animation: fadeIn 0.5s;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }
        
        .cards {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .card {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            animation: slideUp 0.5s;
        }
        
        .status-badge {
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            font-weight: bold;
            margin: 5px 0;
        }
        
        .status-ok { background: #10b981; color: white; }
        .status-error { background: #ef4444; color: white; }
        
        .metric {
            font-size: 2.5em;
            font-weight: bold;
            color: #667eea;
            margin: 10px 0;
        }
        
        .label {
            color: #666;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .ip-display {
            font-family: 'Courier New', monospace;
            background: #f3f4f6;
            padding: 10px;
            border-radius: 8px;
            margin: 10px 0;
            font-size: 1.1em;
        }
        
        .message-section {
            background: white;
            border-radius: 15px;
            padding: 25px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }
        
        .message-form {
            display: flex;
            flex-direction: column;
            gap: 15px;
            margin-bottom: 30px;
        }
        
        input, textarea {
            padding: 12px;
            border: 2px solid #e5e7eb;
            border-radius: 8px;
            font-size: 1em;
            transition: border 0.3s;
        }
        
        input:focus, textarea:focus {
            outline: none;
            border-color: #667eea;
        }
        
        button {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            padding: 12px 30px;
            border-radius: 8px;
            font-size: 1em;
            font-weight: bold;
            cursor: pointer;
            transition: transform 0.2s;
        }
        
        button:hover {
            transform: translateY(-2px);
        }
        
        .messages-list {
            max-height: 400px;
            overflow-y: auto;
        }
        
        .message-item {
            background: #f9fafb;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 10px;
            border-left: 4px solid #667eea;
        }
        
        .message-author {
            font-weight: bold;
            color: #667eea;
            margin-bottom: 5px;
        }
        
        .message-time {
            font-size: 0.8em;
            color: #999;
        }
        
        .pulse {
            animation: pulse 2s infinite;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        @keyframes slideUp {
            from { transform: translateY(20px); opacity: 0; }
            to { transform: translateY(0); opacity: 1; }
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        
        .footer {
            text-align: center;
            color: white;
            margin-top: 30px;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 Hybrid Cloud Demo</h1>
            <p>AWS + OpenStack • FastAPI + PostgreSQL + Patroni</p>
        </div>
        
        <div class="cards">
            <div class="card">
                <div class="label">☁️ Web Server (AWS)</div>
                <div class="ip-display" id="web-ip">Loading...</div>
                <div class="status-badge status-ok">Active</div>
            </div>
            
            <div class="card">
                <div class="label">🐘 DB Leader (OpenStack)</div>
                <div class="ip-display" id="db-ip">Loading...</div>
                <div class="status-badge" id="db-status">Checking...</div>
            </div>
            
            <div class="card">
                <div class="label">📊 Total Hits</div>
                <div class="metric" id="hits">0</div>
                <div class="label">💬 Messages</div>
                <div class="metric" id="msg-count">0</div>
            </div>
        </div>
        
        <div class="message-section">
            <h2 style="margin-bottom: 20px;">💬 Message Board</h2>
            
            <form class="message-form" id="msg-form">
                <input type="text" id="author" placeholder="Your name (optional)" maxlength="50">
                <textarea id="content" placeholder="Your message..." rows="3" maxlength="500" required></textarea>
                <button type="submit">Send</button>
            </form>
            
            <h3 style="margin-bottom: 15px;">Recent Messages</h3>
            <div class="messages-list" id="messages">
                <p style="text-align: center; color: #999;">Loading...</p>
            </div>
        </div>
        
        <div class="footer">
            <p>💡 Test resilience: Stop a DB VM to see Patroni failover (~35s)</p>
            <p>🔄 Auto-refresh every 3 seconds</p>
        </div>
    </div>
    
    <script>
        async function updateStatus() {
            try {
                const res = await fetch('/api/status');
                const data = await res.json();
                
                document.getElementById('web-ip').textContent = data.web_ip;
                document.getElementById('db-ip').textContent = data.db_leader_ip || 'N/A';
                document.getElementById('hits').textContent = data.total_hits;
                document.getElementById('msg-count').textContent = data.messages_count;
                
                const statusEl = document.getElementById('db-status');
                if (data.db_status === 'connected') {
                    statusEl.textContent = 'Connected';
                    statusEl.className = 'status-badge status-ok';
                } else {
                    statusEl.textContent = 'Failover...';
                    statusEl.className = 'status-badge status-error pulse';
                }
            } catch (e) {
                console.error('Status update failed:', e);
            }
        }
        
        async function loadMessages() {
            try {
                const res = await fetch('/api/messages');
                const data = await res.json();
                const container = document.getElementById('messages');
                
                if (data.messages.length === 0) {
                    container.innerHTML = '<p style="text-align: center; color: #999;">No messages yet</p>';
                    return;
                }
                
                container.innerHTML = data.messages.map(msg => `
                    <div class="message-item">
                        <div class="message-author">${msg.author}</div>
                        <div>${msg.content}</div>
                        <div class="message-time">${new Date(msg.created_at).toLocaleString('en-US')}</div>
                    </div>
                `).join('');
            } catch (e) {
                document.getElementById('messages').innerHTML = '<p style="color: red;">Loading error</p>';
            }
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
                    document.getElementById('author').value = '';
                    loadMessages();
                    updateStatus();
                }
            } catch (e) {
                alert("Error sending message");
            }
        });
        
        updateStatus();
        loadMessages();
        setInterval(() => {
            updateStatus();
            loadMessages();
        }, 3000);
    </script>
</body>
</html>
"""