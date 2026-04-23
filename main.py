import os
import socket
import psycopg2
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI()

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5000")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASS", "postgres")
DB_NAME = os.getenv("DB_NAME", "postgres")


def get_db():
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


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index():
    app_ip = socket.gethostbyname(socket.gethostname())

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            "CREATE TABLE IF NOT EXISTS hits (id SERIAL PRIMARY KEY, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);"
        )
        cur.execute("INSERT INTO hits DEFAULT VALUES;")
        cur.execute("SELECT COUNT(*) FROM hits;")
        hits = cur.fetchone()[0]

        cur.execute("SELECT inet_server_addr();")
        db_leader_ip = cur.fetchone()[0]

        conn.close()

        return f"""
        <html>
            <head><meta http-equiv="refresh" content="3"></head>
            <body style="font-family: Arial; text-align: center; margin-top: 50px;">
                <h1>🚀 FastAPI + AWS/OpenStack Hybrid Demo</h1>
                <h2>☁️ Web Node (AWS): <span style="color: blue;">{app_ip}</span></h2>
                <h2>🐘 DB Leader (OpenStack): <span style="color: green;">{db_leader_ip}</span></h2>
                <h3>📊 Total Visits (DB): {hits}</h3>
                <p><i>Kill an OpenStack DB VM to test Patroni Failover! (Switch time: ~35s)</i></p>
                <p><i>Kill an AWS Web VM to test the Auto Scaling Group!</i></p>
            </body>
        </html>
        """

    except Exception as e:
        return f"""
        <html>
            <head><meta http-equiv="refresh" content="2"></head>
            <body style="font-family: Arial; text-align: center; margin-top: 50px; background-color: #ffe6e6;">
                <h1>🔄 DB Failover in Progress...</h1>
                <h2>☁️ Web Node (AWS): <span style="color: blue;">{app_ip}</span></h2>
                <h3 style="color: red;">The OpenStack cluster is electing a new DB Leader!</h3>
                <p>Please wait, the page refreshes automatically. (Around 30 seconds)</p>
                <hr>
                <small style="color: gray;">Internal Error: {e}</small>
            </body>
        </html>
        """