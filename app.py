from flask import Flask, render_template, send_from_directory
from flask_socketio import SocketIO, emit, send
import os
import sqlite3

app = Flask(__name__)
app.config['SECRET_KEY'] = 'abdo_secret_nile_key'
socketio = SocketIO(app, cors_allowed_origins="*")

# دالة لإنشاء قاعدة البيانات والجدول لو مش موجودين
def init_db():
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            sender TEXT,
            content TEXT
        )
    ''')
    conn.commit()
    conn.close()

# تشغيل تهيئة قاعدة البيانات
init_db()

@app.route('/')
def index():
    return render_template('index.html')

# استقبال الرسائل الجديدة وحفظها في قاعدة البيانات ثم بثها للجميع
@socketio.on('new_message')
def handle_new_message(data):
    # حفظ الرسالة في قاعدة البيانات
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO messages (type, sender, content) VALUES (?, ?, ?)",
        (data.get('type', 'text'), data.get('sender', 'مجهول'), data.get('content', ''))
    )
    conn.commit()
    conn.close()
    
    # بث الرسالة لكل الناس في نفس اللحظة
    emit('message', data, broadcast=True)

# عند دخول مستخدم جديد: نرسل له إشعار دخول، ونرسل له كل التاريخ القديم
@socketio.on('user_join')
def handle_user_join(username):
    # إشعار الدخول بصيغة نصية
    join_msg = {
        'type': 'text',
        'sender': '📢 نظام نايل شات',
        'content': f'الانضمام إلى الغرفة الآن: {username}!'
    }
    emit('message', join_msg, broadcast=True)
    
    # جلب الرسائل القديمة من قاعدة البيانات وإرسالها للمستخدم الجديد فقط
    conn = sqlite3.connect('chat.db')
    cursor = conn.cursor()
    cursor.execute("SELECT type, sender, content FROM messages ORDER BY id ASC")
    rows = cursor.fetchall()
    conn.close()
    
    # إرسال التاريخ القديم سطر سطر للمستخدم اللي لسه داخل
    for row in rows:
        old_msg = {
            'type': row[0],
            'sender': row[1],
            'content': row[2]
        }
        emit('message', old_msg) # بدون broadcast عشان تروح له هو بس

@app.route('/manifest.json')
def serve_manifest():
    return send_from_directory('.', 'manifest.json')

@app.route('/icon.png')
def serve_icon():
    return send_from_directory('.', 'icon.png')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
