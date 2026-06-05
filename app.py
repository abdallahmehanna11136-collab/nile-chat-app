from flask import Flask, render_template, request, make_response, jsonify
from flask_socketio import SocketIO, emit, join_room
import os
import sqlite3
import time
from groq import Groq

# ربط الذكاء الاصطناعي (NileAI)
groq_client = Groq(api_key='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')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'nile_chat_mega_v1'
# رفع حد حجم الملفات المسموح برفعها (صور، فيديوهات، ملفات) لـ 50 ميجا
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
socketio = SocketIO(app, cors_allowed_origins="*", max_decode_size=50 * 1024 * 1024)

DB_PATH = os.path.join('/tmp', 'nile_mega_chat.db') if os.path.exists('/tmp') else 'nile_mega_chat.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # قاعدة بيانات متطورة تدعم التعديل، الحذف، ونوع الملف (الميزات: 2, 7, 14, 24)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            room TEXT,
            sender TEXT,
            phone TEXT,
            text TEXT,
            timestamp REAL,
            file_type TEXT DEFAULT 'text',
            file_name TEXT DEFAULT ''
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    response = make_response(render_template('index.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response

@socketio.on('join_room')
def on_join_room(data):
    room = data.get('room', 'public_room')
    join_room(room)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, room, sender, text, file_type, file_name FROM messages WHERE room = ? ORDER BY timestamp ASC", (room,))
    rows = cursor.fetchall()
    conn.close()
    
    history = []
    for r in rows:
        history.append({
            "id": r[0], "room": r[1], "sender": r[2], "text": r[3], "file_type": r[4], "file_name": r[5]
        })
    emit('chat_history', {'messages': history})

@socketio.on('message')
def handle_message_event(data):
    msg_id = data.get('id', f"msg-{int(time.time() * 1000)}")
    room = data.get('room', 'public_room')
    sender = data.get('sender', 'مستخدم')
    phone = data.get('phone', '')
    text = data.get('text', '')
    file_type = data.get('file_type', 'text')
    file_name = data.get('file_name', '')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (id, room, sender, phone, text, timestamp, file_type, file_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (msg_id, room, sender, phone, text, time.time(), file_type, file_name))
    conn.commit()
    conn.close()

    emit('message', {
        'id': msg_id, 'room': room, 'sender': sender, 'phone': phone, 'text': text, 'file_type': file_type, 'file_name': file_name
    }, room=room, include_self=False)

    # ميزة الذكاء الاصطناعي (الميزة 5 و 19 والمنشن التنافسي)
    if room == 'NileAI_room' or (room == 'public_room' and '@NileAI' in text):
        emit('bot_status', {'status': 'جاري التفكير والرد...'}, room=room)
        try:
            prompt_content = text.replace('@NileAI', '').strip()
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "أنت NileAI الذكي في نايل شات. ترد بالعامية المصرية وبإيجاز شديد."},
                    {"role": "user", "content": prompt_content if prompt_content else "أهلاً بك!"}
                ],
                model="llama3-8b-8192",
            )
            reply_text = chat_completion.choices[0].message.content
            bot_msg_id = f"msg-bot-{int(time.time() * 1000)}"
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (id, room, sender, phone, text, timestamp, file_type) VALUES (?, ?, ?, ?, ?, ?, 'text')",
                           (bot_msg_id, room, "NileAI 🤖", "bot-system", reply_text, time.time()))
            conn.commit()
            conn.close()
            
            emit('bot_status', {'status': 'متصل حالياً'}, room=room)
            emit('message', {
                'id': bot_msg_id, 'room': room, 'sender': "NileAI 🤖", 'phone': "bot-system", 'text': reply_text, 'file_type': 'text'
            }, room=room)
        except Exception:
            emit('bot_status', {'status': 'متصل حالياً'}, room=room)

# ميزة حذف الرسائل لايف ومن قاعدة البيانات (الميزة 2)
@socketio.on('delete_message')
def handle_delete(data):
    msg_id = data.get('id')
    room = data.get('room')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()
    emit('message_deleted', {'id': msg_id}, room=room)

# ميزة تعديل الرسائل لايف ومن قاعدة البيانات (الميزة 2)
@socketio.on('edit_message')
def handle_edit(data):
    msg_id = data.get('id')
    room = data.get('room')
    new_text = data.get('text')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE messages SET text = ? WHERE id = ?", (new_text, msg_id))
    conn.commit()
    conn.close()
    emit('message_edited', {'id': msg_id, 'text': new_text}, room=room)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
