from flask import render_template_string
from flask_socketio import SocketIO, emit, join_room
from werkzeug.utils import secure_filename
from datetime import timedelta
import sqlite3
import time
import os
import requests
import json
from gevent import monkey
monkey.patch_all()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'nile_chat_secure_prime_key_2026'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=36500)
UPLOAD_FOLDER = 'static/uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent', engineio_logger=False, logger=False)
DB_PATH = 'nile_chat_database.db'
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "gsk_XbW76VymhF0yJp9uS7NnWGdyb3FYM3Yp5vR9kL8mJq2bN4oP3qR")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, room TEXT, sender TEXT, phone TEXT, text TEXT, 
            timestamp REAL, file_type TEXT DEFAULT 'text', file_name TEXT DEFAULT '', 
            reactions TEXT DEFAULT '', status_ticks TEXT DEFAULT 'sent', reply_to TEXT DEFAULT '',
            is_edited INTEGER DEFAULT 0, star_status INTEGER DEFAULT 0, is_forward INTEGER DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stories (
            id TEXT PRIMARY KEY, sender TEXT, phone TEXT, text TEXT, file_type TEXT, 
            timestamp REAL, views_list TEXT DEFAULT '[]', caption TEXT DEFAULT ''
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS profiles (
            phone TEXT PRIMARY KEY, name TEXT, avatar TEXT, email TEXT DEFAULT '', 
            status_text TEXT DEFAULT 'Available', archived_chats TEXT DEFAULT '[]', 
            custom_ringtone TEXT DEFAULT 'default.mp3', privacy_mode TEXT DEFAULT 'public', 
            wallpaper TEXT DEFAULT '', voice_setting TEXT DEFAULT 'normal',
            blocked_numbers TEXT DEFAULT '[]', pinned_rooms TEXT DEFAULT '[]',
            theme_mode TEXT DEFAULT 'light', saved_login_token TEXT DEFAULT ''
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS units (
            id TEXT PRIMARY KEY, name TEXT, type TEXT, creator TEXT, 
            admins TEXT DEFAULT '[]', subscribers TEXT DEFAULT '[]', description TEXT DEFAULT ''
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS feed_posts (
            id TEXT PRIMARY KEY, sender TEXT, phone TEXT, avatar TEXT, text TEXT, 
            media_url TEXT DEFAULT '', file_type TEXT DEFAULT 'text', timestamp REAL, 
            likes_count INTEGER DEFAULT 0, likes_json TEXT DEFAULT '[]', comments_json TEXT DEFAULT '[]'
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_phone TEXT, contact_phone TEXT, 
            contact_name TEXT, timestamp REAL
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS private_groups (
            id TEXT PRIMARY KEY, name TEXT, creator TEXT, members TEXT DEFAULT '[]', timestamp REAL
        )
    ''')
    conn.commit()
    conn.close()

def get_groq_ai_response(user_message):
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"}
        payload = {
            "model": "llama3-8b-8192",
            "messages": [
                {"role": "system", "content": "أنت Nile AI الذكاء الاصطناعي المدمج المساعد في تطبيق نايل تشات. تجيب بذكاء وبلاغة واختصار شديد ومباشر باللغة العربية بأسلوب تفاعلي ممتاز ومفيد للمستخدمين."},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.7, "max_tokens": 400
        }
        response = requests.post(url, json=payload, headers=headers, timeout=12)
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content'].strip()
        return f"عذراً، لم أتمكن من معالجة الطلب حالياً. (خطأ: {response.status_code})"
    except Exception as e:
        return f"فشل الاتصال بالذكاء الاصطناعي: {str(e)}"

@app.before_request
def make_session_permanent():
    session.permanent = True

from flask import render_template_string, session # تأكد أن render_template_string مستدعاة فوق

@app.route('/')
def index():
    # كود الواجهة المطور ومقاوم لتمطيط الفريمات مدمج داخل البايثون مباشرة
    html_content = """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
        <title>نايل شات المطور</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
        
        <style>
            /* هنا محرك الثيمات لمنع اختفاء الألوان */
            body.nile-theme-dark { background: #0f172a !important; color: #f8fafc !important; }
            body.nile-theme-light { background: #ffffff !important; color: #1e293b !important; }
            body { transition: background 0.3s, color 0.3s; overflow: hidden; }
        </style>
    </head>
    <body>
        <header class="header">
        </header>

        <div id="chat-messages" style="height: calc(100vh - 120px); overflow-y: auto; padding: 15px;"></div>

        <script>
        (function() {
            var socket = typeof socket !== 'undefined' ? socket : (typeof io !== 'undefined' ? io() : null);
            var myProfile = { name: 'Abdallah', phone: '123', avatar: '' };

            // استرجاع الثيم المحفوظ فوراً من المتصفح عشان يتنه محفوظ وميتمسحش
            var savedTheme = localStorage.getItem('nile_theme') || 'dark';
            document.body.className = 'nile-theme-' + savedTheme;

            if (socket && socket.on) {
                socket.off('receive_message');
                socket.on('receive_message', function(data) { 
                    if ((data.room === 'nile_ai_room' || data.senderName === 'Nile AI') && typeof appendMessage === 'function') { 
                        appendMessage(data); 
                    } 
                });
            }

            window.openNileAdvancedSettings = function() {
                var modal = document.getElementById('nileAdvancedSettingsModal');
                if (!modal) {
                    modal = document.createElement('div');
                    modal.id = 'nileAdvancedSettingsModal';
                    modal.style.cssText = 'position: fixed !important; top: 0 !important; left: 0 !important; width: 100vw !important; height: 100vh !important; background: #0f172a !important; color: #f8fafc !important; z-index: 2147483647 !important; direction: rtl !important; box-sizing: border-box !important; display: flex !important; flex-direction: column !important; overflow: hidden !important; margin: 0 !important; padding: 0 !important;';
                    
                    modal.innerHTML = `
                        <div style="background: #1e293b !important; padding: 0 16px !important; display: flex !important; align-items: center !important; gap: 16px !important; border-bottom: 1px solid #334155 !important; height: 60px !important;">
                            <button id="nileCloseSettingsBtn" style="background: transparent !important; border: none !important; color: #38bdf8 !important; font-size: 22px !important; cursor: pointer !important;">➡️</button>
                            <h2 style="margin: 0 !important; font-size: 18px !important; font-weight: 600 !important; color: #f8fafc !important;">إإعدادات المنظومة المطورة</h2>
                        </div>
                        
                        <div style="flex: 1 !important; overflow-y: auto !important; padding: 20px !important; display: flex !important; flex-direction: column !important; gap: 20px !important;">
                            <div style="display: flex !important; align-items: center !important; justify-content: space-between !important; padding: 12px 0 !important; border-bottom: 1px solid #334155 !important;">
                                <span style="font-size: 15px !important; font-weight: 600 !important;">🔒 مستوى الخصوصية والأمان</span>
                                <select id="nilePrivacySelect" style="background: #1e293b !important; color: white !important; border: 1px solid #475569 !important; padding: 8px !important; border-radius: 6px !important; width: 130px !important;">
                                    <option value="everyone">الجميع</option>
                                    <option value="contacts">جهات الاتصال</option>
                                    <option value="nobody">إخفاء تماماً</option>
                                </select>
                            </div>

                            <div style="display: flex !important; align-items: center !important; justify-content: space-between !important; padding: 12px 0 !important; border-bottom: 1px solid #334155 !important;">
                                <span style="font-size: 15px !important; font-weight: 600 !important;">🎨 واجهة نايل شات</span>
                                <select id="nileThemeSelect" style="background: #1e293b !important; color: white !important; border: 1px solid #475569 !important; padding: 8px !important; border-radius: 6px !important; width: 130px !important;">
                                    <option value="dark">مظلم قياسي</option>
                                    <option value="light">وضع فاتح</option>
                                </select>
                            </div>

                            <div style="margin-top: auto !important; padding-top: 25px !important;">
                                <button id="nileSaveSettingsBtn" style="width: 100% !important; background: #22c55e !important; color: white !important; border: none !important; padding: 12px !important; border-radius: 8px !important; cursor: pointer !important; font-weight: bold !important; font-size: 15px !important;">حفظ وتطبيق التغييرات</button>
                            </div>
                        </div>
                    `;
                    document.body.appendChild(modal);

                    document.getElementById('nileCloseSettingsBtn').onclick = function() {
                        modal.style.setProperty('display', 'none', 'important');
                    };

                    document.getElementById('nileSaveSettingsBtn').onclick = function() {
                        var chosenTheme = document.getElementById('nileThemeSelect').value;
                        localStorage.setItem('nile_privacy', document.getElementById('nilePrivacySelect').value);
                        localStorage.setItem('nile_theme', chosenTheme);
                        
                        // تطبيق الثيم فوراً
                        document.body.className = 'nile-theme-' + chosenTheme;
                        modal.style.setProperty('display', 'none', 'important');
                        alert('تم حفظ الإعدادات وتثبيت الثيم بنجاح!');
                    };
                }

                document.getElementById('nilePrivacySelect').value = localStorage.getItem('nile_privacy') || 'everyone';
                document.getElementById('nileThemeSelect').value = localStorage.getItem('nile_theme') || 'dark';
                modal.style.setProperty('display', 'flex', 'important');
            };

            function injectNileTopHeaderButton() {
                if (document.getElementById('nileStandardHeaderBtn')) return;
                var topBar = document.querySelector('.header') || document.querySelector('header') || document.body;
                if (topBar) {
                    var btn = document.createElement('button');
                    btn.id = 'nileStandardHeaderBtn';
                    btn.innerHTML = '⚙️';
                    btn.style.cssText = 'position: fixed !important; top: 14px !important; left: 16px !important; width: 38px !important; height: 38px !important; background: #1e293b !important; color: #38bdf8 !important; border: 1px solid #334155 !important; border-radius: 8px !important; font-size: 18px !important; cursor: pointer !important; display: flex !important; align-items: center !important; justify-content: center !important; z-index: 9999999 !important;';
                    btn.onclick = function(e) {
                        e.preventDefault(); e.stopPropagation();
                        openNileAdvancedSettings();
                    };
                    topBar.appendChild(btn);
                }
            }

            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', injectNileTopHeaderButton);
            } else {
                injectNileTopHeaderButton();
            }
            setInterval(injectNileTopHeaderButton, 1000);
        })();
        </script>
    </body>
    </html>
    """
    # 🚀 هنا قفلنا اللعبة: شيلنا الـ return القديم وبقينا بنعرض المتغير النصي مباشرة غصب عن السيرفر!
    return render_template_string(html_content)from flask import render_template_string, session # تأكد أن render_template_string مستدعاة فوق

@app.route('/')
def index():
    # كود الواجهة المطور ومقاوم لتمطيط الفريمات مدمج داخل البايثون مباشرة
    html_content = """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
        <title>نايل شات المطور</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
        
        <style>
            /* هنا محرك الثيمات لمنع اختفاء الألوان */
            body.nile-theme-dark { background: #0f172a !important; color: #f8fafc !important; }
            body.nile-theme-light { background: #ffffff !important; color: #1e293b !important; }
            body { transition: background 0.3s, color 0.3s; overflow: hidden; }
        </style>
    </head>
    <body>
        <header class="header">
        </header>

        <div id="chat-messages" style="height: calc(100vh - 120px); overflow-y: auto; padding: 15px;"></div>

        <script>
        (function() {
            var socket = typeof socket !== 'undefined' ? socket : (typeof io !== 'undefined' ? io() : null);
            var myProfile = { name: 'Abdallah', phone: '123', avatar: '' };

            // استرجاع الثيم المحفوظ فوراً من المتصفح عشان يتنه محفوظ وميتمسحش
            var savedTheme = localStorage.getItem('nile_theme') || 'dark';
            document.body.className = 'nile-theme-' + savedTheme;

            if (socket && socket.on) {
                socket.off('receive_message');
                socket.on('receive_message', function(data) { 
                    if ((data.room === 'nile_ai_room' || data.senderName === 'Nile AI') && typeof appendMessage === 'function') { 
                        appendMessage(data); 
                    } 
                });
            }

            window.openNileAdvancedSettings = function() {
                var modal = document.getElementById('nileAdvancedSettingsModal');
                if (!modal) {
                    modal = document.createElement('div');
                    modal.id = 'nileAdvancedSettingsModal';
                    modal.style.cssText = 'position: fixed !important; top: 0 !important; left: 0 !important; width: 100vw !important; height: 100vh !important; background: #0f172a !important; color: #f8fafc !important; z-index: 2147483647 !important; direction: rtl !important; box-sizing: border-box !important; display: flex !important; flex-direction: column !important; overflow: hidden !important; margin: 0 !important; padding: 0 !important;';
                    
                    modal.innerHTML = `
                        <div style="background: #1e293b !important; padding: 0 16px !important; display: flex !important; align-items: center !important; gap: 16px !important; border-bottom: 1px solid #334155 !important; height: 60px !important;">
                            <button id="nileCloseSettingsBtn" style="background: transparent !important; border: none !important; color: #38bdf8 !important; font-size: 22px !important; cursor: pointer !important;">➡️</button>
                            <h2 style="margin: 0 !important; font-size: 18px !important; font-weight: 600 !important; color: #f8fafc !important;">إإعدادات المنظومة المطورة</h2>
                        </div>
                        
                        <div style="flex: 1 !important; overflow-y: auto !important; padding: 20px !important; display: flex !important; flex-direction: column !important; gap: 20px !important;">
                            <div style="display: flex !important; align-items: center !important; justify-content: space-between !important; padding: 12px 0 !important; border-bottom: 1px solid #334155 !important;">
                                <span style="font-size: 15px !important; font-weight: 600 !important;">🔒 مستوى الخصوصية والأمان</span>
                                <select id="nilePrivacySelect" style="background: #1e293b !important; color: white !important; border: 1px solid #475569 !important; padding: 8px !important; border-radius: 6px !important; width: 130px !important;">
                                    <option value="everyone">الجميع</option>
                                    <option value="contacts">جهات الاتصال</option>
                                    <option value="nobody">إخفاء تماماً</option>
                                </select>
                            </div>

                            <div style="display: flex !important; align-items: center !important; justify-content: space-between !important; padding: 12px 0 !important; border-bottom: 1px solid #334155 !important;">
                                <span style="font-size: 15px !important; font-weight: 600 !important;">🎨 واجهة نايل شات</span>
                                <select id="nileThemeSelect" style="background: #1e293b !important; color: white !important; border: 1px solid #475569 !important; padding: 8px !important; border-radius: 6px !important; width: 130px !important;">
                                    <option value="dark">مظلم قياسي</option>
                                    <option value="light">وضع فاتح</option>
                                </select>
                            </div>

                            <div style="margin-top: auto !important; padding-top: 25px !important;">
                                <button id="nileSaveSettingsBtn" style="width: 100% !important; background: #22c55e !important; color: white !important; border: none !important; padding: 12px !important; border-radius: 8px !important; cursor: pointer !important; font-weight: bold !important; font-size: 15px !important;">حفظ وتطبيق التغييرات</button>
                            </div>
                        </div>
                    `;
                    document.body.appendChild(modal);

                    document.getElementById('nileCloseSettingsBtn').onclick = function() {
                        modal.style.setProperty('display', 'none', 'important');
                    };

                    document.getElementById('nileSaveSettingsBtn').onclick = function() {
                        var chosenTheme = document.getElementById('nileThemeSelect').value;
                        localStorage.setItem('nile_privacy', document.getElementById('nilePrivacySelect').value);
                        localStorage.setItem('nile_theme', chosenTheme);
                        
                        // تطبيق الثيم فوراً
                        document.body.className = 'nile-theme-' + chosenTheme;
                        modal.style.setProperty('display', 'none', 'important');
                        alert('تم حفظ الإعدادات وتثبيت الثيم بنجاح!');
                    };
                }

                document.getElementById('nilePrivacySelect').value = localStorage.getItem('nile_privacy') || 'everyone';
                document.getElementById('nileThemeSelect').value = localStorage.getItem('nile_theme') || 'dark';
                modal.style.setProperty('display', 'flex', 'important');
            };

            function injectNileTopHeaderButton() {
                if (document.getElementById('nileStandardHeaderBtn')) return;
                var topBar = document.querySelector('.header') || document.querySelector('header') || document.body;
                if (topBar) {
                    var btn = document.createElement('button');
                    btn.id = 'nileStandardHeaderBtn';
                    btn.innerHTML = '⚙️';
                    btn.style.cssText = 'position: fixed !important; top: 14px !important; left: 16px !important; width: 38px !important; height: 38px !important; background: #1e293b !important; color: #38bdf8 !important; border: 1px solid #334155 !important; border-radius: 8px !important; font-size: 18px !important; cursor: pointer !important; display: flex !important; align-items: center !important; justify-content: center !important; z-index: 9999999 !important;';
                    btn.onclick = function(e) {
                        e.preventDefault(); e.stopPropagation();
                        openNileAdvancedSettings();
                    };
                    topBar.appendChild(btn);
                }
            }

            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', injectNileTopHeaderButton);
            } else {
                injectNileTopHeaderButton();
            }
            setInterval(injectNileTopHeaderButton, 1000);
        })();
        </script>
    </body>
    </html>
    """
    # 🚀 هنا قفلنا اللعبة: شيلنا الـ return القديم وبقينا بنعرض المتغير النصي مباشرة غصب عن السيرفر!
    return render_template_string(html_content)
    
@app.route('/')
def index():
    # كود الواجهة المطور ومقاوم لتمطيط الفريمات مدمج داخل البايثون مباشرة
    html_content = """
    <!DOCTYPE html>
    <html lang="ar" dir="rtl">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
        <title>نايل شات المطور</title>
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
        
        <style>
            /* هنا محرك الثيمات لمنع اختفاء الألوان */
            body.nile-theme-dark { background: #0f172a !important; color: #f8fafc !important; }
            body.nile-theme-light { background: #ffffff !important; color: #1e293b !important; }
            body { transition: background 0.3s, color 0.3s; overflow: hidden; }
        </style>
    </head>
    <body>
        <header class="header">
        </header>

        <div id="chat-messages" style="height: calc(100vh - 120px); overflow-y: auto; padding: 15px;"></div>

        <script>
        (function() {
            var socket = typeof socket !== 'undefined' ? socket : (typeof io !== 'undefined' ? io() : null);
            var myProfile = { name: 'Abdallah', phone: '123', avatar: '' };

            // استرجاع الثيم المحفوظ فوراً من المتصفح عشان يتنه محفوظ وميتمسحش
            var savedTheme = localStorage.getItem('nile_theme') || 'dark';
            document.body.className = 'nile-theme-' + savedTheme;

            if (socket && socket.on) {
                socket.off('receive_message');
                socket.on('receive_message', function(data) { 
                    if ((data.room === 'nile_ai_room' || data.senderName === 'Nile AI') && typeof appendMessage === 'function') { 
                        appendMessage(data); 
                    } 
                });
            }

            window.openNileAdvancedSettings = function() {
                var modal = document.getElementById('nileAdvancedSettingsModal');
                if (!modal) {
                    modal = document.createElement('div');
                    modal.id = 'nileAdvancedSettingsModal';
                    modal.style.cssText = 'position: fixed !important; top: 0 !important; left: 0 !important; width: 100vw !important; height: 100vh !important; background: #0f172a !important; color: #f8fafc !important; z-index: 2147483647 !important; direction: rtl !important; box-sizing: border-box !important; display: flex !important; flex-direction: column !important; overflow: hidden !important; margin: 0 !important; padding: 0 !important;';
                    
                    modal.innerHTML = `
                        <div style="background: #1e293b !important; padding: 0 16px !important; display: flex !important; align-items: center !important; gap: 16px !important; border-bottom: 1px solid #334155 !important; height: 60px !important;">
                            <button id="nileCloseSettingsBtn" style="background: transparent !important; border: none !important; color: #38bdf8 !important; font-size: 22px !important; cursor: pointer !important;">➡️</button>
                            <h2 style="margin: 0 !important; font-size: 18px !important; font-weight: 600 !important; color: #f8fafc !important;">إإعدادات المنظومة المطورة</h2>
                        </div>
                        
                        <div style="flex: 1 !important; overflow-y: auto !important; padding: 20px !important; display: flex !important; flex-direction: column !important; gap: 20px !important;">
                            <div style="display: flex !important; align-items: center !important; justify-content: space-between !important; padding: 12px 0 !important; border-bottom: 1px solid #334155 !important;">
                                <span style="font-size: 15px !important; font-weight: 600 !important;">🔒 مستوى الخصوصية والأمان</span>
                                <select id="nilePrivacySelect" style="background: #1e293b !important; color: white !important; border: 1px solid #475569 !important; padding: 8px !important; border-radius: 6px !important; width: 130px !important;">
                                    <option value="everyone">الجميع</option>
                                    <option value="contacts">جهات الاتصال</option>
                                    <option value="nobody">إخفاء تماماً</option>
                                </select>
                            </div>

                            <div style="display: flex !important; align-items: center !important; justify-content: space-between !important; padding: 12px 0 !important; border-bottom: 1px solid #334155 !important;">
                                <span style="font-size: 15px !important; font-weight: 600 !important;">🎨 واجهة نايل شات</span>
                                <select id="nileThemeSelect" style="background: #1e293b !important; color: white !important; border: 1px solid #475569 !important; padding: 8px !important; border-radius: 6px !important; width: 130px !important;">
                                    <option value="dark">مظلم قياسي</option>
                                    <option value="light">وضع فاتح</option>
                                </select>
                            </div>

                            <div style="margin-top: auto !important; padding-top: 25px !important;">
                                <button id="nileSaveSettingsBtn" style="width: 100% !important; background: #22c55e !important; color: white !important; border: none !important; padding: 12px !important; border-radius: 8px !important; cursor: pointer !important; font-weight: bold !important; font-size: 15px !important;">حفظ وتطبيق التغييرات</button>
                            </div>
                        </div>
                    `;
                    document.body.appendChild(modal);

                    document.getElementById('nileCloseSettingsBtn').onclick = function() {
                        modal.style.setProperty('display', 'none', 'important');
                    };

                    document.getElementById('nileSaveSettingsBtn').onclick = function() {
                        var chosenTheme = document.getElementById('nileThemeSelect').value;
                        localStorage.setItem('nile_privacy', document.getElementById('nilePrivacySelect').value);
                        localStorage.setItem('nile_theme', chosenTheme);
                        
                        // تطبيق الثيم فوراً
                        document.body.className = 'nile-theme-' + chosenTheme;
                        modal.style.setProperty('display', 'none', 'important');
                        alert('تم حفظ الإعدادات وتثبيت الثيم بنجاح!');
                    };
                }

                document.getElementById('nilePrivacySelect').value = localStorage.getItem('nile_privacy') || 'everyone';
                document.getElementById('nileThemeSelect').value = localStorage.getItem('nile_theme') || 'dark';
                modal.style.setProperty('display', 'flex', 'important');
            };

            function injectNileTopHeaderButton() {
                if (document.getElementById('nileStandardHeaderBtn')) return;
                var topBar = document.querySelector('.header') || document.querySelector('header') || document.body;
                if (topBar) {
                    var btn = document.createElement('button');
                    btn.id = 'nileStandardHeaderBtn';
                    btn.innerHTML = '⚙️';
                    btn.style.cssText = 'position: fixed !important; top: 14px !important; left: 16px !important; width: 38px !important; height: 38px !important; background: #1e293b !important; color: #38bdf8 !important; border: 1px solid #334155 !important; border-radius: 8px !important; font-size: 18px !important; cursor: pointer !important; display: flex !important; align-items: center !important; justify-content: center !important; z-index: 9999999 !important;';
                    btn.onclick = function(e) {
                        e.preventDefault(); e.stopPropagation();
                        openNileAdvancedSettings();
                    };
                    topBar.appendChild(btn);
                }
            }

            if (document.readyState === 'loading') {
                document.addEventListener('DOMContentLoaded', injectNileTopHeaderButton);
            } else {
                injectNileTopHeaderButton();
            }
            setInterval(injectNileTopHeaderButton, 1000);
        })();
        </script>
    </body>
    </html>
    """
    # 🚀 هنا قفلنا اللعبة: شيلنا الـ return القديم وبقينا بنعرض المتغير النصي مباشرة غصب عن السيرفر!
    return render_template_string(html_content)

@app.route('/static/manifest.json')
def serve_manifest():
    manifest_data = {
        "short_name": "NileChat", "name": "Nile Chat Pro 2026",
        "icons": [{"src": "/static/icon.png", "type": "image/png", "sizes": "512x512", "purpose": "any maskable"}],
        "start_url": "/", "background_color": "#0b141a", "theme_color": "#00a884",
        "display": "standalone", "orientation": "portrait"
    }
    return jsonify(manifest_data)

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
    ext = filename.split('.')[-1].lower()
    f_type = 'text'
    if ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']: f_type = 'image'
    elif ext in ['mp4', 'webm', 'ogg', 'mov']: f_type = 'video'
    elif ext in ['mp3', 'wav', 'aac', 'm4a']: f_type = 'audio'
    f_url = url_for('static', filename=f"uploads/{filename}", _external=True)
    return jsonify({'url': f_url, 'file_type': f_type, 'name': file.filename})

@socketio.on('register_user')
def handle_register(data):
    phone = str(data.get('phone')).strip()
    name = data.get('name', 'User')
    avatar = data.get('avatar', '')
    email = data.get('email', '')
    token = data.get('token', '')
    if phone:
        join_room(f"user_{phone}")
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name, theme_mode FROM profiles WHERE phone = ?", (phone,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("INSERT INTO profiles (phone, name, avatar, email, saved_login_token) VALUES (?, ?, ?, ?, ?)", (phone, name, avatar, email, token))
            theme = 'light'
        else:
            cursor.execute("UPDATE profiles SET name=?, avatar=?, email=?, saved_login_token=? WHERE phone=?", (name, avatar, email, token, phone))
            theme = row[1]
        conn.commit()
        conn.close()
        emit('login_persist_status', {'status': 'verified', 'phone': phone, 'theme_mode': theme, 'name': name, 'avatar': avatar})

@socketio.on('verify_saved_login')
def verify_saved_login(data):
    phone = str(data.get('phone')).strip()
    token = data.get('token', '')
    if phone and token:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name, avatar, theme_mode FROM profiles WHERE phone = ? AND saved_login_token = ?", (phone, token))
        row = cursor.fetchone()
        conn.close()
        if row:
            join_room(f"user_{phone}")
            emit('login_persist_status', {'status': 'success', 'phone': phone, 'name': row[0], 'avatar': row[1], 'theme_mode': row[2]})
            return
    emit('login_persist_status', {'status': 'failed'})

@socketio.on('update_profile_live')
def handle_profile_update(data):
    phone = str(data.get('phone')).strip()
    name = data.get('name')
    avatar = data.get('avatar')
    wallpaper = data.get('wallpaper', '')
    ringtone = data.get('custom_ringtone', 'default.mp3')
    voice_setting = data.get('voice_setting', 'normal')
    status_text = data.get('status_text', 'Available')
    theme_mode = data.get('theme_mode', 'light')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE profiles 
        SET name=?, avatar=?, wallpaper=?, custom_ringtone=?, voice_setting=?, status_text=?, theme_mode=? 
        WHERE phone=?
    """, (name, avatar, wallpaper, ringtone, voice_setting, status_text, theme_mode, phone))
    conn.commit()
    conn.close()
    emit('profile_updated_success', {'theme_mode': theme_mode}, room=f"user_{phone}")

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

@socketio.on('add_new_contact')
def add_new_contact(data):
    user_phone = str(data.get('user_phone')).strip()
    contact_phone = str(data.get('contact_phone')).strip()
    contact_name = data.get('contact_name', '').strip()
    
    if user_phone and contact_phone:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT phone, name, avatar FROM profiles WHERE phone = ?", (contact_phone,))
        profile = cursor.fetchone()
        if profile:
            cursor.execute("SELECT id FROM contacts WHERE user_phone = ? AND contact_phone = ?", (user_phone, contact_phone))
            if not cursor.fetchone():
                cursor.execute("INSERT INTO contacts (user_phone, contact_phone, contact_name, timestamp) VALUES (?, ?, ?, ?)", 
                               (user_phone, contact_phone, contact_name if contact_name else profile[1], time.time()))
                conn.commit()
            emit('contact_added_status', {'status': 'success', 'phone': profile[0], 'name': contact_name if contact_name else profile[1], 'avatar': profile[2]})
        else:
            emit('contact_added_status', {'status': 'not_found'})
        conn.close()

@socketio.on('get_my_contacts')
def get_my_contacts(data):
    user_phone = str(data.get('user_phone')).strip()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT c.contact_phone, c.contact_name, p.avatar, p.status_text 
        FROM contacts c JOIN profiles p ON c.contact_phone = p.phone 
        WHERE c.user_phone = ? ORDER BY c.contact_name ASC
    """, (user_phone,))
    rows = cursor.fetchall()
    conn.close()
    contacts_list = [{"phone": r[0], "name": r[1], "avatar": r[2], "status_text": r[3]} for r in rows]
    emit('my_contacts_list', {'contacts': contacts_list})

@socketio.on('create_private_group')
def create_private_group(data):
    name = data.get('group_name', '').strip()
    creator = str(data.get('creator_phone')).strip()
    members = data.get('members', [])
    if creator not in members:
        members.append(creator)
    
    if name and creator:
        group_id = f"group_{int(time.time() * 1000)}"
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO private_groups (id, name, creator, members, timestamp) VALUES (?, ?, ?, ?, ?)",
                       (group_id, name, creator, json.dumps(members), time.time()))
        conn.commit()
        conn.close()
        for member in members:
            emit('new_private_group_alert', {'group_id': group_id, 'name': name}, room=f"user_{member}")

@socketio.on('get_my_private_groups')
def get_my_private_groups(data):
    phone = str(data.get('user_phone')).strip()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, creator, members FROM private_groups")
    rows = cursor.fetchall()
    conn.close()
    my_groups = []
    for r in rows:
        members_list = json.loads(r[3])
        if phone in members_list:
            my_groups.append({"id": r[0], "name": r[1], "creator": r[2], "members": members_list})
    emit('my_private_groups_list', {'groups': my_groups})

@socketio.on('join_room')
def on_join_room(data):
    room = data.get('room', 'public_room')
    join_room(room)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, room, sender, text, file_type, file_name, reactions, reply_to, phone, is_edited, star_status 
        FROM messages WHERE room = ? ORDER BY timestamp ASC
    """, (room,))
    rows = cursor.fetchall()
    conn.close()
    history = [{
        "id": r[0], "room": r[1], "sender": r[2], "text": r[3], "file_type": r[4], 
        "file_name": r[5], "reactions": r[6], "reply_to": r[7], "phone": r[8],
        "is_edited": r[9], "star_status": r[10]
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
    
    if not msg_id:
        msg_id = f"msg-{int(time.time() * 1000)}"
        data['id'] = msg_id

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO messages (id, room, sender, phone, text, timestamp, file_type, file_name, reply_to) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (msg_id, room, sender, phone, text, time.time(), file_type, file_name, reply_to))
    conn.commit()
    
    emit('message', data, room=room)
    emit('message_delivery_receipt', {'id': msg_id, 'status': 'delivered'}, room=room)

    if room == 'AI_bot' and str(phone) != 'AI_SYSTEM':
        user_specific_room = f"ai_room_{phone}"
        join_room(user_specific_room)
        
        ai_reply = get_groq_ai_response(text)
        ai_msg_id = f"msg-ai-{int(time.time() * 1000)}"
        
        ai_data = {
            'id': ai_msg_id, 
            'room': 'AI_bot', 
            'sender': 'Nile AI', 
            'phone': 'AI_SYSTEM', 
            'text': ai_reply, 
            'file_type': 'text', 
            'file_name': '', 
            'reply_to': msg_id, 
            'is_edited': 0, 
            'star_status': 0
        }
        
        cursor.execute("""
            INSERT INTO messages (id, room, sender, phone, text, timestamp, file_type, file_name, reply_to) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (ai_msg_id, 'AI_bot', 'Nile AI', 'AI_SYSTEM', ai_reply, time.time(), 'text', '', msg_id))
        conn.commit()
        
        emit('message', ai_data, room=user_specific_room)
    conn.close()

@socketio.on('edit_message')
def handle_edit_message(data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE messages SET text=?, is_edited=1 WHERE id=?", (data.get('text'), data.get('id')))
    conn.commit()
    conn.close()
    emit('message_edited', data, room=data.get('room'))

@socketio.on('delete_message')
def handle_delete_message(data):
    message_id = data.get('id') or data.get('message_id')
    if message_id:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM messages WHERE id=?", (message_id,))
        conn.commit()
        conn.close()
        emit('message_deleted', {'id': message_id, 'message_id': message_id, 'room': data.get('room')}, room=data.get('room'))

@socketio.on('toggle_star_message')
def handle_toggle_star(data):
    msg_id = data.get('id')
    status = data.get('star_status', 0)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE messages SET star_status=? WHERE id=?", (status, msg_id))
    conn.commit()
    conn.close()
    emit('message_star_updated', data, room=data.get('room'))

@socketio.on('update_reaction')
def handle_reaction(data):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE messages SET reactions=? WHERE id=?", (data.get('reactions'), data.get('id')))
    conn.commit()
    conn.close()
    emit('reaction_updated', data, room=data.get('room'))

@socketio.on('add_reaction')
def handle_add_reaction(data):
    message_id = data.get('message_id')
    emoji = data.get('emoji')
    if message_id and emoji:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('UPDATE messages SET reactions = ? WHERE id = ?', (emoji, message_id))
        conn.commit()
        conn.close()
        emit('reaction_added', {'message_id': message_id, 'emoji': emoji, 'room': data.get('room')}, broadcast=True)

@socketio.on('forward_or_reply')
def handle_forward_reply(data):
    phone = session.get('user_phone') or data.get('phone')
    message_text = data.get('message') or data.get('text')
    reply_to_id = data.get('reply_to_id') or data.get('reply_to')
    is_forwarded = data.get('is_forwarded', False)
    room = data.get('room', 'public_room')
    msg_id = f"msg-{int(time.time() * 1000)}"
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO messages (id, room, sender, phone, text, timestamp, reply_to, is_forward) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (msg_id, room, data.get('sender', 'User'), phone, message_text, time.time(), reply_to_id, 1 if is_forwarded else 0))
    conn.commit()
    conn.close()
    
    data['id'] = msg_id
    emit('message', data, room=room)

@socketio.on('add_story')
def handle_story(data):
    story_id = f"story-{int(time.time() * 1000)}"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO stories (id, sender, phone, text, file_type, timestamp, caption) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (story_id, data.get('sender'), data.get('phone'), data.get('text'), data.get('file_type'), time.time(), data.get('caption', '')))
    conn.commit()
    conn.close()
    emit('new_story_alert', broadcast=True)

@socketio.on('get_stories')
def get_stories():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT s.id, s.sender, s.text, s.file_type, p.avatar, s.phone, s.caption 
        FROM stories s LEFT JOIN profiles p ON s.phone = p.phone ORDER BY s.timestamp DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    emit('stories_list', {'stories': [{
        "id": r[0], "sender": r[1], "text": r[2], "file_type": r[3], 
        "avatar": r[4], "phone": r[5], "caption": r[6]
    } for r in rows]})

@socketio.on('create_unit')
def create_unit(data):
    u_id = f"unit_{int(time.time() * 1000)}"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO units (id, name, type, creator, description) 
        VALUES (?, ?, ?, ?, ?)
    """, (u_id, data.get('name'), data.get('type'), data.get('creator'), data.get('description', '')))
    conn.commit()
    conn.close()
    emit('unit_created_alert', broadcast=True)

@socketio.on('get_units')
def get_units():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, type, description FROM units")
    rows = cursor.fetchall()
    conn.close()
    emit('units_list', {'units': [{"id": r[0], "name": r[1], "type": r[2], "description": r[3]} for r in rows]})

@socketio.on('add_feed_post')
def add_feed_post(data):
    post_id = f"post-{int(time.time() * 1000)}"
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO feed_posts (id, sender, phone, avatar, text, media_url, file_type, timestamp) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (post_id, data.get('sender'), data.get('phone'), data.get('avatar'), data.get('text'), data.get('media_url', ''), data.get('file_type', 'text')))
    conn.commit()
    conn.close()
    emit('new_feed_post_alert', broadcast=True)

@socketio.on('like_feed_post')
def like_feed_post(data):
    post_id = data.get('post_id')
    phone = data.get('phone')
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT likes_json FROM feed_posts WHERE id=?", (post_id,))
    row = cursor.fetchone()
    if row:
        likes = json.loads(row[0])
        if phone in likes: likes.remove(phone)
        else: likes.append(phone)
        cursor.execute("UPDATE feed_posts SET likes_count=?, likes_json=? WHERE id=?", (len(likes), json.dumps(likes), post_id))
        conn.commit()
    conn.close()
    emit('new_feed_post_alert', broadcast=True)

@socketio.on('get_feed_posts')
def get_feed_posts():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT id, sender, text, media_url, avatar, file_type, likes_count, likes_json FROM feed_posts ORDER BY timestamp DESC")
    rows = cursor.fetchall()
    conn.close()
    emit('feed_posts_list', {'posts': [{
        "id": r[0], "sender": r[1], "text": r[2], "media_url": r[3], 
        "avatar": r[4], "file_type": r[5], "likes": r[6], "likes_json": json.loads(r[7])
    } for r in rows]})

@socketio.on('call_signal')
def handle_call_signal(data):
    target = data.get('target_phone')
    emit('call_signal', data, room=f"user_{target}")

@socketio.on('webrtc_ice_candidate')
def handle_ice(data):
    target = data.get('target_phone')
    emit('webrtc_ice_candidate', data, room=f"user_{target}")

@socketio.on('webrtc_offer_answer')
def handle_offer_answer(data):
    target = data.get('target_phone')
    emit('webrtc_offer_answer', data, room=f"user_{target}")

@socketio.on('request_qr_code_link')
def generate_qr_info(data):
    room = data.get('room')
    user = data.get('phone')
    if room and user:
        qr_string = f"nilechat://join?room={room}&invited_by={user}"
        emit('qr_code_generated', {'qr_string': qr_string, 'room': room}, room=f"user_{user}")

@socketio.on('send_message')
def handle_nile_notification(data):
    room = data.get('room')
    if room and data.get('senderName') != 'Nile AI':
        emit('receive_message', data, room=room, include_self=False)
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
