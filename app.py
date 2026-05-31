from flask import Flask, render_template, send_from_directory, jsonify
from flask_socketio import SocketIO, emit
import os
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = 'abdo_secret_nile_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# تهيئة قاعدة البيانات الجديدة باسم جديد تماماً للأمان
def init_db():
    conn = sqlite3.connect('private_chat.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS private_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT,
            receiver TEXT,
            content TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html')

# جلب لستة الأشخاص
@app.route('/get_chats/<username>')
def get_chats(username):
    conn = sqlite3.connect('private_chat.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT DISTINCT sender FROM private_messages WHERE receiver = ?
        UNION
        SELECT DISTINCT receiver FROM private_messages WHERE sender = ?
    ''', (username, username))
    chats = [row[0] for row in cursor.fetchall()]
    conn.close()
    return jsonify(chats)

# جلب المحادثة الثابتة بين شخصين بس
@app.route('/get_messages/<user1>/<user2>')
def get_messages(user1, user2):
    conn = sqlite3.connect('private_chat.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT sender, content FROM private_messages 
        WHERE (sender = ? AND receiver = ?) OR (sender = ? AND receiver = ?)
        ORDER BY id ASC
    ''', (user1, user2, user2, user1))
    messages = [{'sender': row[0], 'content': row[1]} for row in cursor.fetchall()]
    conn.close()
    return jsonify(messages)

# استقبال الرسائل الخاصة وبثها
@socketio.on('private_msg')
def handle_private_msg(data):
    sender = data['sender']
    receiver = data['receiver']
    content = data['content']
    
    conn = sqlite3.connect('private_chat.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO private_messages (sender, receiver, content) VALUES (?, ?, ?)",
        (sender, receiver, content)
    )
    conn.commit()
    conn.close()
    
    emit('receive_private', data, broadcast=True)

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('.', 'manifest.json')

@app.route('/icon.png')
def serve_icon():
    return send_from_directory('.', 'icon.png')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
