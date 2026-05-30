from flask import Flask, render_template
from flask_socketio import SocketIO, send

app = Flask(__name__)
app.config['SECRET_KEY'] = 'abdo_secret_nile_key'
# تشغيل عادي وبسيط متوافق مع ريندر مباشرة
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route('/')
def index():
    return render_template('index.html')

@socketio.on('message')
def handle_message(msg):
    send(msg, broadcast=True)

@socketio.on('user_join')
def handle_user_join(username):
    send(f"📢 نظام نايل شات: {username} انضم إلى الغرفة الآن!", broadcast=True)

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port)
