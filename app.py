from flask import Flask, render_template, make_response, jsonify, request
from flask_socketio import SocketIO, emit, join_room
import sqlite3
import time
from groq import Groq

# ربط عميل الذكاء الاصطناعي
groq_client = Groq(api_key='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')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'nile_chat_ultra_max_system'
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024
socketio = SocketIO(app, cors_allowed_origins="*", max_decode_size=200 * 1024 * 1024)

DB_PATH = 'nile_chat_database.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, room TEXT, sender TEXT, phone TEXT, text TEXT, 
            timestamp REAL, file_type TEXT DEFAULT 'text', file_name TEXT DEFAULT '', reactions TEXT DEFAULT ''
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stories (
            id TEXT PRIMARY KEY, sender TEXT, phone TEXT, text TEXT, file_type TEXT, timestamp REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id TEXT PRIMARY KEY, name TEXT, creator TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            phone TEXT PRIMARY KEY, name TEXT, last_seen REAL, sid TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    response = make_response(render_template('index.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

@socketio.on('register_user')
def handle_register(data):
    phone = data.get('phone')
    name = data.get('name')
    if phone and name:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO users (phone, name, last_seen, sid) VALUES (?, ?, ?, ?)",
                       (phone, name, time.time(), request.sid))
        conn.commit()
        conn.close()
        join_room(f"user_{phone}")

@socketio.on('join_room')
def on_join_room(data):
    room = data.get('room', 'public_room')
    join_room(room)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, room, sender, text, file_type, file_name, reactions FROM messages WHERE room = ? ORDER BY timestamp ASC", (room,))
    rows = cursor.fetchall()
    conn.close()
    history = [{"id": r[0], "room": r[1], "sender": r[2], "text": r[3], "file_type": r[4], "file_name": r[5], "reactions": r[6]} for r in rows]
    emit('chat_history', {'messages': history})

@socketio.on('message')
def handle_message_event(data):
    msg_id = data.get('id', f"msg-{int(time.time() * 1000)}")
    room = data.get('room', 'public_room')
    sender = data.get('sender', 'مستخدم')
    phone = data.get('phone', '')
    text = data.get('text', '')
    file_type = data.get('file_type', 'text')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (id, room, sender, phone, text, timestamp, file_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (msg_id, room, sender, phone, text, time.time(), file_type))
    conn.commit()
    conn.close()

    emit('message', {'id': msg_id, 'room': room, 'sender': sender, 'phone': phone, 'text': text, 'file_type': file_type, 'reactions': ''}, room=room)

    # تشغيل رد الذكاء الاصطناعي الفوري دون تعليق
    if room == 'NileAI_room' or (room == 'public_room' and '@NileAI' in text):
        try:
            prompt_content = text.replace('@NileAI', '').strip()
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "أنت NileAI الذكي. ترد بالعامية المصرية وبإيجاز شديد وعميق وبدون مقدمات."},
                    {"role": "user", "content": prompt_content if prompt_content else "أهلاً بك!"}
                ],
            model="llama3-8b-8192",
            )
            reply_text = chat_completion.choices[0].message.content
            bot_msg_id = f"msg-bot-{int(time.time() * 1000)}"
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (id, room, sender, phone, text, timestamp, file_type) VALUES (?, ?, 'NileAI 🤖', 'bot-system', ?, ?, 'text')",
                           (bot_msg_id, room, reply_text, time.time()))
            conn.commit()
            conn.close()
            
            emit('message', {'id': bot_msg_id, 'room': room, 'sender': "NileAI 🤖", 'phone': "bot-system", 'text': reply_text, 'file_type': 'text', 'reactions': ''}, room=room)
        except Exception as e:
            print("AI Error:", e)

@socketio.on('add_story')
def handle_story(data):
    story_id = f"story-{int(time.time() * 1000)}"
    sender = data.get('sender')
    phone = data.get('phone')
    text = data.get('text')
    file_type = data.get('file_type', 'text')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM stories WHERE phone = ?", (phone,))
    cursor.execute("INSERT INTO stories (id, sender, phone, text, file_type, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                   (story_id, sender, phone, text, file_type, time.time()))
    conn.commit()
    conn.close()
    emit('new_story_alert', broadcast=True)

@socketio.on('get_stories')
def get_stories():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    day_ago = time.time() - 86400
    cursor.execute("SELECT id, sender, text, file_type FROM stories WHERE timestamp > ? ORDER BY timestamp DESC", (day_ago,))
    rows = cursor.fetchall()
    conn.close()
    stories = [{"id": r[0], "sender": r[1], "text": r[2], "file_type": r[3]} for r in rows]
    emit('stories_list', {'stories': stories})

@socketio.on('create_group')
def create_group(data):
    g_id = f"group_{int(time.time() * 1000)}"
    g_name = data.get('name')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO groups (id, name, creator) VALUES (?, ?, 'user')", (g_id, g_name))
    conn.commit()
    conn.close()
    emit('group_created_alert', broadcast=True)

@socketio.on('get_groups')
def get_groups():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM groups")
    rows = cursor.fetchall()
    conn.close()
    groups = [{"id": r[0], "name": r[1]} for r in rows]
    emit('groups_list', {'groups': groups})

@socketio.on('call_signal')
def handle_call_signal(data):
    target_phone = data.get('target_phone')
    if target_phone:
        emit('call_signal', data, room=f"user_{target_phone}", include_self=False)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
