from flask import Flask, render_template
from flask_socketio import SocketIO, emit, send
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'abdo_secret_nile_key'
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def index():
    return render_template('index.html')

# استقبال الرسائل الجديدة (سواء صوت أو نص) وبثها للجميع بنظام منظّم
@socketio.on('new_message')
def handle_new_message(data):
    emit('message', data, broadcast=True)

@socketio.on('user_join')
def handle_user_join(username):
    # إشعار الدخول بصيغة نصية
    emit('message', {'type': 'text', 'sender': '📢 نظام نايل شات', 'content': f'{username} انضم إلى الغرفة الآن!'}, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, allow_unsafe_werkzeug=True)
