from flask import Flask, render_template, request, send_from_directory
from flask_socketio import SocketIO, emit, join_room
import os
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = 'abdu_secret_nile_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# إنشاء قاعدة البيانات والجداول بناءً على هيكلة كودك الأصلي
def init_db():
    conn = sqlite3.connect('nile_rooms.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT,
            sender TEXT,
            content TEXT,
            msg_id TEXT
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
    return send_from_directory(os.path.join(app.root_path, 'static'), 'manifest.json')

@app.route('/icon.png')
def icon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'icon.png')

@socketio.on('join_room')
def handle_join_room(data):
    room = data.get('room', 'عامة')
    join_room(room)

@socketio.on('new_message')
def handle_new_message(data):
    room = data['room']
    sender = data['sender']
    content = data['content']
    msg_id = data.get('id')
    msg_type = data.get('type', 'text') # استقبال نوع الرسالة (صوت أو نص)

    conn = sqlite3.connect('nile_rooms.db')
    cursor = conn.cursor()
    try:
        # الحفظ متوافق تماماً مع حقول الداتابيز اللي عندك
        cursor.execute("INSERT INTO messages (room, sender, content, msg_id) VALUES (?, ?, ?, ?)", 
                       (room, sender, content, msg_id))
        conn.commit()
    except Exception as e:
        print(f"Error writing to database: {e}")
    finally:
        conn.close()

    # إرسال الرسالة للغرفة المحددة مع تمرير النوع ليعرضها المتصفح بشكل صحيح
    emit('message', {'sender': sender, 'content': content, 'id': msg_id, 'type': msg_type}, to=room)

@socketio.on('delete_message_server')
def handle_delete_message(data):
    room = data['room']
    msg_id = data['id']

    conn = sqlite3.connect('nile_rooms.db')
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM messages WHERE msg_id = ?", (msg_id,))
        conn.commit()
    except Exception as e:
        print(f"Error deleting message: {e}")
    finally:
        conn.close()

    emit('delete_message_client', {'id': msg_id}, room=room)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
