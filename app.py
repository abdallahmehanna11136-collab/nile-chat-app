from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO, emit, join_room
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
    # جدول الرسائل معدل ليدعم الخصوصية بناءً على رقم الهاتف
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            room TEXT,
            sender TEXT,
            sender_phone TEXT,
            content TEXT,
            msg_type TEXT,
            timestamp REAL,
            reply_to TEXT
        )
    ''')
    # جدول الغرف
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS created_rooms (
            room_name TEXT PRIMARY KEY,
            room_type TEXT,
            password TEXT,
            creator_phone TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/service-worker.js')
def sw():
    return send_from_directory(app.static_folder, 'service-worker.js')

@socketio.on('get_all_rooms')
def handle_get_rooms(data):
    phone = data.get('phone')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # جلب الغرف العامة + الغرف الخاصة التي تنتمي لهذا الهاتف فقط أو المحادثات السرية الخاصة به
    cursor.execute('SELECT room_name, room_type FROM created_rooms WHERE room_type="public" OR creator_phone=?', (phone,))
    rows = cursor.fetchall()
    rooms = [{'name': row[0], 'type': row[1]} for row in rows]
    conn.close()
    emit('receive_rooms_list', rooms)

@socketio.on('create_new_room_server')
def handle_create_room(data):
    name = data.get('name')
    room_type = data.get('type')
    password = data.get('password', '')
    creator = data.get('phone')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO created_rooms (room_name, room_type, password, creator_phone) VALUES (?, ?, ?, ?)', 
                       (name, room_type, password, creator))
        conn.commit()
        conn.close()
        # تحديث القائمة للمستخدم الحالي
        handle_get_rooms({'phone': creator})
    except sqlite3.Error:
        conn.close()
        emit('room_error', 'اسم الغرفة موجود بالفعل!')

@socketio.on('join_room')
def handle_join_room(data):
    room = data.get('room')
    password = data.get('password', '')
    phone = data.get('phone')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT room_type, password, creator_phone FROM created_rooms WHERE room_name = ?', (room,))
    row = cursor.fetchone()
    
    # حماية الغرف الخاصة والمحادثات المباشرة
    if row:
        if row[0] == 'private' and row[1] != password:
            conn.close()
            emit('auth_failed', {'room': room})
            return
        if '-' in room and phone not in room: # شات سري مباشر ليس ملكه
            conn.close()
            return

    join_room(room)
    
    # جلب الرسائل الخاصة بهذه الغرفة فقط
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
    room = data.get('room')
    sender = data.get('sender')
    phone = data.get('phone')
    content = data.get('content')
    msg_type = data.get('type', 'text')
    reply_to = data.get('reply_to', '')
    timestamp = time.time()
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO messages (id, room, sender, sender_phone, content, msg_type, timestamp, reply_to) VALUES (?, ?, ?, ?, ?, ?, ?, ?)', 
                       (msg_id, room, sender, phone, content, msg_type, timestamp, reply_to))
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
    cursor.execute('DELETE FROM messages WHERE id = ?', (msg_id,))
    conn.commit()
    conn.close()
    emit('delete_message_client', {'id': msg_id}, room=room)

@socketio.on('edit_message_server')
def handle_edit_message(data):
    msg_id = data.get('id')
    room = data.get('room')
    new_content = data.get('content')
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
