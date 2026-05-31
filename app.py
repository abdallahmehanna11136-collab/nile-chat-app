from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO, emit, join_room
import os
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = 'abdo_secret_nile_key'
socketio = SocketIO(app, cors_allowed_origins="*")

def init_db():
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    # تأكد من وجود خانة room في الجدول لحفظ الرسايل جوة الأوضة
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT,
            sender TEXT,
            content TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

# الربط الصحيح مع السطر 40 في الجافا سكريبت لدخول الغرفة
@socketio.on('join_room')
def handle_join_room(data):
    room = data['room']
    join_room(room)
    
    # جلب رسايل الغرفة دي بس أول ما المستخدم يدخل
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT sender, content FROM messages WHERE room = ? ORDER BY id ASC", (room,))
        rows = cursor.fetchall()
        for row in rows:
            emit('message', {'sender': row[0], 'content': row[1]})
    except:
        pass
    conn.close()

# استقبال الرسالة وبثها لداخل الغرفة السرية بس
@socketio.on('new_message')
def handle_new_message(data):
    room = data['room']
    sender = data['sender']
    content = data['content']
    
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (room, sender, content) VALUES (?, ?, ?)", (room, sender, content))
    conn.commit()
    conn.close()
    
    emit('message', {'sender': sender, 'content': content}, to=room)

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('.', 'manifest.json')

@app.route('/icon.png')
def serve_icon():
    return send_from_directory('.', 'icon.png')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
