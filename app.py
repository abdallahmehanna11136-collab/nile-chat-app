from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO, emit, join_room
import os
import sqlite3
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'nile_chat_secret_key_123'

# تكبير حجم بافر البيانات لـ 50 ميجا عشان يرفع الصور والفيديوهات الصغيره كـ Base64 مستقر
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', max_http_buffer_size=50 * 1024 * 1024)

DB_PATH = os.path.join('/tmp', 'chat_database.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # جدول الرسائل محدث ليدعم نوع الرسالة (نص، صورة، فيديو) والردود والخصوصية
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
    return send_from_directory(app.static_folder if app.static_folder else '.', 'service-worker.js')

@socketio.on('get_all_rooms')
def handle_get_rooms(data):
    phone = data.get('phone')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # جلب الغرف العامة + الغرف الخاصة التي تنتمي لهذا الهاتف فقط (خصوصية تامة)
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
        handle_get_rooms({'phone': creator})
    except sqlite3.Error:
        conn.close()
        emit('room_error', 'إسم الغرفة موجود بالفعل!')

@socketio.on('join_room')
def handle_join_room(data):
    room = data.get('room')
    password = data.get('password', '')
    phone = data.get('phone')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT room_type, password, creator_phone FROM created_rooms WHERE room_name=?', (room,))
    row = cursor.fetchone()
    
    if row:
        if row[0] == 'private' and row[1] != password:
            conn.close()
            emit('auth_failed', {'room': room})
            return
    
    # حماية وعزل الشات السري المباشر (رقم التليفون)
    if '-' in room and phone not in room:
        conn.close()
        return
        
    join_room(room)
    
    # جلب الأرشيف الخاص بهذه الغرفة فقط لمنع تداخل الرسائل والخصوصية المطلقة
    cursor.execute('SELECT id, sender, content, msg_type, timestamp, reply_to FROM messages WHERE room = ? ORDER BY timestamp ASC', (room,))
    rows = cursor.fetchall()
    conn.close()
    
    for row in rows:
        emit('message', {
            'id': row[0], 'sender': row[1], 'content': row[2],
            'type': row[3], 'timestamp': row[4], 'reply_to': row[5], 'room': room
        })

# 💥 تعديل حدث استقبال الرسائل والملفات والـ AI وعزلها بالكامل 💥
@socketio.on('new_message')
def handle_new_message(data):
    msg_id = data.get('id')
    room = data.get('room')
    sender = data.get('sender')
    phone = data.get('phone')
    content = data.get('content')
    msg_type = data.get('type', 'text') # نص، صورة، فيديو، ملف
    reply_to = data.get('reply_to', '')
    timestamp = time.time()
    
    # حفظ الرسالة أو الملف في قاعدة البيانات
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO messages (id, room, sender, sender_phone, content, msg_type, timestamp, reply_to) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                       (msg_id, room, sender, phone, content, msg_type, timestamp, reply_to))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Database Error: {e}")
    finally:
        conn.close()
        
    data['timestamp'] = timestamp
    # بث الرسالة/الملف لأعضاء هذه الغرفة فقط (To Room) تحقيقاً للخصوصية التامة والعزل
    emit('message', data, to=room)

    # 🤖 ميزة الذكاء الاصطناعي التلقائي (الرد السريع في نفس الغرفة وعزل الرد)
    if content and (content.startswith('/') or 'يا ذكاء' in content or 'ai' in content.lower()):
        ai_response_id = f"ai-{int(time.time()*1000)}"
        ai_reply = "أهلاً بك! أنا مساعدك الذكي في Nile Chat. جاري معالجة طلبك وتحديث الأيقونات الآن لتنطلق طيارة! 🚀"
        
        # حفظ رد الـ AI في قاعدة البيانات
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO messages (id, room, sender, sender_phone, content, msg_type, timestamp, reply_to) VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                       (ai_response_id, room, 'المساعد الذكي 🤖', '0000', ai_reply, 'text', time.time(), msg_id))
        conn.commit()
        conn.close()
        
        # بث رد الـ AI لأفراد الغرفة دي بس
        emit('message', {
            'id': ai_response_id, 'room': room, 'sender': 'المساعد الذكي 🤖',
            'phone': '0000', 'content': ai_reply, 'type': 'text',
            'timestamp': time.time(), 'reply_to': msg_id
        }, to=room)

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
    new_content = data.get('content')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT timestamp FROM messages WHERE id = ?', (msg_id,))
    row = cursor.fetchone()
    if row and (time.time() - row[0] <= 900): # صلاحية التعديل خلال 15 دقيقة
        cursor.execute('UPDATE messages SET content = ? WHERE id = ?', (new_content, msg_id))
        conn.commit()
        emit('edit_message_client', {'id': msg_id, 'content': new_content}, to=room)
    conn.close()

# إشارات مكالمات الفيديو والصوت الأصلية بتاعتك بدون تعديل مع توجيهها للغرفة لعزلها
@socketio.on('call_user')
def handle_call(data):
    room = data.get('room')
    emit('call_received', {'from': data['from'], 'offer': data['offer'], 'type': data['type']}, to=room, include_self=False)

@socketio.on('answer_call')
def handle_answer(data):
    room = data.get('room')
    emit('call_answered', {'answer': data['answer']}, to=room, include_self=False)

@socketio.on('ice_candidate')
def handle_ice(data):
    room = data.get('room')
    emit('ice_candidate', data['candidate'], to=room, include_self=False)

@socketio.on('end_call')
def handle_end_call(data):
    room = data.get('room')
    emit('end_call', to=room, include_self=False)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
