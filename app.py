from flask import Flask, render_template
from flask_socketio import SocketIO, emit, join_room
import os
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = 'nile_chat_secret_key_123'

# تشغيل الـ SocketIO بأبسط طريقة متوافقة مع السيرفر الخارجي
socketio = SocketIO(app, cors_allowed_origins="*")

# مسار قاعدة البيانات في المجلد المؤقت لـ Render
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

# --- أحداث الشات وحفظ البيانات ---

@socketio.on('join_room')
def handle_join_room(data):
    username = data.get('username')
    room = data.get('room', 'عامة')
    
    join_room(room)
    
    conn = sqlite3.connect(DB_PATH)
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
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO messages (id, room, sender, content, msg_type) VALUES (?, ?, ?, ?, ?)',
                       (msg_id, room, sender, content, msg_type))
        conn.commit()
    except sqlite3.Error as e:
        print(f"Error: {e}")
    finally:
        conn.close()
    
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
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM messages WHERE id = ?', (msg_id,))
    conn.commit()
    conn.close()
    
    emit('delete_message_client', {'id': msg_id}, room=room)
