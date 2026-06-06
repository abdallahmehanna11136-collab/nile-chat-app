import os
import sqlite3
import time
from flask import Flask, render_template, make_response, request, jsonify, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['SECRET_KEY'] = 'nile_chat_key_2026'

# إعداد مجلد الميديا المرفوعة
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
DB_PATH = 'nile_chat_database.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # جدول الرسائل مطور لدعم الردود والتفاعلات والتعديل
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, 
            room TEXT, 
            sender TEXT, 
            phone TEXT, 
            text TEXT, 
            timestamp REAL, 
            file_type TEXT DEFAULT 'text', 
            file_name TEXT DEFAULT '', 
            reactions TEXT DEFAULT '', 
            status_ticks TEXT DEFAULT 'sent', 
            reply_to TEXT DEFAULT ''
        )
    ''')
    
    # جدول الحالات يدعم النصوص والميديا
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stories (
            id TEXT PRIMARY KEY, 
            sender TEXT, 
            phone TEXT, 
            text TEXT, 
            file_type TEXT, 
            timestamp REAL, 
            reposts_count INTEGER DEFAULT 0
        )
    ''')
    
    # جدول الحسابات الشخصية والخلفيات والحالات المخصصة
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            phone TEXT PRIMARY KEY, 
            name TEXT, 
            avatar TEXT, 
            email TEXT DEFAULT '', 
            status_text TEXT DEFAULT 'Available', 
            archived_chats TEXT DEFAULT '', 
            custom_ringtone TEXT DEFAULT 'default.mp3', 
            privacy_mode TEXT DEFAULT 'public', 
            wallpaper TEXT DEFAULT ''
        )
    ''')
    
    # جدول المجموعات والقنوات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS units (
            id TEXT PRIMARY KEY, 
            name TEXT, 
            type TEXT, 
            creator TEXT, 
            admins TEXT
        )
    ''')
    
    # جدول اليوميات والمنشورات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feed_posts (
            id TEXT PRIMARY KEY, 
            sender TEXT, 
            phone TEXT, 
            avatar TEXT, 
            text TEXT, 
            media_url TEXT, 
            file_type TEXT, 
            timestamp REAL, 
            likes INTEGER DEFAULT 0
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

# هندسة رفع الملفات الذكية (صور، فيديو، صوت) وتحديد نوعها تلقائياً للمتصفح
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files: 
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    filename = secure_filename(f"{int(time.time() * 1000)}_{file.filename}")
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(file_path)
    
    # تحديد نوع الملف المرفوع ليتطابق مع شروط عرض الـ HTML
    ext = filename.split('.')[-1].lower()
    f_type = 'text'
    if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
        f_type = 'image'
    elif ext in ['mp4', 'webm', 'ogg', 'mov']:
        f_type = 'video'
    elif ext in ['mp3', 'wav', 'aac', 'm4a', 'ogg']:
        f_type = 'audio'
        
    f_url = url_for('static', filename=f"uploads/{filename}", _external=True)
    return jsonify({'url': f_url, 'file_type': f_type, 'name': file.filename})

@socketio.on('register_user')
def handle_register(data):
    phone = str(data.get('phone')).strip()
    name = data.get('name', 'User')
    avatar = data.get('avatar', '')
    email = data.get('email', '')
    if phone:
        join_room(f"user_{phone}")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM profiles WHERE phone = ?", (phone,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO profiles (phone, name, avatar, email) VALUES (?, ?, ?, ?)", (phone, name, avatar, email))
        else:
            cursor.execute("UPDATE profiles SET name=?, avatar=?, email=? WHERE phone=?", (name, avatar, email, phone))
        conn.commit()
        conn.close()

@socketio.on('update_profile_live')
def handle_profile_update(data):
    phone = str(data.get('phone')).strip()
    name = data.get('name')
    avatar = data.get('avatar')
    wallpaper = data.get('wallpaper', '')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE profiles SET name=?, avatar=?, wallpaper=? WHERE phone=?", (name, avatar, wallpaper, phone))
    conn.commit()
    conn.close()

@socketio.on('find_user_by_phone')
def find_user_by_phone(data):
    search_phone = str(data.get('search_phone')).strip()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT phone, name, avatar, status_text FROM profiles WHERE phone = ?", (search_phone,))
    row = cursor.fetchone()
    conn.close()
    if row:
        emit('user_search_result', {
            'found': True, 
            'phone': row[0], 
            'name': row[1], 
            'avatar': row[2], 
            'status_text': row[3]
        })
    else:
        emit('user_search_result', {'found': False, 'phone': search_phone})

@socketio.on('join_room')
def on_join_room(data):
    room = data.get('room', 'public_room')
    join_room(room)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # جلب جميع حقول الرسائل بما فيها التفاعلات والردود لترتيب الشات
    cursor.execute("""
        SELECT id, room, sender, text, file_type, file_name, reactions, reply_to, phone 
        FROM messages WHERE room = ? ORDER BY timestamp ASC
    """, (room,))
    rows = cursor.fetchall()
    conn.close()
    
    history = [{
        "id": r[0], "room": r[1], "sender": r[2], "text": r[3], 
        "file_type": r[4], "file_name": r[5], "reactions": r[6], 
        "reply_to": r[7], "phone": r[8]
    } for r in rows]
    emit('chat_history', {'messages': history})

@socketio.on('message')
def handle_message_event(data):
    room = data.get('room', 'public_room')
    msg_id = data.get('id')
    sender = data.get('sender')
    phone = data.get('phone')
    text = data.get('text')
    file_type = data.get('file_type', 'text')
    file_name = data.get('file_name', '')
    reply_to = data.get('reply_to', '')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO messages (id, room, sender, phone, text, timestamp, file_type, file_name, reply_to) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (msg_id, room, sender, phone, text, time.time(), file_type, file_name, reply_to))
    conn.commit()
    conn.close()
    emit('message', data, room=room)

# أحداث تعديل وحذف وتفاعلات الرسائل المتطابقة مع أزرار لوحة الـ HTML
@socketio.on('edit_message')
def handle_edit_message(data):
    msg_id = data.get('id')
    new_text = data.get('text')
    room = data.get('room')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE messages SET text=? WHERE id=?", (new_text, msg_id))
    conn.commit()
    conn.close()
    emit('message_edited', data, room=room)

@socketio.on('delete_message')
def handle_delete_message(data):
    msg_id = data.get('id')
    room = data.get('room')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE id=?", (msg_id,))
    conn.commit()
    conn.close()
    emit('message_deleted', data, room=room)

@socketio.on('update_reaction')
def handle_reaction(data):
    msg_id = data.get('id')
    reaction = data.get('reactions')
    room = data.get('room')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE messages SET reactions=? WHERE id=?", (reaction, msg_id))
    conn.commit()
    conn.close()
    emit('reaction_updated', data, room=room)

# هندسة وإدارة ربط الحالات (Stories) مع جلب الآفاتار الخاص بصاحبها تلقائياً
@socketio.on('add_story')
def handle_story(data):
    story_id = f"story-{int(time.time() * 1000)}"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO stories (id, sender, phone, text, file_type, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                   (story_id, data.get('sender'), data.get('phone'), data.get('text'), data.get('file_type'), time.time()))
    conn.commit()
    conn.close()
    emit('new_story_alert', broadcast=True)

@socketio.on('get_stories')
def get_stories():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # جلب الحالات مع دمج صورة صاحب الحساب لتظهر الأيقونات والدوائر بشكل كامل في الفرونت
    cursor.execute("""
        SELECT s.id, s.sender, s.text, s.file_type, p.avatar 
        FROM stories s LEFT JOIN profiles p ON s.phone = p.phone 
        ORDER BY s.timestamp DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    emit('stories_list', {'stories': [
        {"id": r[0], "sender": r[1], "text": r[2], "file_type": r[3], "avatar": r[4]} for r in rows
    ]})

# هندسة وإدارة المجموعات والقنوات
@socketio.on('create_unit')
def create_unit(data):
    u_id = f"unit_{int(time.time() * 1000)}"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO units (id, name, type, creator) VALUES (?, ?, ?, ?)", 
                   (u_id, data.get('name'), data.get('type'), data.get('creator')))
    conn.commit()
    conn.close()
    emit('unit_created_alert', broadcast=True)

@socketio.on('get_units')
def get_units():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, type FROM units")
    rows = cursor.fetchall()
    conn.close()
    emit('units_list', {'units': [{"id": r[0], "name": r[1], "type": r[2]} for r in rows]})

# هندسة وإدارة منشورات اليوميات المتوافقة بالكامل مع الفرونت إند الـ 700 سطر
@socketio.on('add_feed_post')
def add_feed_post(data):
    post_id = f"post-{int(time.time() * 1000)}"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO feed_posts (id, sender, phone, avatar, text, media_url, file_type, timestamp) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (post_id, data.get('sender'), data.get('phone'), data.get('avatar'), data.get('text'), data.get('media_url'), data.get('file_type'), time.time()))
    conn.commit()
    conn.close()
    emit('new_feed_post_alert', broadcast=True)

@socketio.on('get_feed_posts')
def get_feed_posts():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, sender, text, media_url, avatar, file_type FROM feed_posts ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    emit('feed_posts_list', {'posts': [
        {"id": r[0], "sender": r[1], "text": r[2], "media_url": r[3], "avatar": r[4], "file_type": r[5]} for r in rows
    ]})

# تمرير إشارات اتصال WebRTC بين الهواتف والمتصفحات لضمان فتح شاشات المكالمات
@socketio.on('call_signal')
def handle_call_signal(data):
    target = data.get('target_phone')
    # بث إشارة الاتصال إلى الروم الخاص بالمستخدم المستهدف مباشرة
    emit('call_signal', data, room=f"user_{target}")

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
