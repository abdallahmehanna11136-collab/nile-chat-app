from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO, emit, join_room
import os
import sqlite3
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'nile_chat_secret_key_123'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

DB_PATH = os.path.join('/tmp', 'chat_database.db') if os.path.exists('/tmp') else 'chat_database.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            room TEXT,
            sender TEXT,
            phone TEXT,
            text TEXT,
            timestamp REAL,
            reply_to TEXT,
            is_edited INTEGER DEFAULT 0,
            is_forwarded INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            phone TEXT PRIMARY KEY,
            avatar TEXT,
            status_text TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/manifest.json')
def manifest():
    return send_from_directory(app.static_folder or 'static', 'manifest.json')

@app.route('/service-worker.js')
def sw():
    return send_from_directory(app.static_folder or 'static', 'service-worker.js')

@socketio.on('join')
def on_join(data):
    room = data.get('room', 'العامة')
    join_room(room)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, room, sender, text, reply_to, is_edited, is_forwarded FROM messages WHERE room = ? ORDER BY timestamp ASC", (room,))
    rows = cursor.fetchall()
    
    cursor.execute("SELECT phone, avatar, status_text FROM profiles")
    p_rows = cursor.fetchall()
    profiles = {r[0]: {"avatar": r[1], "status": r[2]} for r in p_rows}
    conn.close()
    
    history = []
    for r in rows:
        history.append({
            "id": r[0], "room": r[1], "sender": r[2], "text": r[3],
            "reply_to": r[4], "is_edited": bool(r[5]), "is_forwarded": bool(r[6])
        })
    
    emit('chat_history', {'messages': history, 'profiles': profiles})

@socketio.on('send_message')
def on_send_message(data):
    msg_id = data['id']
    room = data['room']
    sender = data['sender']
    phone = data['phone']
    text = data['text']
    reply_to = data.get('reply_to', None)
    is_forwarded = data.get('is_forwarded', 0)
    ts = time.time()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO messages (id, room, sender, phone, text, timestamp, reply_to, is_forwarded) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (msg_id, room, sender, phone, text, ts, reply_to, is_forwarded))
    conn.commit()
    conn.close()
    
    emit('message', {
        'id': msg_id, 'room': room, 'sender': sender, 'phone': phone,
        'text': text, 'reply_to': reply_to, 'is_edited': False, 'is_forwarded': bool(is_forwarded)
    }, room=room)

@socketio.on('edit_message')
def on_edit_message(data):
    msg_id = data['id']
    room = data['room']
    new_text = data['text']
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE messages SET text = ?, is_edited = 1 WHERE id = ?", (new_text, msg_id))
    conn.commit()
    conn.close()
    
    emit('message_edited', {'id': msg_id, 'room': room, 'text': new_text}, room=room)

@socketio.on('delete_message')
def on_delete_message(data):
    msg_id = data['id']
    room = data['room']
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()
    
    emit('message_deleted', {'id': msg_id, 'room': room}, room=room)

@socketio.on('update_profile')
def on_update_profile(data):
    phone = data['phone']
    avatar = data.get('avatar', '')
    status_text = data.get('status', '')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO profiles (phone, avatar, status_text) VALUES (?, ?, ?)", (phone, avatar, status_text))
    conn.commit()
    conn.close()
    
    emit('profile_updated', {'phone': phone, 'avatar': avatar, 'status': status_text}, broadcast=True)
@socketio.on('call_user')
def on_call_user(data):
    room = data.get('room', 'العامة')
    emit('call_received', data, room=room, include_self=False)

@socketio.on('answer_call')
def on_answer_call(data):
    room = data.get('room', 'العامة')
    emit('call_answered', data, room=room, include_self=False)

@socketio.on('ice_candidate')
def on_ice_candidate(data):
    room = data.get('room', 'العامة')
    emit('ice_candidate_received', data, room=room, include_self=False)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000)
