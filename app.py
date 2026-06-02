from flask import Flask, render_template
from flask_socketio import SocketIO, emit, join_room
import os
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = 'nile_chat_secret_key_123'
socketio = SocketIO(app, cors_allowed_origins="*")

# --- إعداد وإنشاء قاعدة البيانات لحفظ الرسائل للأبد ---
def init_db():
    conn = sqlite3.connect('chat_database.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            room TEXT,
            sender TEXT,
            content TEXT,
            msg_type TEXT
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
    return app.send_static_file('service-worker.js')

# --- التعامل مع أحداث الشات والربط السريع ---

@socketio.on('join_room')
def handle_join_room(data):
    username = data.get('username')
    room = data.get('room', 'عامة')
    
    join_room(room)
    print(f"👤 {username} دخل الغرفة: {room}")
    
    # سحب أرشيف الغرفة من الداتابيز فوراً
    conn = sqlite3.connect('chat_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, room, sender, content, msg_type FROM messages WHERE room = ?', (room,))
    rows = cursor.fetchall()
    conn.close()
    
    for row in rows:
        emit('message', {
            'id': row[0],
            'room': row[1],
            'sender': row[2],
            'content': row[3],
            'type': row[4]
        })

@socketio.on('new_message')
def handle_new_message(data):
    msg_id = data.get('id')
    room = data.get('room', 'عامة')
    sender = data.get('sender')
    content = data.get('content')
    msg_type = data.get('type', 'text')
    
    # حفظ الرسالة أو الفويس في قاعدة البيانات
    conn = sqlite3.connect('chat_database.db')
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO messages (id, room, sender, content, msg_type) VALUES (?, ?, ?, ?, ?)',
                       (msg_id, room, sender, content, msg_type))
        conn.commit()
    except sqlite3.Error as e:
        print(f"خطأ في الحفظ: {e}")
    finally:
        conn.close()
    
    # إرسال الرسالة فوراً للغرفة المحددة
    emit('message', {
        'id': msg_id,
        'room': room,
        'sender': sender,
        'content': content,
        'type': msg_type
    }, room=room)

@socketio.on('delete_message_server')
def handle_delete_message(data):
    room = data.get('room')
    msg_id = data.get('id')
    
    # حذف نهائي من الداتابيز
    conn = sqlite3.connect('chat_database.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM messages WHERE id = ?', (msg_id,))
    conn.commit()
    conn.close()
    
    # مسح من الشاشات عند الجميع فوراً
    emit('delete_message_client', {'id': msg_id}, room=room)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=True)
