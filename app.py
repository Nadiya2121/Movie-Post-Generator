import os
import threading
import random
import json
import io
import asyncio
import re
import html
import urllib.parse
import aiohttp
from flask import Flask, render_template_string, request, redirect, url_for, session, jsonify
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode

# --- কনফিগারেশন এরিয়া ---
API_ID = int(os.environ.get('API_ID', 29462738)) 
API_HASH = os.environ.get('API_HASH', '297f51aaab99720a09e80273628c3c24') 
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8531734553:AAE8Ev_XmhH9zNXygZTF1PLpI0YuqTSMc28') 
TMDB_API_KEY = os.environ.get('TMDB_API_KEY', '7dc544d9253bccc3cfecc1c677f69819') 
BOT_USERNAME = os.environ.get('BOT_USERNAME', 'MoviePostGeneratorBot') 

OWNER_ID = int(os.environ.get('OWNER_ID', 8297458824)) 
DATABASE_CHANNEL_ID = int(os.environ.get('DATABASE_CHANNEL_ID', -1003506219023)) 

OWNER_DIRECT_LINK = os.environ.get('OWNER_DIRECT_LINK', 'https://omg10.com/4/11047054') 
REVENUE_SHARE_PERCENT = int(os.environ.get('REVENUE_SHARE_PERCENT', 20)) 
IMGBB_API_KEY = os.environ.get('IMGBB_API_KEY', 'c082ca1c9578c2f544c5845a07eda70a') 

AUTO_DELETE_DELAY = 300 
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

http_session = None
web_app = Flask(__name__)
web_app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'supersecretkey_bdmoviezone')

# --- ডেটাবেজ ইনিশিয়ালাইজেশন ---
MONGO_URI = os.environ.get('MONGO_URI') 
mongo_client = None
db_mongo = None

if MONGO_URI:
    try:
        import pymongo
        mongo_client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        db_mongo = mongo_client['BDMovieZoneBot']
        mongo_client.server_info() 
        print("MongoDB Connected Successfully!")
    except Exception as e:
        print(f"MongoDB Connection Failed: {e}. Falling back to Local JSON.")
        db_mongo = None

# --- ডেটা রিড ও রাইট মেকানিজম ---
def load_movies_db():
    if db_mongo is not None:
        try:
            return list(db_mongo['movies'].find({}))
        except Exception:
            pass
    if os.path.exists("movies_db.json"):
        try:
            with open("movies_db.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []

def save_movie_to_db(movie_id, data):
    data['_id'] = movie_id
    if db_mongo is not None:
        try:
            db_mongo['movies'].update_one({'_id': movie_id}, {'$set': data}, upsert=True)
            return
        except Exception:
            pass
    
    # JSON Fallback
    movies = load_movies_db()
    # ডুপ্লিকেট এড়াতে রিমুভ করে নতুন করে রাইট
    movies = [m for m in movies if m.get('_id') != movie_id]
    movies.append(data)
    with open("movies_db.json", "w", encoding="utf-8") as f:
        json.dump(movies, f, indent=4, ensure_ascii=False)

def delete_movie_from_db(movie_id):
    if db_mongo is not None:
        try:
            db_mongo['movies'].delete_one({'_id': movie_id})
            return
        except Exception:
            pass
    movies = load_movies_db()
    movies = [m for m in movies if m.get('_id') != movie_id]
    with open("movies_db.json", "w", encoding="utf-8") as f:
        json.dump(movies, f, indent=4, ensure_ascii=False)

# CORS হেডার যুক্ত করা (ব্লগার ডোমেইন থেকে রিকোয়েস্ট অ্যালাও করার জন্য)
@web_app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    return response

# ==================== এপিআই এন্ডপয়েন্ট (API Endpoints) ====================

@web_app.route('/api/movies', methods=['GET'])
def get_all_movies_api():
    """ব্লগার সাইট এই এপিআই থেকে সমস্ত মুভির ডাটা নিয়ে দেখাবে"""
    movies = load_movies_db()
    return jsonify(movies)

@web_app.route('/api/movies/<movie_id>', methods=['GET'])
def get_single_movie_api(movie_id):
    movies = load_movies_db()
    for m in movies:
        if m.get('_id') == movie_id:
            return jsonify(m)
    return jsonify({"error": "Movie not found"}), 404

@web_app.route('/api/tmdb-fetch', methods=['POST'])
def tmdb_fetch_api():
    """অ্যাডমিন প্যানেল থেকে TMDB ডাটা দ্রুত সিঙ্ক করার এপিআই"""
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
        
    data = request.json or {}
    tmdb_input = data.get('tmdb_input', '').strip()
    is_tv = data.get('is_tv', False)
    
    # আইডি এক্সট্রাক্ট করা (লিঙ্ক বা ডিরেক্ট আইডি থেকে)
    tmdb_id = tmdb_input
    if "themoviedb.org" in tmdb_input:
        match = re.search(r"/(movie|tv)/(\d+)", tmdb_input)
        if match:
            tmdb_id = match.group(2)
            is_tv = (match.group(1) == "tv")
            
    endpoint = "tv" if is_tv else "movie"
    url = f"https://api.themoviedb.org/3/{endpoint}/{tmdb_id}?api_key={TMDB_API_KEY}&append_to_response=images"
    
    # এসিঙ্ক্রোনাসলি কল সম্পন্ন করতে loop ক্রিয়েট
    async def fetch():
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=10) as r:
                if r.status != 200:
                    return None
                return await r.json()
                
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    res_data = loop.run_until_complete(fetch())
    
    if not res_data:
        return jsonify({"error": "Failed to fetch data from TMDB"}), 400
        
    title = res_data.get('title') if not is_tv else res_data.get('name')
    release_date = res_data.get('release_date') if not is_tv else res_data.get('first_air_date')
    year = release_date.split('-')[0] if release_date else 'N/A'
    rating = f"{res_data.get('vote_average'):.1f}/10" if res_data.get('vote_average') else 'N/A'
    genres = ", ".join([g['name'] for g in res_data.get('genres', [])])
    poster = f"https://image.tmdb.org/t/p/w500{res_data.get('poster_path')}" if res_data.get('poster_path') else 'https://via.placeholder.com/300x450'
    backdrop = f"https://image.tmdb.org/t/p/original{res_data.get('backdrop_path')}" if res_data.get('backdrop_path') else 'https://via.placeholder.com/1280x720'
    plot = res_data.get('overview', 'No description available.')

    # স্ক্রিনশট ফিল্টারিং
    backdrops = res_data.get('images', {}).get('backdrops', [])
    screenshots = [f"https://image.tmdb.org/t/p/w780{bg.get('file_path')}" for bg in backdrops[:4] if bg.get('file_path')]

    return jsonify({
        "title": f"{title} ({year})",
        "poster": poster,
        "backdrop": backdrop,
        "rating": rating,
        "genres": genres,
        "plot": plot,
        "screenshots": screenshots
    })


# ==================== ওয়েব অ্যাডমিন প্যানেল ভিউজ ====================

@web_app.route('/')
def home():
    return "BD Movie Zone API & Bot Server is active!"

@web_app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        else:
            return render_template_string(LOGIN_HTML, error="ভুল পাসওয়ার্ড! আবার ট্রাই করুন।")
    return render_template_string(LOGIN_HTML)

@web_app.route('/admin')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    movies = load_movies_db()
    return render_template_string(DASHBOARD_HTML, movies=movies)

@web_app.route('/admin/edit/<movie_id>', methods=['GET', 'POST'])
def edit_movie(movie_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
        
    movies = load_movies_db()
    movie = next((m for m in movies if m.get('_id') == movie_id), None)
    if not movie:
        return "Movie not found", 404
        
    if request.method == 'POST':
        movie['movie_data']['title'] = request.form.get('title')
        movie['movie_data']['poster'] = request.form.get('poster')
        movie['movie_data']['backdrop'] = request.form.get('backdrop')
        movie['movie_data']['rating'] = request.form.get('rating')
        movie['movie_data']['lang'] = request.form.get('lang')
        movie['movie_data']['genres'] = request.form.get('genres')
        movie['movie_data']['plot'] = request.form.get('plot')
        
        screens = request.form.get('screenshots', '').split('\n')
        movie['movie_data']['screenshots'] = [s.strip() for s in screens if s.strip()]
        
        if movie.get('type') == 'series':
            movie['season'] = request.form.get('season')
            
        save_movie_to_db(movie_id, movie)
        return redirect(url_for('admin_dashboard'))
        
    return render_template_string(EDIT_HTML, movie=movie)

@web_app.route('/admin/delete/<movie_id>')
def delete_movie(movie_id):
    if not session.get('admin_logged_in'):
        return redirect(url_for('admin_login'))
    delete_movie_from_db(movie_id)
    return redirect(url_for('admin_dashboard'))

@web_app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))

# Flask সার্ভার রান করার ফাংশন
def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)


# ==================== পাইগ্রাম টেলিগ্রাম বট লজিক ====================

app = Client("movie_post_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
user_states = {}

async def upload_image_to_cloud(file_id):
    global http_session
    if not http_session: return None
    try:
        get_file_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
        async with http_session.get(get_file_url, timeout=10) as resp:
            res = await resp.json()
        if not res.get('ok'): return None
        file_path = res['result']['file_path']
        download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        async with http_session.get(download_url, timeout=12) as resp:
            img_data = await resp.read()
        
        # Catbox Upload
        url = "https://catbox.moe/user/api.php"
        form_data = aiohttp.FormData()
        form_data.add_field('reqtype', 'fileupload')
        form_data.add_field('fileToUpload', img_data, filename='photo.jpg', content_type='image/jpeg')
        async with http_session.post(url, data=form_data, timeout=10) as resp:
            res_text = await resp.text()
            if resp.status == 200 and res_text.startswith('http'):
                return res_text.strip()
    except Exception as e:
        print(f"Upload failed: {e}")
    return None

async def save_file_to_db_channel(from_chat_id, message_id, file_type, file_id, caption=""):
    global http_session
    if not http_session: return None
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument" if file_type == 'document' else f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
        payload = {"chat_id": DATABASE_CHANNEL_ID, "caption": caption, "parse_mode": "HTML"}
        if file_type == 'document': payload["document"] = file_id
        else: payload["video"] = file_id
        async with http_session.post(url, json=payload, timeout=15) as resp:
            res = await resp.json()
        if res.get('ok'): return res['result']['message_id']
    except Exception as e:
         print(f"Forward to DB failed: {e}")
    return None

@app.on_message(filters.command("start") & filters.private)
async def handle_start(client, message):
    chat_id = message.chat.id
    text = message.text.strip() if message.text else ""
    
    # স্টার্ট লিংক ডিকোড করা
    if len(text.split()) > 1:
        param = text.split()[1]
        if param.startswith("msg_"):
            db_msg_id = int(param.split("_")[1])
            try:
                user_msg_id = await client.copy_message(chat_id, DATABASE_CHANNEL_ID, db_msg_id)
                warning_text = f"⚠️ এই ফাইলটি আগামী **{int(AUTO_DELETE_DELAY/60)} মিনিটের** মধ্যে ডিলিট হয়ে যাবে। এখনই আপনার Saved Messages এ ফরোয়ার্ড করে রাখুন।"
                sent_warning = await client.send_message(chat_id, warning_text)
                asyncio.create_task(delete_messages_after_delay(chat_id, [user_msg_id.id, sent_warning.id], AUTO_DELETE_DELAY))
            except Exception as e:
                await client.send_message(chat_id, f"❌ ফাইলটি লোড করা যাচ্ছে না: {e}")
        return

    user_states[chat_id] = {}
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 মুভি পোস্ট", callback_data="type_movie"),
         InlineKeyboardButton("📺 ওয়েব সিরিজ পোস্ট", callback_data="type_series")]
    ])
    await client.send_message(chat_id, "👋 **BD Movie Zone ডাইনামিক পোস্ট জেনারেটর প্যানেল!**\nক্যাটাগরি সিলেক্ট করুন:", reply_markup=markup)

@app.on_callback_query()
async def handle_query(client, callback_query):
    chat_id = callback_query.message.chat.id
    data = callback_query.data
    
    if data in ["type_movie", "type_series"]:
        p_type = "movie" if data == "type_movie" else "series"
        user_states[chat_id] = {'type': p_type, 'step': 'waiting_for_search'}
        await callback_query.edit_message_text("🔍 অনুগ্রহ করে ইংরেজি নাম লিখে সার্চ করুন অথবা TMDB লিঙ্কটি সরাসরি পাঠান:")
        
    elif data.startswith("select_"):
        parts = data.split("_")
        movie_id = parts[1]
        is_tv = parts[2] == "tv"
        await fetch_tmdb_details(client, chat_id, movie_id, is_tv)
        
    elif data.startswith("lang_"):
        selected_lang = data.split("_")[1]
        user_states[chat_id]['movie_data']['lang'] = selected_lang
        
        if user_states[chat_id]['type'] == 'movie':
            user_states[chat_id]['step'] = 'waiting_for_480p'
            await client.send_message(chat_id, "👉 এখন মুভির **480p** ফাইলটি ফরোয়ার্ড করুন (না থাকলে /skip লিখুন):")
        else:
            user_states[chat_id]['step'] = 'waiting_for_season'
            await client.send_message(chat_id, "👉 এবার সিজন নাম্বারটি লিখে পাঠান (উদা: 1, 2):")

async def fetch_tmdb_details(client, chat_id, movie_id, is_tv):
    global http_session
    endpoint = "tv" if is_tv else "movie"
    url = f"https://api.themoviedb.org/3/{endpoint}/{movie_id}?api_key={TMDB_API_KEY}&append_to_response=images"
    try:
        async with http_session.get(url, timeout=10) as resp:
            data = await resp.json()
        title = data.get('title') if not is_tv else data.get('name')
        release_date = data.get('release_date') if not is_tv else data.get('first_air_date')
        year = release_date.split('-')[0] if release_date else 'N/A'
        rating = f"{data.get('vote_average'):.1f}/10" if data.get('vote_average') else 'N/A'
        genres = ", ".join([g['name'] for g in data.get('genres', [])])
        
        poster = f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}" if data.get('poster_path') else 'https://via.placeholder.com/300x450'
        backdrop = f"https://image.tmdb.org/t/p/original{data.get('backdrop_path')}" if data.get('backdrop_path') else 'https://via.placeholder.com/1280x720'
        plot = data.get('overview', 'No description available.')

        backdrops = data.get('images', {}).get('backdrops', [])
        screenshots = [f"https://image.tmdb.org/t/p/w780{bg.get('file_path')}" for bg in backdrops[:4] if bg.get('file_path')]

        user_states[chat_id]['movie_data'] = {
            'title': f"{title} ({year})",
            'poster': poster,
            'backdrop': backdrop,
            'rating': rating,
            'genres': genres,
            'plot': plot,
            'screenshots': screenshots
        }
        await send_language_picker(client, chat_id)
    except Exception as e:
        await client.send_message(chat_id, "❌ TMDB ডাটা লোড করতে ত্রুটি ঘটেছে!")

@app.on_message(filters.private)
async def handle_all_messages(client, message):
    chat_id = message.chat.id
    if chat_id not in user_states or 'step' not in user_states[chat_id]:
        return

    state = user_states[chat_id]['step']
    p_type = user_states[chat_id].get('type')

    if state == 'waiting_for_search' and message.text:
        text_input = message.text.strip()
        # TMDB লিঙ্ক পার্স করা
        if "themoviedb.org" in text_input:
            match = re.search(r"/(movie|tv)/(\d+)", text_input)
            if match:
                is_tv = (match.group(1) == "tv")
                await fetch_tmdb_details(client, chat_id, match.group(2), is_tv)
                return

        # সাধারণ সার্চ কুয়েরি
        is_tv_str = "tv" if p_type == "series" else "movie"
        url = f"https://api.themoviedb.org/3/search/{is_tv_str}?api_key={TMDB_API_KEY}&query={urllib.parse.quote(text_input)}"
        async with http_session.get(url) as r:
            res = await r.json()
        results = res.get('results', [])
        if results:
            markup = []
            for item in results[:5]:
                name = item.get('title') if p_type == "movie" else item.get('name')
                release = item.get('release_date') if p_type == "movie" else item.get('first_air_date')
                year = release.split('-')[0] if release else 'N/A'
                markup.append([InlineKeyboardButton(f"{name} ({year})", callback_data=f"select_{item['id']}_{is_tv_str}")])
            await client.send_message(chat_id, "🔍 কোন মুভি/সিরিজটি আপলোড করতে চান সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(markup))
        else:
            await client.send_message(chat_id, "❌ কোনো তথ্য খুঁজে পাওয়া যায়নি!")

    # --- মুভির ফাইল রিসিভ ---
    elif p_type == 'movie' and state in ['waiting_for_480p', 'waiting_for_720p', 'waiting_for_1080p']:
        file_msg_id = ""
        if message.document or message.video:
            file_type = 'document' if message.document else 'video'
            file_id = message.document.file_id if message.document else message.video.file_id
            
            q_str = "480p (SD)" if state == 'waiting_for_480p' else "720p (HD)" if state == 'waiting_for_720p' else "1080p (FHD)"
            cap = (f"🎬 <b>{user_states[chat_id]['movie_data']['title']}</b>\n"
                   f"💿 Quality: <b>{q_str}</b>\n🗣 Language: {user_states[chat_id]['movie_data']['lang']}")
            
            db_msg_id = await save_file_to_db_channel(chat_id, message.id, file_type, file_id, cap)
            if db_msg_id: file_msg_id = f"msg_{db_msg_id}"
        elif message.text and message.text.lower().strip() == '/skip':
            file_msg_id = ""
        else:
            await client.send_message(chat_id, "⚠️ ফাইল পাঠান অথবা এড়াতে /skip লিখুন।")
            return

        if state == 'waiting_for_480p':
            user_states[chat_id]['dl_480_key'] = file_msg_id
            user_states[chat_id]['step'] = 'waiting_for_720p'
            await client.send_message(chat_id, "👉 এবার **720p (HD)** ফাইলটি ফরোয়ার্ড করুন (না থাকলে /skip লিখুন):")
        elif state == 'waiting_for_720p':
            user_states[chat_id]['dl_720_key'] = file_msg_id
            user_states[chat_id]['step'] = 'waiting_for_1080p'
            await client.send_message(chat_id, "👉 এবার **1080p (FullHD)** ফাইলটি ফরোয়ার্ড করুন (না থাকলে /skip লিখুন):")
        elif state == 'waiting_for_1080p':
            user_states[chat_id]['dl_1080_key'] = file_msg_id
            
            # ডাটাবেজে ফাইনাল পোস্ট ডাটা সেভ
            m_id = "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(12))
            movie_post_data = {
                "type": "movie",
                "movie_data": user_states[chat_id]['movie_data'],
                "dl_links": {
                    "480p": user_states[chat_id].get('dl_480_key', ''),
                    "720p": user_states[chat_id].get('dl_720_key', ''),
                    "1080p": user_states[chat_id].get('dl_1080_key', '')
                },
                "status": "published"
            }
            save_movie_to_db(m_id, movie_post_data)
            
            app_url = os.environ.get('APP_URL', 'https://your-bot-domain.koyeb.app').rstrip('/')
            await client.send_message(chat_id, f"🎉 **মুভিটি সফলভাবে ডাটাবেজে পাবলিশ হয়েছে!**\n\n"
                                              f"🔗 আপনার blogger হোমপেজে এটি স্বয়ংক্রিয়ভাবে লাইভ হয়ে গেছে।\n"
                                              f"🛠️ কোনো ভুল সংশোধন করতে অ্যাডমিন প্যানেলে যান।")
            user_states[chat_id] = {}

    # --- ওয়েব সিরিজ ফাইল রিসিভ ---
    elif p_type == 'series' and state in ['waiting_for_season', 'waiting_for_episodes', 'waiting_for_ep_name']:
        if state == 'waiting_for_season' and message.text:
            user_states[chat_id]['season'] = message.text.strip()
            user_states[chat_id]['episodes'] = []
            user_states[chat_id]['step'] = 'waiting_for_episodes'
            
            markup = InlineKeyboardMarkup([[InlineKeyboardButton("✅ সম্পন্ন করুন ও পাবলিশ করুন", callback_data="publish_series")]])
            await client.send_message(chat_id, f"🎬 **সিজন {message.text.strip()} সেট করা হয়েছে!**\nএখন প্রথম এপিসোড ফাইলটি ফরোয়ার্ড করুন:", reply_markup=markup)
            
        elif state == 'waiting_for_episodes':
            if message.document or message.video:
                user_states[chat_id]['temp_file_id'] = message.document.file_id if message.document else message.video.file_id
                user_states[chat_id]['temp_file_type'] = 'document' if message.document else 'video'
                user_states[chat_id]['temp_message_id'] = message.id
                user_states[chat_id]['step'] = 'waiting_for_ep_name'
                await client.send_message(chat_id, "📝 এই এপিসোডের নামটি কী হবে? টাইপ করে জানান (উদা: Episode 1, Batch Zip):")
            else:
                await client.send_message(chat_id, "⚠️ অনুগ্রহ করে ওয়েব সিরিজের ডাউনলোড ফাইলটি পাঠান।")

        elif state == 'waiting_for_ep_name' and message.text:
            ep_title = message.text.strip()
            file_id = user_states[chat_id]['temp_file_id']
            file_type = user_states[chat_id]['temp_file_type']
            orig_msg_id = user_states[chat_id]['temp_message_id']
            
            cap = f"📺 <b>{user_states[chat_id]['movie_data']['title']}</b>\n💿 {ep_title}"
            db_msg_id = await save_file_to_db_channel(chat_id, orig_msg_id, file_type, file_id, cap)
            
            if db_msg_id:
                user_states[chat_id]['episodes'].append({"name": ep_title, "key": f"msg_{db_msg_id}"})
                user_states[chat_id]['step'] = 'waiting_for_episodes'
                
                markup = InlineKeyboardMarkup([[InlineKeyboardButton("✅ সম্পূর্ণ করে পাবলিশ করুন", callback_data="publish_series")]])
                await client.send_message(chat_id, f"✅ **'{ep_title}' যুক্ত হয়েছে!**\nপরের এপিসোডটি পাঠান অথবা কাজ শেষ করতে নিচের বাটনে ক্লিক করুন:", reply_markup=markup)

@app.on_callback_query(filters.regex("publish_series"))
async def publish_series_callback(client, callback_query):
    chat_id = callback_query.message.chat.id
    if chat_id not in user_states or 'episodes' not in user_states[chat_id]:
        return
        
    m_id = "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(12))
    series_post_data = {
        "type": "series",
        "movie_data": user_states[chat_id]['movie_data'],
        "season": user_states[chat_id]['season'],
        "episodes": user_states[chat_id]['episodes'],
        "status": "published"
    }
    save_movie_to_db(m_id, series_post_data)
    await callback_query.edit_message_text(f"🎉 **সিরিজটি সফলভাবে পাবলিশ হয়েছে!**\n\nএটি ব্লগার সাইটে লাইভ হয়ে গেছে।")
    user_states[chat_id] = {}

# মেসেজ ডিলিট ডিলে এসিঙ্ক ফাংশন
async def delete_messages_after_delay(chat_id, message_ids, delay):
    await asyncio.sleep(delay)
    for msg_id in message_ids:
        try:
            await app.delete_messages(chat_id, msg_id)
        except Exception:
            pass

# ল্যাঙ্গুয়েজ সিলেক্টর UI
async def send_language_picker(client, chat_id, text="🗣 অনুগ্রহ করে মুভি/সিরিজের ভাষা সিলেক্ট করুন:"):
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_English"), InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_Hindi")],
        [InlineKeyboardButton("🇧🇩 Bangla", callback_data="lang_Bangla"), InlineKeyboardButton("🎙 Dual Audio (Hin-Eng)", callback_data="lang_Dual Audio (Hindi-English)")],
        [InlineKeyboardButton("🎙 Multi Audio", callback_data="lang_Multi Audio"), InlineKeyboardButton("✏️ কাস্টম টাইপ করুন", callback_data="lang_custom")]
    ])
    await client.send_message(chat_id, text, reply_markup=markup)


# ==================== এডমিন প্যানেল HTML টেমপ্লেটস ====================

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Admin Login - BD Movie Zone</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0b0f19; color: #fff; height: 100vh; display: flex; align-items: center; justify-content: center; }
        .card { background: #151f32; border: 1px solid rgba(255,255,255,0.1); width: 380px; }
    </style>
</head>
<body>
    <div class="card p-4 shadow">
        <h4 class="text-center text-info mb-4">BD Movie Zone Control</h4>
        {% if error %}<div class="alert alert-danger">{{error}}</div>{% endif %}
        <form method="POST">
            <div class="mb-3">
                <label class="form-label">অ্যাডমিন পাসওয়ার্ড:</label>
                <input type="password" name="password" class="form-control" required>
            </div>
            <button type="submit" class="btn btn-info w-100 text-white">লগইন</button>
        </form>
    </div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Control Panel - BD Movie Zone</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0b0f19; color: #fff; padding-top: 30px; }
        .table { background: #151f32; color: #fff; border-radius: 8px; overflow: hidden; }
        .btn-edit { background: #0dcaf0; color: #000; }
    </style>
</head>
<body>
    <div class="container">
        <div class="d-flex justify-content-between align-items-center mb-4">
            <h2 class="text-info">🎬 BD Movie Zone - Control Panel</h2>
            <a href="/admin/logout" class="btn btn-danger">লগআউট</a>
        </div>
        
        <div class="mb-3">
            <input type="text" id="searchBox" class="form-control" placeholder="সার্চ মুভি বা সিরিজ...">
        </div>

        <table class="table table-bordered align-middle">
            <thead>
                <tr>
                    <th>পোস্টার</th>
                    <th>টাইটেল</th>
                    <th>টাইপ</th>
                    <th>ক্যাটাগরি</th>
                    <th>অ্যাকশন</th>
                </tr>
            </thead>
            <tbody id="movieTable">
                {% for m in movies %}
                <tr>
                    <td><img src="{{m.movie_data.poster}}" style="width: 50px; border-radius: 4px;"></td>
                    <td><strong>{{m.movie_data.title}}</strong></td>
                    <td><span class="badge bg-secondary">{{m.type|upper}}</span></td>
                    <td>{{m.movie_data.genres}}</td>
                    <td>
                        <a href="/admin/edit/{{m._id}}" class="btn btn-sm btn-edit">Edit/Sync</a>
                        <a href="/admin/delete/{{m._id}}" onclick="return confirm('মুছে ফেলতে চান?')" class="btn btn-sm btn-danger">Delete</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>

    <script>
        document.getElementById('searchBox').addEventListener('keyup', function() {
            let val = this.value.toLowerCase();
            let rows = document.querySelectorAll('#movieTable tr');
            rows.forEach(row => {
                let text = row.innerText.toLowerCase();
                row.style.display = text.includes(val) ? '' : 'none';
            });
        });
    </script>
</body>
</html>
"""

EDIT_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Edit Movie - BD Movie Zone</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background-color: #0b0f19; color: #fff; padding: 40px 0; }
        .form-card { background: #151f32; border-radius: 12px; padding: 30px; border: 1px solid rgba(255,255,255,0.05); }
    </style>
</head>
<body>
    <div class="container" style="max-width: 800px;">
        <h3 class="text-info mb-4">🛠️ এডিট ও TMDB ইনস্ট্যান্ট সিঙ্ক্রোনাইজার</h3>
        
        <!-- TMDB কুইক সিঙ্ক টুল -->
        <div class="form-card mb-4" style="background-color: #1a263d;">
            <h5 class="text-warning">⚡ TMDB অটোমেটিক সিঙ্ক টুল</h5>
            <p class="text-muted small">ভুল পোস্টার বা বিবরণ সংশোধন করতে এখানে সঠিক TMDB ID বা লিঙ্ক বসিয়ে "Sync & Autofill" চাপুন:</p>
            <div class="input-group">
                <input type="text" id="tmdbInput" class="form-control" placeholder="উদা: 550 বা https://www.themoviedb.org/movie/550">
                <button type="button" id="syncBtn" class="btn btn-warning">Sync & Autofill</button>
            </div>
            <div id="syncStatus" class="mt-2 small text-info"></div>
        </div>

        <form method="POST" class="form-card">
            <div class="mb-3">
                <label class="form-label">মুভি টাইটেল:</label>
                <input type="text" name="title" id="formTitle" class="form-control" value="{{movie.movie_data.title}}" required>
            </div>
            <div class="row">
                <div class="col-md-6 mb-3">
                    <label class="form-label">পোস্টার ইমেজ লিঙ্ক (Portrait Poster):</label>
                    <input type="text" name="poster" id="formPoster" class="form-control" value="{{movie.movie_data.poster}}">
                </div>
                <div class="col-md-6 mb-3">
                    <label class="form-label">ব্যানার ইমেজ লিঙ্ক (Landscape Backdrop):</label>
                    <input type="text" name="backdrop" id="formBackdrop" class="form-control" value="{{movie.movie_data.backdrop}}">
                </div>
            </div>
            <div class="row">
                <div class="col-md-4 mb-3">
                    <label class="form-label">IMDb রেটিং:</label>
                    <input type="text" name="rating" id="formRating" class="form-control" value="{{movie.movie_data.rating}}">
                </div>
                <div class="col-md-4 mb-3">
                    <label class="form-label">ভাষা (Language):</label>
                    <input type="text" name="lang" id="formLang" class="form-control" value="{{movie.movie_data.lang}}">
                </div>
                <div class="col-md-4 mb-3">
                    <label class="form-label">জনরা (Genres):</label>
                    <input type="text" name="genres" id="formGenres" class="form-control" value="{{movie.movie_data.genres}}">
                </div>
            </div>
            {% if movie.type == 'series' %}
            <div class="mb-3">
                <label class="form-label">সিজন (Season):</label>
                <input type="text" name="season" class="form-control" value="{{movie.season}}">
            </div>
            {% endif %}
            <div class="mb-3">
                <label class="form-label">কাহিনী সংক্ষেপ (Storyline):</label>
                <textarea name="plot" id="formPlot" class="form-control" rows="4">{{movie.movie_data.plot}}</textarea>
            </div>
            <div class="mb-4">
                <label class="form-label">স্ক্রিনশটস (প্রতি লাইনে একটি লিঙ্ক):</label>
                <textarea name="screenshots" id="formScreens" class="form-control" rows="4">{% for s in movie.movie_data.screenshots %}{{s}}&#10;{% endfor %}</textarea>
            </div>

            <div class="d-flex justify-content-between">
                <button type="submit" class="btn btn-success px-4">সংরক্ষণ করুন</button>
                <a href="/admin" class="btn btn-secondary">বাতিল করুন</a>
            </div>
        </form>
    </div>

    <script>
        document.getElementById('syncBtn').addEventListener('click', function() {
            let val = document.getElementById('tmdbInput').value.trim();
            if(!val) { alert("অনুগ্রহ করে একটি TMDB লিঙ্ক বা আইডি দিন!"); return; }
            
            let statusDiv = document.getElementById('syncStatus');
            statusDiv.innerHTML = "⏳ তথ্য সংগ্রহ করা হচ্ছে...";
            
            fetch('/api/tmdb-fetch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tmdb_input: val,
                    is_tv: {% if movie.type == 'series' %}true{% else %}false{% endif %}
                })
            })
            .then(res => res.json())
            .then(data => {
                if(data.error) {
                    statusDiv.innerHTML = "❌ ত্রুটি: " + data.error;
                } else {
                    document.getElementById('formTitle').value = data.title;
                    document.getElementById('formPoster').value = data.poster;
                    document.getElementById('formBackdrop').value = data.backdrop;
                    document.getElementById('formRating').value = data.rating;
                    document.getElementById('formGenres').value = data.genres;
                    document.getElementById('formPlot').value = data.plot;
                    
                    if(data.screenshots) {
                        document.getElementById('formScreens').value = data.screenshots.join('\\n');
                    }
                    statusDiv.innerHTML = "✅ সঠিক তথ্য সাফল্যের সাথে অটোফিল করা হয়েছে! নিচের 'সংরক্ষণ করুন' বাটনে ক্লিক করুন।";
                }
            })
            .catch(err => {
                statusDiv.innerHTML = "❌ কানেকশন এরর!";
            });
        });
    </script>
</body>
</html>
"""

COPY_CODE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Code Export - BD Movie Zone</title>
</head>
<body style="background: #090e17; color: #eee; font-family: sans-serif; text-align: center; padding-top: 50px;">
    <h2>BD Movie Zone HTML Export</h2>
    <button onclick="copyCode()" style="padding: 10px 20px; background: #00bcd4; border: none; border-radius: 4px; color: #fff; font-size: 16px; cursor: pointer;">Copy Code</button>
    <pre style="text-align: left; background: #111; padding: 20px; max-width: 800px; margin: 20px auto; overflow: auto; height: 350px;"><code id="cd">{{escaped_html}}</code></pre>
    <script>
        function copyCode() {
            navigator.clipboard.writeText(document.getElementById('cd').innerText);
            alert("Copied!");
        }
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    web_thread = threading.Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()
    
    async def main():
        global http_session
        print("Starting Pyrogram Bot Client...")
        await app.start()
        http_session = aiohttp.ClientSession()
        print("System Online & Connected!")
        await idle()
        if http_session:
            await http_session.close()
        await app.stop()

    asyncio.get_event_loop().run_until_complete(main())
