from flask import Flask, render_template, make_response, request, jsonify, url_for
from flask_socketio import SocketIO, emit, join_room
import sqlite3
import time
import os
from werkzeug.utils import secure_filename
from groq import Groq

# 1. إعداد عميل الذكاء الاصطناعي بقراءة المفتاح من البيئة المحيطة لتجنب الحظر
GROQ_API_KEY = os.environ.get('GROQ_API_KEY', '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')
groq_client = Groq(api_key=GROQ_API_KEY)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'nile_chat_stable_core_system'

# مجلد حفظ الملفات والصور والميديا
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# إعداد السوكيت ليدعم الاتصال الآمن wss والاتصال العادي أوتوماتيكياً على Render
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', ping_timeout=60, ping_interval=25)
DB_PATH = 'nile_chat_database.db'

# 2. تهيئة الجداول في قاعدة البيانات
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, room TEXT, sender TEXT, phone TEXT, text TEXT, 
            timestamp REAL, file_type TEXT DEFAULT 'text', file_name TEXT DEFAULT '', reactions TEXT DEFAULT ''
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stories (
            id TEXT PRIMARY KEY, sender TEXT, phone TEXT, text TEXT, file_type TEXT, timestamp REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS groups (
            id TEXT PRIMARY KEY, name TEXT, creator TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    response = make_response(render_template('index.html'))
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return response

# 3. مسار رفع الميديا (الصور، الفيديو، الحالات) - تم تعديله ليدعم الرفع الآمن
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    
    filename = secure_filename(f"{int(time.time())}_{file.filename}")
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    
    # تحويل الرابط ليكون متوافق مع https الخاص بـ Render
    f_url = url_for('static', filename=f"uploads/{filename}", _external=True)
    if request.headers.get('X-Forwarded-Proto') == 'https':
        f_url = f_url.replace('http://', 'https://')
        
    f_type = 'file'
    mimetype = file.mimetype
    if mimetype.startswith('image/'): f_type = 'image'
    elif mimetype.startswith('video/'): f_type = 'video'
    elif mimetype.startswith('audio/'): f_type = 'audio'
    
    return jsonify({'url': f_url, 'file_type': f_type})

# 4. أحداث السوكيت
@socketio.on('register_user')
def handle_register(data):
    phone = data.get('phone')
    if phone:
        join_room(f"user_{phone}")

@socketio.on('join_room')
def on_join_room(data):
    room = data.get('room', 'public_room')
    join_room(room)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, room, sender, text, file_type, file_name, reactions FROM messages WHERE room = ? ORDER BY timestamp ASC", (room,))
    rows = cursor.fetchall()
    conn.close()
    
    history = [{"id": r[0], "room": r[1], "sender": r[2], "text": r[3], "file_type": r[4], "file_name": r[5], "reactions": r[6]} for r in rows]
    emit('chat_history', {'messages': history})

@socketio.on('message')
def handle_message_event(data):
    msg_id = data.get('id', f"msg-{int(time.time() * 1000)}")
    room = data.get('room', 'public_room')
    sender = data.get('sender', 'مستخدم')
    phone = data.get('phone', '')
    text = data.get('text', '')
    file_type = data.get('file_type', 'text')
    file_name = data.get('file_name', '')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (id, room, sender, phone, text, timestamp, file_type, file_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (msg_id, room, sender, phone, text, time.time(), file_type, file_name))
    conn.commit()
    conn.close()

    emit('message', {'id': msg_id, 'room': room, 'sender': sender, 'phone': phone, 'text': text, 'file_type': file_type, 'file_name': file_name, 'reactions': ''}, room=room)

    # رد الذكاء الاصطناعي السريع (NileAI)
    if room == 'NileAI_room' or (room == 'public_room' and '@NileAI' in text):
        try:
            prompt_content = text.replace('@NileAI', '').strip()
            if file_type != 'text':
                prompt_content = "لقد أرسلت لك ملفاً ميديا."

            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "أنت NileAI المساعد الخارق. رد بالعامية المصرية بذكاء وسرعة رهيبة وبدون أي مقدمات أو اعتذارات."},
                    {"role": "user", "content": prompt_content if prompt_content else "أهلاً بك!"}
                ],
                model="llama3-8b-8192",
            )
            reply_text = chat_completion.choices[0].message.content
            bot_msg_id = f"msg-bot-{int(time.time() * 1000)}"
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (id, room, sender, phone, text, timestamp, file_type, file_name) VALUES (?, ?, 'NileAI 🤖', 'bot-system', ?, ?, 'text', '')",
                           (bot_msg_id, room, reply_text, time.time()))
            conn.commit()
            conn.close()
            
            emit('message', {'id': bot_msg_id, 'room': room, 'sender': "NileAI 🤖", 'phone': "bot-system", 'text': reply_text, 'file_type': 'text', 'file_name': '', 'reactions': ''}, room=room)
        except Exception as e:
            print("AI Engine Error:", e)

# 5. ميزة التفاعلات
@socketio.on('add_reaction')
def add_reaction(data):
    msg_id = data.get('id')
    room = data.get('room')
    reaction = data.get('reaction')
    if msg_id and reaction:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("UPDATE messages SET reactions = ? WHERE id = ?", (reaction, msg_id))
        conn.commit()
        conn.close()
        emit('reaction_updated', {'id': msg_id, 'reactions': reaction}, room=room)

# 6. ميزة الحالات (Stories)
@socketio.on('add_story')
def handle_story(data):
    story_id = f"story-{int(time.time() * 1000)}"
    sender = data.get('sender')
    phone = data.get('phone')
    text = data.get('text')
    file_type = data.get('file_type', 'text')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM stories WHERE phone = ?", (phone,))
    cursor.execute("INSERT INTO stories (id, sender, phone, text, file_type, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                   (story_id, sender, phone, text, file_type, time.time()))
    conn.commit()
    conn.close()
    
    # إرسال بث مباشر لكل الناس إن فيه ستوري جديدة تظهر فوراً في الـ HTML
    emit('new_story_alert', broadcast=True)

@socketio.on('get_stories')
def get_stories():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    day_ago = time.time() - 86400
    cursor.execute("SELECT id, sender, text, file_type FROM stories WHERE timestamp > ? ORDER BY timestamp DESC", (day_ago,))
    rows = cursor.fetchall()
    conn.close()
    stories = [{"id": r[0], "sender": r[1], "text": r[2], "file_type": r[3]} for r in rows]
    emit('stories_list', {'stories': stories})

# 7. ميزة المجموعات
@socketio.on('create_group')
def create_group(data):
    g_id = f"group_{int(time.time() * 1000)}"
    g_name = data.get('name')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO groups (id, name, creator) VALUES (?, ?, 'user')", (g_id, g_name))
    conn.commit()
    conn.close()
    emit('group_created_alert', broadcast=True)

@socketio.on('get_groups')
def get_groups():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM groups")
    rows = cursor.fetchall()
    conn.close()
    groups = [{"id": r[0], "name": r[1]} for r in rows]
    emit('groups_list', {'groups': groups})

# 8. نظام إشارات المكالمات اللايف (WebRTC Signaling) لربط المايك والكاميرا أونلاين
@socketio.on('call_signal')
def handle_call_signal(data):
    target_phone = data.get('target_phone')
    if target_phone:
        # تمرير الـ Offer أو الـ Answer أو الـ Candidates للطرف الثاني فوراً عبر السيرفر الآمن
        emit('call_signal', data, room=f"user_{target_phone}", include_self=False)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
