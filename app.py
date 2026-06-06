import os
import sqlite3
import time
from flask import Flask, render_template, make_response, request, jsonify, url_for
from flask_socketio import SocketIO, emit, join_room, leave_room
from werkzeug.utils import secure_filename
from groq import Groq

groq_client = Groq(api_key='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')

app = Flask(__name__)
app.config['SECRET_KEY'] = 'nile_chat_key_2026'

UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
DB_PATH = 'nile_chat_database.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, room TEXT, sender TEXT, phone TEXT, text TEXT, 
            timestamp REAL, file_type TEXT DEFAULT 'text', file_name TEXT DEFAULT '', 
            reactions TEXT DEFAULT '', status_ticks TEXT DEFAULT 'sent', reply_to TEXT DEFAULT ''
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stories (
            id TEXT PRIMARY KEY, sender TEXT, phone TEXT, text TEXT, file_type TEXT, timestamp REAL, reposts_count INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            phone TEXT PRIMARY KEY, name TEXT, avatar TEXT, email TEXT DEFAULT '', 
            status_text TEXT DEFAULT 'Available', archived_chats TEXT DEFAULT '', 
            custom_ringtone TEXT DEFAULT 'default.mp3', privacy_mode TEXT DEFAULT 'public', wallpaper TEXT DEFAULT ''
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS units (
            id TEXT PRIMARY KEY, name TEXT, type TEXT, creator TEXT, admins TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feed_posts (
            id TEXT PRIMARY KEY, sender TEXT, phone TEXT, avatar TEXT, text TEXT, media_url TEXT, file_type TEXT, timestamp REAL, likes INTEGER DEFAULT 0
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
    
    f_url = url_for('static', filename=f"uploads/{filename}", _external=True)
    if request.headers.get('X-Forwarded-Proto') == 'https':
        f_url = f_url.replace('http://', 'https://')
        
    f_type = 'file'
    mimetype = file.mimetype or ''
    if mimetype.startswith('image/'): f_type = 'image'
    elif mimetype.startswith('video/'): f_type = 'video'
    elif mimetype.startswith('audio/'): f_type = 'audio'
    
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
        cursor.execute("SELECT name, avatar, email FROM profiles WHERE phone = ?", (phone,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT INTO profiles (phone, name, avatar, email) VALUES (?, ?, ?, ?)", (phone, name, avatar, email))
        else:
            cursor.execute("UPDATE profiles SET name=?, email=? WHERE phone=?", (name, email, phone))
        conn.commit()
        conn.close()

@socketio.on('update_profile_live')
def handle_profile_update(data):
    phone = str(data.get('phone')).strip()
    name = data.get('name')
    avatar = data.get('avatar')
    status_text = data.get('status_text', 'Available')
    custom_ringtone = data.get('custom_ringtone', 'default.mp3')
    wallpaper = data.get('wallpaper', '')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE profiles SET name=?, avatar=?, status_text=?, custom_ringtone=?, wallpaper=? WHERE phone=?", 
                   (name, avatar, status_text, custom_ringtone, wallpaper, phone))
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
        emit('user_search_result', {'found': True, 'phone': row[0], 'name': row[1], 'avatar': row[2], 'status_text': row[3]})
    else:
        emit('user_search_result', {'found': False, 'phone': search_phone})

@socketio.on('join_room')
def on_join_room(data):
    room = data.get('room', 'public_room')
    join_room(room)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, room, sender, text, file_type, file_name, reactions, status_ticks, reply_to FROM messages WHERE room = ? ORDER BY timestamp ASC", (room,))
    rows = cursor.fetchall()
    conn.close()
    
    history = [{
        "id": r[0], "room": r[1], "sender": r[2], "text": r[3], 
        "file_type": r[4], "file_name": r[5], "reactions": r[6], 
        "status_ticks": r[7], "reply_to": r[8]
    } for r in rows]
    emit('chat_history', {'messages': history})

@socketio.on('message')
def handle_message_event(data):
    msg_id = data.get('id', f"msg-{int(time.time() * 1000)}")
    room = data.get('room', 'public_room')
    sender = data.get('sender', 'User')
    phone = str(data.get('phone', '')).strip()
    text = data.get('text', '')
    file_type = data.get('file_type', 'text')
    file_name = data.get('file_name', '')
    reply_to = data.get('reply_to', '')

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO messages (id, room, sender, phone, text, timestamp, file_type, file_name, reactions, status_ticks, reply_to) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', 'read', ?)",
                   (msg_id, room, sender, phone, text, time.time(), file_type, file_name, reply_to))
    conn.commit()
    conn.close()

    payload = {
        'id': msg_id, 'room': room, 'sender': sender, 'phone': phone, 
        'text': text, 'file_type': file_type, 'file_name': file_name, 
        'reactions': '', 'status_ticks': 'read', 'reply_to': reply_to
    }
    emit('message', payload, room=room)

    if room == f"AI_{phone}":
        try:
            prompt_content = text.strip()
            chat_completion = groq_client.chat.completions.create(
                messages=[
                    {"role": "system", "content": "أنت مساعد ذكي لتطبيق نايل شات. رد بالعامية المصرية باختصار."},
                    {"role": "user", "content": prompt_content}
                ],
                model="llama3-8b-8192",
            )
            reply_text = chat_completion.choices[0].message.content
            bot_msg_id = f"msg-bot-{int(time.time() * 1000)}"
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO messages (id, room, sender, phone, text, timestamp, file_type, file_name, reactions, status_ticks, reply_to) VALUES (?, ?, 'نايل شات 🤖', 'bot-system', ?, ?, 'text', '', '', 'read', '')",
                           (bot_msg_id, room, reply_text, time.time()))
            conn.commit()
            conn.close()
            
            emit('message', {
                'id': bot_msg_id, 'room': room, 'sender': "نايل شات 🤖", 'phone': "bot-system", 
                'text': reply_text, 'file_type': 'text', 'file_name': '', 'reactions': '', 'status_ticks': 'read', 'reply_to': ''
            }, room=room)
        except Exception as e:
            pass

@socketio.on('edit_message')
def handle_edit(data):
    msg_id = data.get('id')
    new_text = data.get('text')
    room = data.get('room')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE messages SET text = ? WHERE id = ?", (new_text, msg_id))
    conn.commit()
    conn.close()
    emit('message_edited', {'id': msg_id, 'text': new_text, 'room': room}, room=room)

@socketio.on('delete_message')
def handle_delete(data):
    msg_id = data.get('id')
    room = data.get('room')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE id = ?", (msg_id,))
    conn.commit()
    conn.close()
    emit('message_deleted', {'id': msg_id, 'room': room}, room=room)

@socketio.on('update_reaction')
def handle_reaction(data):
    msg_id = data.get('id')
    reactions = data.get('reactions')
    room = data.get('room')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE messages SET reactions = ? WHERE id = ?", (reactions, msg_id))
    conn.commit()
    conn.close()
    emit('reaction_updated', {'id': msg_id, 'reactions': reactions, 'room': room}, room=room)

@socketio.on('add_story')
def handle_story(data):
    story_id = f"story-{int(time.time() * 1000)}"
    sender = data.get('sender')
    phone = str(data.get('phone')).strip()
    text = data.get('text')
    file_type = data.get('file_type', 'text')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO stories (id, sender, phone, text, file_type, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                   (story_id, sender, phone, text, file_type, time.time()))
    conn.commit()
    conn.close()
    emit('new_story_alert', broadcast=True)

@socketio.on('get_stories')
def get_stories():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    day_ago = time.time() - 86400
    cursor.execute("SELECT stories.id, stories.sender, stories.text, stories.file_type, profiles.avatar, stories.phone FROM stories LEFT JOIN profiles ON stories.phone = profiles.phone WHERE stories.timestamp > ? ORDER BY stories.timestamp DESC", (day_ago,))
    rows = cursor.fetchall()
    conn.close()
    stories = [{"id": r[0], "sender": r[1], "text": r[2], "file_type": r[3], "avatar": r[4] if r[4] else '', "phone": r[5]} for r in rows]
    emit('stories_list', {'stories': stories})

@socketio.on('create_unit')
def create_unit(data):
    u_id = f"unit_{int(time.time() * 1000)}"
    name = data.get('name')
    u_type = data.get('type', 'group')
    creator = str(data.get('creator')).strip()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO units (id, name, type, creator, admins) VALUES (?, ?, ?, ?, ?)", (u_id, name, u_type, creator, creator))
    conn.commit()
    conn.close()
    emit('unit_created_alert', broadcast=True)

@socketio.on('get_units')
def get_units():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, type, creator, admins FROM units")
    rows = cursor.fetchall()
    conn.close()
    units = [{"id": r[0], "name": r[1], "type": r[2], "creator": r[3], "admins": r[4]} for r in rows]
    emit('units_list', {'units': units})

@socketio.on('add_feed_post')
def add_feed_post(data):
    post_id = f"post-{int(time.time() * 1000)}"
    sender = data.get('sender')
    phone = str(data.get('phone')).strip()
    avatar = data.get('avatar', '')
    text = data.get('text', '')
    media_url = data.get('media_url', '')
    file_type = data.get('file_type', 'text')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO feed_posts (id, sender, phone, avatar, text, media_url, file_type, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (post_id, sender, phone, avatar, text, media_url, file_type, time.time()))
    conn.commit()
    conn.close()
    emit('new_feed_post_alert', broadcast=True)

@socketio.on('get_feed_posts')
def get_feed_posts():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT feed_posts.id, feed_posts.sender, feed_posts.text, feed_posts.media_url, feed_posts.file_type, profiles.avatar, feed_posts.likes, feed_posts.phone FROM feed_posts LEFT JOIN profiles ON feed_posts.phone = profiles.phone ORDER BY feed_posts.timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    posts = [{"id": r[0], "sender": r[1], "text": r[2], "media_url": r[3], "file_type": r[4], "avatar": r[5] if r[5] else '', "likes": r[6], "phone": r[7]} for r in rows]
    emit('feed_posts_list', {'posts': posts})

@socketio.on('call_signal')
def handle_call_signal(data):
    target_phone = str(data.get('target_phone')).strip()
    if target_phone:
        emit('call_signal', data, room=f"user_{target_phone}", include_self=False)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
