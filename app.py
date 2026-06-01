from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO, emit, join_room
import os
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = 'abdo_secret_nile_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# إنشاء قاعدة البيانات الجديدة والجداول على نضافة تماماً
def init_db():
    conn = sqlite3.connect('nile_rooms.db')
    cursor = conn.cursor()
    cursor.execute('''
       CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                msg_id TEXT,
                room TEXT,
                sender TEXT,
                content TEXT
            )
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

# الربط الصحيح لدخول الغرفة وجلب رسايلها القديمة بس
@socketio.on('join_room')
def handle_join_room(data):
    room = data['room']
    join_room(room)
    
   # جلب أرشيف الرسائل الخاص بهذه الغرفة السرية فقط
    conn = sqlite3.connect('nile_rooms.db')
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT sender, content, msg_id FROM messages WHERE room = ? ORDER BY id ASC", (room,))
        rows = cursor.fetchall()
        for row in rows:
            emit('message', {'sender': row[0], 'content': row[1], 'id': row[2]})
    except Exception as e:
        print(f"Error reading database: {e}")
    finally:
        conn.close()
# استقبال الرسائل الجديدة وحفظها وبثها جوة الأوضة بس
@socketio.on('new_message')
def handle_new_message(data):
    room = data['room']
    sender = data['sender']
    content = data['content']
    msg_id = data.get('id')

    conn = sqlite3.connect('nile_rooms.db')
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO messages (msg_id, room, sender, content) VALUES (?, ?, ?, ?)", (msg_id, room, sender, content))
        conn.commit()
    except Exception as e:
        print(f"Error writing to database: {e}")
    finally:
        conn.close()

    emit('message', {'sender': sender, 'content': content, 'id': msg_id}, to=room)

@socketio.on('delete_message_server')
def handle_delete_message(data):
    room = data.get('room')
    msg_id = data.get('id')
    
    conn = sqlite3.connect('nile_rooms.db')
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM messages WHERE msg_id = ?", (msg_id,))
        conn.commit()
    except Exception as e:
        print(f"Error deleting from database: {e}")
    finally:
        conn.close()
        
    emit('delete_message_client', {'id': msg_id}, to=room)

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('.', 'manifest.json')

@app.route('/icon.png')
def serve_icon():
    return send_from_directory('.', 'icon.png')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
