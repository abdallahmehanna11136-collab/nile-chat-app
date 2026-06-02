from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import sqlite3
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'nile_chat_secret_key_123'

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

DB_PATH = os.path.join('/tmp', 'chat_database.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            room TEXT,
            sender TEXT,
            content TEXT,
            msg_type TEXT,
            timestamp REAL,
            reply_to TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS created_rooms (
            room_name TEXT PRIMARY KEY,
            room_type TEXT,
            password TEXT
        )
    ''')
    cursor.execute("INSERT OR IGNORE INTO created_rooms (room_name, room_type, password) VALUES ('الرئيسية العامة', 'public', '')")
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/service-worker.js')
def sw():
    return app.send_static_file('service-worker.js')

@socketio.on('get_all_rooms')
def handle_get_rooms():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT room_name, room_type FROM created_rooms')
    rows = cursor.fetchall()
    rooms = [{'name': row[0], 'type': row[1]} for row in rows]
    conn.close()
    emit('receive_rooms_list', rooms)

@socketio.on('create_new_room_server')
def handle_create_room(data):
    name = data.get('name')
    room_type = data.get('type')
    password = data.get('password', '')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO created_rooms (room_name, room_type, password) VALUES (?, ?, ?)', (name, room_type, password))
        conn.commit()
        conn.close()
        handle_get_rooms()
    except sqlite3.Error:
        conn.close()
        emit('room_error', 'اسم الغرفة موجود بالفعل!')

@socketio.on('join_room')
def handle_join_room(data):
    room = data.get('room', 'الرئيسية العامة')
    password = data.get('password', '')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT room_type, password FROM created_rooms WHERE room_name = ?', (room,))
    row = cursor.fetchone()
    
    if row and row[0] == 'private' and row[1] != password:
        conn.close()
        emit('auth_failed', {'room': room})
        return

    join_room(room)
    cursor.execute('SELECT id, sender, content, msg_type, timestamp, reply_to FROM messages WHERE room = ?', (room,))
    rows = cursor.fetchall()
    conn.close()
    
    for row in rows:
        emit('message', {
            'id': row[0], 'sender': row[1], 'content': row[2], 
            'type': row[3], 'timestamp': row[4], 'reply_to': row[5], 'room': room
        }, to=request.sid)

@socketio.on('new_message')
def handle_new_message(data):
    msg_id = data.get('id')
    room = data.get('room', 'الرئيسية العامة')
    sender = data.get('sender')
    content = data.get('content')
    msg_type = data.get('type', 'text')
    reply_to = data.get('reply_to', '')
    timestamp = time.time()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO messages (id, room, sender, content, msg_type, timestamp, reply_to) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                       (msg_id, room, sender, content, msg_type, timestamp, reply_to))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error: {e}")
    finally:
        conn.close()
    
    data['timestamp'] = timestamp
    emit('message', data, room=room)

@socketio.on('delete_message_server')
def handle_delete_message(data):
    room = data.get('room')
    msg_id = data.get('id')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT timestamp FROM messages WHERE id = ?', (msg_id,))
    row = cursor.fetchone()
    if row and (time.time() - row[0] <= 900):
        cursor.execute('UPDATE messages SET content = ? WHERE id = ?', (new_content, msg_id))
        conn.commit()
        emit('edit_message_client', {'id': msg_id, 'content': new_content}, room=room)
    conn.close()

@socketio.on('call_user')
def handle_call(data): emit('call_received', {'from': data['from'], 'offer': data['offer'], 'type': data['type']}, room=data['room'], include_self=False)
@socketio.on('answer_call')
def handle_answer(data): emit('call_answered', {'answer': data['answer']}, room=data['room'], include_self=False)
@socketio.on('ice_candidate')
def handle_ice(data): emit('ice_candidate', data['candidate'], room=data['room'], include_self=False)
@socketio.on('end_call')
def handle_end_call(data): emit('end_call', room=data['room'], include_self=False)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
