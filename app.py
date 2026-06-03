from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO, emit, join_room
import os
import sqlite3
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'nile_chat_secret_key_123'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 🛠️ تصحيح الخطأ الفني: استخدام os.path.join المظبوطة لمنع كراش Render
DB_PATH = os.path.join('/tmp', 'chat_database.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # جدول الرسائل: يدعم التعديل، الحذف، التحويل، الرد، والصحين
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            room TEXT,
            sender TEXT,
            sender_phone TEXT,
            content TEXT,
            msg_type TEXT,
            timestamp REAL,
            reply_to TEXT,
            is_forwarded INTEGER DEFAULT 0,
            is_read INTEGER DEFAULT 0
        )
    ''')
    # جدول الغرف والمجموعات
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
    return send_from_directory(app.static_folder or 'static', 'service-worker.js')

@socketio.on('get_all_rooms')
def handle_get_rooms(data):
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
    creator = data.get('phone')
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO created_rooms VALUES (?, ?, ?, ?)', (name, room_type, password, creator))
        conn.commit()
        conn.close()
        handle_get_rooms({'phone': creator})
    except sqlite3.Error:
        emit('room_error', 'اسم الغرفة موجود بالفعل!')

@socketio.on('join_room')
def handle_join_room(data):
    room = data.get('room')
    password = data.get('password', '')
    phone = data.get('phone')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT room_type, password FROM created_rooms WHERE room_name = ?', (room,))
    row = cursor.fetchone()
    
    if row and row[0] == 'private' and row[1] != password:
        conn.close()
        emit('auth_failed', {'room': room})
        return
        
    if '-' in room and phone not in room:
        conn.close()
        return
        
    # 🔒 حماية وعزل غرف الذكاء الاصطناعي بناءً على رقم هاتف المستخدم لمنع التداخل
    if room.startswith('AI-Chat-') and room != f"AI-Chat-{phone}":
        conn.close()
        return

    join_room(room)
    
    # تحديث علامات الصح لتصبح مقروءة عند دخول الطرف الآخر
    cursor.execute('UPDATE messages SET is_read = 1 WHERE room = ? AND sender_phone != ?', (room, phone))
    conn.commit()
    
    cursor.execute('SELECT id, sender, content, msg_type, timestamp, reply_to, is_forwarded, is_read, sender_phone FROM messages WHERE room = ?', (room,))
    rows = cursor.fetchall()
    conn.close()
    
    for r in rows:
        emit('message', {
            'id': r[0], 'sender': r[1], 'content': r[2], 'type': r[3],
            'timestamp': r[4], 'reply_to': r[5], 'is_forwarded': r[6], 'is_read': r[7], 'phone': r[8], 'room': room
        })

@socketio.on('new_message')
def handle_new_message(data):
    msg_id = data.get('id')
    room = data.get('room')
    sender = data.get('sender')
    phone = data.get('phone')
    content = data.get('content')
    msg_type = data.get('type', 'text')
    reply_to = data.get('reply_to', '')
    is_forwarded = data.get('is_forwarded', 0)
    ts = time.time()
    
    if room.startswith('AI-Chat-') and room != f"AI-Chat-{phone}":
        return
        
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)', 
                   (msg_id, room, sender, phone, content, msg_type, ts, reply_to, is_forwarded))
    conn.commit()
    conn.close()
    
    emit('message', {
        'id': msg_id, 'room': room, 'sender': sender, 'phone': phone,
        'content': content, 'type': msg_type, 'reply_to': reply_to, 
        'is_forwarded': is_forwarded, 'is_read': 0, 'timestamp': ts
    }, to=room)

    # 🤖 معالجة رد بوت الذكاء الاصطناعي (NileAI) وإرساله للمستخدم صاحب الرقم فقط
    if room == f"AI-Chat-{phone}":
        ai_response = f"أهلاً بك يا فنان في نظام نايل الذكي. شاتك هنا مؤمن ومعزول تماماً ومستحيل مستخدم تاني يشوفه على السيرفر. رسالتك هي: {content}"
        ai_msg_id = f"ai-{int(time.time()*1000)}"
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)', 
                       (ai_msg_id, room, 'NileAI', 'AI-System', ai_response, 'text', ts+1, '', 0))
        conn.commit()
        conn.close()
        
        emit('message', {
            'id': ai_msg_id, 'room': room, 'sender': '🤖 NileAI', 'phone': 'AI-System',
            'content': ai_response, 'type': 'text', 'reply_to': '', 
            'is_forwarded': 0, 'is_read': 1, 'timestamp': ts+1
        }, to=room)

@socketio.on('mark_as_read')
def handle_mark_read(data):
    room = data.get('room')
    phone = data.get('phone')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('UPDATE messages SET is_read = 1 WHERE room = ? AND sender_phone != ?', (room, phone))
    conn.commit()
    conn.close()
    emit('messages_read_update', {'room': room}, to=room)

@socketio.on('delete_message_server')
def handle_delete_message(data):
    msg_id = data.get('id')
    room = data.get('room')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM messages WHERE id = ?', (msg_id,))
    conn.commit()
    conn.close()
    emit('delete_message_client', {'id': msg_id}, to=room)

@socketio.on('edit_message_server')
def handle_edit_message(data):
    msg_id = data.get('id')
    room = data.get('room')
    content = data.get('content')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT timestamp FROM messages WHERE id = ?', (msg_id,))
    row = cursor.fetchone()
    if row and (time.time() - row[0] <= 900): # صلاحية التعديل 15 دقيقة
        cursor.execute('UPDATE messages SET content = ? WHERE id = ?', (content, msg_id))
        conn.commit()
        emit('edit_message_client', {'id': msg_id, 'content': content}, to=room)
    conn.close()

@socketio.on('ice_candidate')
def handle_ice(data):
    emit('ice_candidate', data.get('candidate'), to=data.get('room'), include_self=False)

@socketio.on('call_user')
def handle_call(data):
    emit('call_received', data, to=data.get('room'), include_self=False)

@socketio.on('answer_call')
def handle_answer(data):
    emit('call_answered', data, to=data.get('room'), include_self=False)

@socketio.on('end_call')
def handle_end(data):
    emit('end_call', to=data.get('room'))

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
