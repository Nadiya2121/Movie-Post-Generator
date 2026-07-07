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
AUTO_DELETE_DELAY = 300 
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', 'admin123')

# Koyeb সাব-পাথ ফ্রেমওয়ার্ক ডিফাইন
MAIN_WEBSITE_URL = "https://gorgeous-donetta-nahidcrk-7b84dba9.koyeb.app/view/Movie-Post-Generator/"
PREFIX = "/view/Movie-Post-Generator"

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
    movies = load_movies_db()
    existing_movie = None
    
    # টাইটেল চেক করে আগের পোস্ট আছে কি না চেক করুন
    for m in movies:
        if m['movie_data']['title'] == data['movie_data']['title']:
            existing_movie = m
            break
            
    if existing_movie:
        if data['type'] == 'movie':
            for quality, link in data['dl_links'].items():
                if link:
                    existing_movie['dl_links'][quality] = link
        else:
            existing_ep_names = [ep['name'] for ep in existing_movie['episodes']]
            for ep in data['episodes']:
                if ep['name'] not in existing_ep_names:
                    existing_movie['episodes'].append(ep)
                    
        if db_mongo is not None:
            try:
                db_mongo['movies'].update_one({'_id': existing_movie['_id']}, {'$set': existing_movie})
                return
            except Exception:
                pass
        
        movies = [m for m in movies if m.get('_id') != existing_movie['_id']]
        movies.append(existing_movie)
    else:
        data['_id'] = movie_id
        if db_mongo is not None:
            try:
                db_mongo['movies'].update_one({'_id': movie_id}, {'$set': data}, upsert=True)
                return
            except Exception:
                pass
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

# CORS হেডার যুক্ত করা
@web_app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    response.headers['Access-Control-Allow-Methods'] = 'GET,POST,PUT,DELETE,OPTIONS'
    return response

# ==================== এপিআই এন্ডপয়েন্ট ====================

@web_app.route('/api/movies', methods=['GET'])
@web_app.route(f'{PREFIX}/api/movies', methods=['GET'])
def get_all_movies_api():
    movies = load_movies_db()
    return jsonify(movies)

@web_app.route('/api/settings', methods=['GET'])
@web_app.route(f'{PREFIX}/api/settings', methods=['GET'])
def get_settings_api():
    settings = load_settings()
    return jsonify(settings)

def load_settings():
    default_settings = {
        'direct_links': ["https://omg10.com/4/11047054"],
        'revenue_share': 20
    }
    if db_mongo is not None:
        try:
            config = db_mongo['settings'].find_one({'_id': 'system_config'})
            if config: return config
        except Exception: pass
    if os.path.exists("settings.json"):
        try:
            with open("settings.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception: pass
    return default_settings

def save_settings(settings):
    if db_mongo is not None:
        try:
            db_mongo['settings'].update_one({'_id': 'system_config'}, {'$set': settings}, upsert=True)
            return
        except Exception: pass
    with open("settings.json", "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)

system_settings = load_settings()

@web_app.route('/api/tmdb-fetch', methods=['POST'])
@web_app.route(f'{PREFIX}/api/tmdb-fetch', methods=['POST'])
def tmdb_fetch_api():
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json or {}
    tmdb_input = data.get('tmdb_input', '').strip()
    is_tv = data.get('is_tv', False)
    tmdb_id = tmdb_input
    if "themoviedb.org" in tmdb_input:
        match = re.search(r"/(movie|tv)/(\d+)", tmdb_input)
        if match:
            tmdb_id = match.group(2)
            is_tv = (match.group(1) == "tv")
            
    endpoint = "tv" if is_tv else "movie"
    url = f"https://api.themoviedb.org/3/{endpoint}/{tmdb_id}?api_key={TMDB_API_KEY}&append_to_response=images"
    
    async def fetch():
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=10) as r:
                if r.status != 200: return None
                return await r.json()
                
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    res_data = loop.run_until_complete(fetch())
    if not res_data: return jsonify({"error": "Failed to fetch data"}), 400
        
    title = res_data.get('title') if not is_tv else res_data.get('name')
    release = res_data.get('release_date') if not is_tv else res_data.get('first_air_date')
    year = release.split('-')[0] if release else 'N/A'
    rating = f"{res_data.get('vote_average'):.1f}/10" if res_data.get('vote_average') else 'N/A'
    genres = ", ".join([g['name'] for g in res_data.get('genres', [])])
    poster = f"https://image.tmdb.org/t/p/w500{res_data.get('poster_path')}" if res_data.get('poster_path') else 'https://via.placeholder.com/300x450'
    backdrop = f"https://image.tmdb.org/t/p/original{res_data.get('backdrop_path')}" if res_data.get('backdrop_path') else 'https://via.placeholder.com/1280x720'
    plot = res_data.get('overview', 'No description available.')
    backdrops = res_data.get('images', {}).get('backdrops', [])
    screenshots = [f"https://image.tmdb.org/t/p/w780{bg.get('file_path')}" for bg in backdrops[:4] if bg.get('file_path')]

    return jsonify({
        "title": f"{title} ({year})", "poster": poster, "backdrop": backdrop,
        "rating": rating, "genres": genres, "plot": plot, "screenshots": screenshots
    })


# ==================== ওয়েব অ্যাডমিন প্যানেল ভিউজ (ডাইনামিক সাব-পাথ সমর্থিত) ====================

@web_app.route('/')
@web_app.route(f'{PREFIX}/')
def home():
    return "BD Movie Zone API & Bot Server is active!"

@web_app.route('/admin/login', methods=['GET', 'POST'])
@web_app.route(f'{PREFIX}/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(f"{PREFIX}/admin")
        else:
            return render_template_string(LOGIN_HTML, error="ভুল পাসওয়ার্ড! আবার ট্রাই করুন。", prefix=PREFIX)
    return render_template_string(LOGIN_HTML, prefix=PREFIX)

@web_app.route('/admin')
@web_app.route(f'{PREFIX}/admin')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect(f"{PREFIX}/admin/login")
    movies = load_movies_db()
    settings = load_settings()
    return render_template_string(DASHBOARD_HTML, movies=movies, settings=settings, prefix=PREFIX)

@web_app.route('/admin/save-settings', methods=['POST'])
@web_app.route(f'{PREFIX}/admin/save-settings', methods=['POST'])
def admin_save_settings():
    if not session.get('admin_logged_in'):
        return redirect(f"{PREFIX}/admin/login")
    links_raw = request.form.get('direct_links', '')
    links_list = [l.strip() for l in links_raw.split('\n') if l.strip().startswith('http')]
    settings = {
        'direct_links': links_list,
        'revenue_share': int(request.form.get('revenue_share', 20))
    }
    save_settings(settings)
    global system_settings
    system_settings = settings
    return redirect(f"{PREFIX}/admin")

@web_app.route('/admin/edit/<movie_id>', methods=['GET', 'POST'])
@web_app.route(f'{PREFIX}/admin/edit/<movie_id>', methods=['GET', 'POST'])
def edit_movie(movie_id):
    if not session.get('admin_logged_in'):
        return redirect(f"{PREFIX}/admin/login")
        
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
        return redirect(f"{PREFIX}/admin")
        
    return render_template_string(EDIT_HTML, movie=movie, prefix=PREFIX)

@web_app.route('/admin/delete/<movie_id>')
@web_app.route(f'{PREFIX}/admin/delete/<movie_id>')
def delete_movie(movie_id):
    if not session.get('admin_logged_in'):
        return redirect(f"{PREFIX}/admin/login")
    delete_movie_from_db(movie_id)
    return redirect(f"{PREFIX}/admin")

@web_app.route('/admin/logout')
@web_app.route(f'{PREFIX}/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(f"{PREFIX}/admin/login")

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)


# ==================== পাইগ্রাম টেলিগ্রাম বট ও অটো-পার্স লজিক ====================

app = Client("movie_post_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# ফাইল ক্যাপশন বা নাম পরিষ্কার করার ফাংশন
def clean_movie_filename(filename):
    name = os.path.splitext(filename)[0]
    name = re.sub(r'[\._\-]', ' ', name)
    name = re.sub(r'\[.*?\]', ' ', name)
    name = re.sub(r'\(.*?\)', ' ', name)
    
    junk_patterns = [
        r'\b(480p|720p|1080p|2160p|4k|hd|sd|web[- ]?dl|bluray|brrip|dvdrip|hdtv|hdtc|hc)\b',
        r'\b(x264|x265|h264|h265|hevc|10bit|aac|dd5\.1|ac3|mp3|dual[- ]audio|multi[- ]audio|hindi|bangla|english|bengali|esub|sub)\b',
        r'\b(yts|yify|psa|pahe|galaxyrg|megusta|tigole|silas|qxr|vxt|rarbg|extratorrent)\b',
        r'\b(nf|netflix|dsnp|amzn|amazon|hmax|hbomax|apple[- ]?tv)\b'
    ]
    for pattern in junk_patterns:
        name = re.sub(pattern, ' ', name, flags=re.IGNORECASE)
        
    name = re.sub(r'\s+', ' ', name).strip()
    
    year_match = re.search(r'\b(19|20)\d{2}\b', name)
    if year_match:
        year_idx = name.find(year_match.group(0))
        name_before_year = name[:year_idx].strip()
        if len(name_before_year) > 2:
            return name_before_year + " " + year_match.group(0)
    return name

# অটোমেটিক কোয়ালিটি ডিটেকশন
def detect_file_quality(filename):
    fn_lower = filename.lower()
    if "1080" in fn_lower: return "1080p"
    elif "720" in fn_lower: return "720p"
    elif "480" in fn_lower: return "480p"
    return "720p"

@app.on_message(filters.command("start") & filters.private)
async def handle_start(client, message):
    chat_id = message.chat.id
    text = message.text.strip() if message.text else ""
    
    if len(text.split()) > 1:
        param = text.split()[1]
        if param.startswith("msg_"):
            db_msg_id = int(param.split("_")[1])
            try:
                user_msg_id = await client.copy_message(chat_id, DATABASE_CHANNEL_ID, db_msg_id)
                warning_text = f"⚠️ কপিরাইটের কারণে ফাইলটি আগামী **{int(AUTO_DELETE_DELAY/60)} মিনিটের** মধ্যে ডিলিট হয়ে যাবে। এখনই ফাইলটি আপনার **Saved Messages**-এ ফরোয়ার্ড করে রাখুন।"
                sent_warning = await client.send_message(chat_id, warning_text)
                asyncio.create_task(delete_messages_after_delay(chat_id, [user_msg_id.id, sent_warning.id], AUTO_DELETE_DELAY))
            except Exception as e:
                await client.send_message(chat_id, f"❌ ফাইলটি লোড করা যাচ্ছে না বা ডিলেট হয়ে গেছে।")
        return

    admin_btn = []
    if chat_id == OWNER_ID:
        admin_btn = [
            [InlineKeyboardButton("⚙️ অ্যাডমিন কন্ট্রোল প্যানেল (Login)", url=MAIN_WEBSITE_URL + "admin")],
            [InlineKeyboardButton("🌐 আমার লাইভ মুভি সাইট", url=MAIN_WEBSITE_URL)]
        ]
    else:
        admin_btn = [
            [InlineKeyboardButton("🌐 ভিজিট করুন মুভি সাইট", url=MAIN_WEBSITE_URL)]
        ]

    await client.send_message(
        chat_id, 
        f"👋 **BD Movie Zone আল্ট্রা-ফাস্ট ইন্টেলিজেন্ট সিস্টেম!**\n\n"
        "👉 **অটো-পোস্টিং নিয়ম:** যেকোনো মুভি/সিরিজের ডাউনলোড ফাইল সরাসরি এই চ্যাটে ফরোয়ার্ড করে দিন। "
        "বট স্বয়ংক্রিয়ভাবে ফাইলের নাম থেকে মুভি সনাক্ত করবে, TMDB থেকে কভার ও স্ক্রিনশট কালেক্ট করবে এবং "
        "সাথে সাথে সরাসরি মুভি সাইটে ডাইনামিকভাবে পোস্ট পাবলিশ করে দেবে।",
        reply_markup=InlineKeyboardMarkup(admin_btn)
    )

# --- মূল এসিঙ্ক্রোনাস অটোমেটিক ফাইল পোস্টিং হ্যান্ডলার ---
@app.on_message((filters.document | filters.video) & filters.private)
async def auto_file_poster_handler(client, message):
    chat_id = message.chat.id
    
    if chat_id != OWNER_ID:
        await message.reply_text("❌ দুঃখিত! শুধুমাত্র বটের মালিক এই ফিচারের সাহায্যে ফাইল ডাইরেক্ট পাবলিশ করতে পারবেন।")
        return

    filename = message.document.file_name if message.document else message.video.file_name
    if not filename:
        filename = message.caption if message.caption else "Unknown Movie"
        
    status_msg = await message.reply_text("⏳ **ফাইল ডিটেক্ট করা হয়েছে! নাম পরিষ্কার করা হচ্ছে...**")
    cleaned_title = clean_movie_filename(filename)
    detected_quality = detect_file_quality(filename)
    
    await status_msg.edit_text(f"🔍 **মুভির নাম:** `{cleaned_title}`\n💿 **কোয়ালিটি:** `{detected_quality}`\n\n⏳ TMDB ডাটাবেজে সার্চ করা হচ্ছে...")
    
    url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={urllib.parse.quote(cleaned_title)}"
    movie_meta = None
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                res_json = await resp.json()
                results = res_json.get('results', [])
                if results:
                    top_result = results[0]
                    m_id = top_result['id']
                    detail_url = f"https://api.themoviedb.org/3/movie/{m_id}?api_key={TMDB_API_KEY}&append_to_response=images"
                    async with session.get(detail_url) as d_resp:
                        if d_resp.status == 200:
                            details = await d_resp.json()
                            release_year = details.get('release_date', 'N/A').split('-')[0]
                            title_with_year = f"{details.get('title')} ({release_year})"
                            rating = f"{details.get('vote_average'):.1f}/10" if details.get('vote_average') else 'N/A'
                            genres = ", ".join([g['name'] for g in details.get('genres', [])])
                            poster = f"https://image.tmdb.org/t/p/w500{details.get('poster_path')}" if details.get('poster_path') else 'https://via.placeholder.com/300x450'
                            backdrop = f"https://image.tmdb.org/t/p/original{details.get('backdrop_path')}" if details.get('backdrop_path') else 'https://via.placeholder.com/1280x720'
                            plot = details.get('overview', 'No description available.')
                            backdrops = details.get('images', {}).get('backdrops', [])
                            screenshots = [f"https://image.tmdb.org/t/p/w780{bg.get('file_path')}" for bg in backdrops[:4] if bg.get('file_path')]
                            
                            movie_meta = {
                                'title': title_with_year, 'poster': poster, 'backdrop': backdrop,
                                'rating': rating, 'genres': genres, 'plot': plot, 'screenshots': screenshots,
                                'lang': 'N/A'
                            }

    if not movie_meta:
        movie_meta = {
            'title': cleaned_title,
            'poster': 'https://via.placeholder.com/300x450?text=No+Poster+Found',
            'backdrop': 'https://via.placeholder.com/1280x720?text=No+Backdrop',
            'rating': 'N/A', 'genres': 'Movie', 'plot': 'No synopsis fetched. You can update this using the Admin Sync tool.',
            'screenshots': [], 'lang': 'N/A'
        }

    await status_msg.edit_text("⏳ **ফাইলটি ব্যাকআপ ক্লাউড ডাটাবেজে সংরক্ষণ করা হচ্ছে...**")

    file_type = 'document' if message.document else 'video'
    file_id = message.document.file_id if message.document else message.video.file_id
    caption = f"🎬 <b>{movie_meta['title']}</b>\n💿 Quality: <b>{detected_quality}</b>"
    
    db_msg_id = await save_file_to_db_channel(chat_id, message.id, file_type, file_id, caption)
    if not db_msg_id:
        await status_msg.edit_text("❌ ফাইল ডাটাবেজ চ্যানেলে সংরক্ষণ ব্যর্থ হয়েছে!")
        return
        
    file_key = f"msg_{db_msg_id}"
    m_id_unique = "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(12))
    
    movie_data = {
        "type": "movie",
        "movie_data": movie_meta,
        "dl_links": {
            "480p": file_key if detected_quality == "480p" else "",
            "720p": file_key if detected_quality == "720p" else "",
            "1080p": file_key if detected_quality == "1080p" else ""
        },
        "status": "published"
    }
    
    save_movie_to_db(m_id_unique, movie_data)

    success_text = (
        f"🎉 **পোস্টটি সফলভাবে তৈরি ও লাইভ পাবলিশ করা হয়েছে!**\n\n"
        f"🎬 **নাম:** `{movie_meta['title']}`\n"
        f"💿 **কোয়ালিটি লিংক যুক্ত হয়েছে:** `{detected_quality}`\n"
        f"🗣 **ল্যাঙ্গুয়েজ ট্যাগ:** `N/A` (এখনই প্যানেল থেকে ট্যাগ বসান)\n\n"
        f"💡 একই মুভির ভিন্ন কোয়ালিটি লিংক এড করতে চাইলে শুধু ফাইলটি ফরোয়ার্ড করলেই হবে, ডাটা অটোমেটিক মার্জ হয়ে যাবে।"
    )
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛠️ ল্যাঙ্গুয়েজ ট্যাগ বসান (অ্যাডমিন প্যানেল)", url=MAIN_WEBSITE_URL + "admin")],
        [InlineKeyboardButton("🌐 সাইটে পোস্টটি দেখুন", url=MAIN_WEBSITE_URL)]
    ])
    
    await status_msg.delete()
    await message.reply_text(success_text, reply_markup=markup)

async def delete_messages_after_delay(chat_id, message_ids, delay):
    await asyncio.sleep(delay)
    for msg_id in message_ids:
        try: await app.delete_messages(chat_id, msg_id)
        except Exception: pass


# ==================== এডমিন প্যানেল HTML টেমপ্লেটস (১০০% রেসপন্সিভ মোবাইল ফ্রেন্ডলি থিম) ====================

LOGIN_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login - BD Movie Zone</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;800&display=swap" rel="stylesheet">
    <style>
        body { 
            background-color: #06070d; 
            color: #fff; 
            height: 100vh; 
            display: flex; 
            align-items: center; 
            justify-content: center;
            font-family: 'Plus Jakarta Sans', sans-serif;
            padding: 20px;
        }
        .card { 
            background: #0f111a; 
            border: 1px solid rgba(255,255,255,0.08); 
            width: 100%;
            max-width: 400px; 
            border-radius: 16px;
            box-shadow: 0 15px 30px rgba(0,0,0,0.5);
        }
        .btn-info {
            background: linear-gradient(135deg, #38bdf8, #0ea5e9);
            border: none;
            font-weight: bold;
        }
    </style>
</head>
<body>
    <div class="card p-4 shadow">
        <h4 class="text-center text-info mb-4" style="font-weight: 800; letter-spacing: 0.5px;">🎬 BD MOVIE ZONE</h4>
        <p class="text-center text-muted small">কন্ট্রোল ড্যাশবোর্ডে লগইন করুন</p>
        {% if error %}<div class="alert alert-danger py-2 text-center" style="font-size: 13px;">{{error}}</div>{% endif %}
        <form method="POST">
            <div class="mb-3">
                <label class="form-label text-muted small">অ্যাডমিন পাসওয়ার্ড:</label>
                <input type="password" name="password" class="form-control bg-dark text-white border-secondary" style="border-radius: 10px; padding: 12px;" required>
            </div>
            <button type="submit" class="btn btn-info w-100 text-dark py-3" style="border-radius: 10px;">লগইন করুন</button>
        </form>
    </div>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Control Panel - BD Movie Zone</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { background-color: #06070d; color: #f1f5f9; font-family: 'Plus Jakarta Sans', sans-serif; padding-bottom: 50px; }
        .dashboard-header { background: #0f111a; border-bottom: 1px solid rgba(255,255,255,0.06); padding: 15px 10px; margin-bottom: 25px; }
        .card { background: #0f111a; border: 1px solid rgba(255,255,255,0.05); border-radius: 16px; color: #fff; }
        
        /* মডার্ন মোবাইল-বান্ধব কার্ড ভিউ */
        .movie-card-row {
            display: flex;
            background: #0f111a;
            border-radius: 14px;
            padding: 12px;
            margin-bottom: 15px;
            border: 1px solid rgba(255,255,255,0.04);
            align-items: center;
            gap: 15px;
        }
        .movie-poster-box {
            width: 70px;
            height: 100px;
            border-radius: 10px;
            overflow: hidden;
            flex-shrink: 0;
            background: #000;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .movie-poster-box img { width: 100%; height: 100%; object-fit: cover; }
        .movie-details-box { flex-grow: 1; min-width: 0; }
        .movie-title-text { font-size: 15px; font-weight: 700; color: #fff; line-height: 1.3; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        
        .tag-badge { background: rgba(56, 189, 248, 0.15); color: #38bdf8; font-size: 11px; padding: 4px 10px; border-radius: 20px; font-weight: bold; display: inline-block; }
        
        /* টাচ-ফ্রেন্ডলি অ্যাকশন বাটনসমূহ */
        .action-btn-group { display: flex; gap: 8px; margin-top: 10px; }
        .action-btn { flex: 1; padding: 10px; border-radius: 8px; font-size: 12px; font-weight: bold; text-align: center; text-decoration: none !important; }
        .btn-edit { background: linear-gradient(135deg, #0284c7, #0ea5e9); color: #fff; }
        .btn-delete { background: rgba(239, 68, 68, 0.1); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.2); }
        
        .form-control, .form-control:focus { background-color: #161824 !important; border-color: rgba(255,255,255,0.1) !important; color: #fff !important; border-radius: 10px; }
    </style>
</head>
<body>

    <div class="dashboard-header shadow-sm">
        <div class="container d-flex justify-content-between align-items-center">
            <h5 class="mb-0 text-info" style="font-weight: 800; letter-spacing: 0.5px;">🎬 BD MOVIE ZONE</h5>
            <div>
                 <a href="{{prefix}}/admin/logout" class="btn btn-sm btn-danger px-3" style="border-radius: 8px; font-weight: bold;">Logout</a>
            </div>
        </div>
    </div>

    <div class="container">
        <!-- বিজ্ঞাপন কন্ট্রোল উইজেট -->
        <div class="card p-3 mb-4 shadow">
            <h6 class="text-warning mb-3" style="font-weight: 800;">🔗 Direct Link Rotation (স্প্যাম প্রোটেকশন)</h6>
            <form action="{{prefix}}/admin/save-settings" method="POST">
                <div class="mb-3">
                    <label class="form-label text-muted small">ডিরেক্ট লিঙ্কসমূহ (প্রতি লাইনে একটি লিংক):</label>
                    <textarea name="direct_links" class="form-control" rows="3" placeholder="https://link.com" required>{% for link in settings.direct_links %}{{link}}&#10;{% endfor %}</textarea>
                </div>
                <div class="mb-3" style="display:none;">
                    <input type="hidden" name="revenue_share" value="{{settings.revenue_share}}">
                </div>
                <button type="submit" class="btn btn-warning w-100 text-dark py-2" style="border-radius:8px; font-weight: 800; font-size:13px;">আপডেট লিংক রোটেশন</button>
            </form>
        </div>

        <!-- সার্চ উইজেট -->
        <div class="mb-4">
            <input type="text" id="searchBox" class="form-control py-3 px-4" placeholder="🔍 সার্চ মুভি বা সিরিজ...">
        </div>

        <!-- লাইভ কার্ড লিস্ট (মোবাইল বান্ধব) -->
        <div id="movieCardList">
            {% for m in movies %}
            <div class="movie-card-row shadow-sm">
                <div class="movie-poster-box">
                    <img src="{{m.movie_data.poster}}" alt="Poster">
                </div>
                <div class="movie-details-box">
                    <div class="movie-title-text">{{m.movie_data.title}}</div>
                    <span class="tag-badge">🗣️ {{m.movie_data.lang}}</span>
                    
                    <div class="action-btn-group">
                         <a href="{{prefix}}/admin/edit/{{m._id}}" class="action-btn btn-edit">Edit / Tag Sync</a>
                         <a href="{{prefix}}/admin/delete/{{m._id}}" onclick="return confirm('মুছে ফেলতে চান?')" class="action-btn btn-delete">Delete</a>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <script>
        document.getElementById('searchBox').addEventListener('keyup', function() {
            let val = this.value.toLowerCase();
            let cards = document.querySelectorAll('.movie-card-row');
            cards.forEach(card => {
                let text = card.innerText.toLowerCase();
                card.style.display = text.includes(val) ? '' : 'none';
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
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Edit Movie - BD Movie Zone</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { background-color: #06070d; color: #fff; font-family: 'Plus Jakarta Sans', sans-serif; padding-top: 20px; padding-bottom: 50px; }
        .form-card { background: #0f111a; border-radius: 16px; padding: 20px; border: 1px solid rgba(255,255,255,0.06); }
        .form-control { background-color: #161824 !important; border-color: rgba(255,255,255,0.08) !important; color: #fff !important; border-radius: 10px; padding: 12px; }
        .form-label { font-size: 13px; color: #94a3b8; font-weight: bold; margin-bottom: 6px; }
        .btn-success { background: linear-gradient(135deg, #059669, #10b981); border: none; font-weight: bold; border-radius: 10px; padding: 14px; }
        .btn-secondary { background-color: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.1); color: #fff; border-radius: 10px; padding: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <h4 class="text-info mb-3" style="font-weight: 800;">🛠️ এডিট ও ল্যাঙ্গুয়েজ আপডেট</h4>
        
        <!-- TMDB কুইক সিঙ্ক টুল -->
        <div class="form-card mb-4" style="background-color: #121624;">
            <h6 class="text-warning mb-2" style="font-weight: 800;">⚡ TMDB কুইক সিঙ্ক (হট-ফিক্সার)</h6>
            <div class="input-group">
                <input type="text" id="tmdbInput" class="form-control" placeholder="সঠিক TMDB ID বা লিঙ্ক বসান">
                <button type="button" id="syncBtn" class="btn btn-warning text-dark font-weight-bold">Sync & AutoFill</button>
            </div>
            <div id="syncStatus" class="mt-2 small text-info"></div>
        </div>

        <form action="{{prefix}}/admin/edit/{{movie._id}}" method="POST" class="form-card">
            <div class="mb-3">
                <label class="form-label">মুভি টাইটেল:</label>
                <input type="text" name="title" id="formTitle" class="form-control" value="{{movie.movie_data.title}}" required>
            </div>
            
            <div class="mb-3">
                <label class="form-label text-warning font-weight-bold">🗣️ ল্যাঙ্গুয়েজ ট্যাগ (যা ডিসপ্লে বা কার্ডে দেখাবে):</label>
                <input type="text" name="lang" id="formLang" class="form-control bg-warning text-dark font-weight-bold" style="background-color: #fef08a !important; color: #000 !important;" value="{{movie.movie_data.lang}}" placeholder="উদা: Bangla / Dual Audio">
            </div>

            <div class="mb-3">
                <label class="form-label">পোস্টার ইমেজ লিঙ্ক:</label>
                <input type="text" name="poster" id="formPoster" class="form-control" value="{{movie.movie_data.poster}}">
            </div>
            <div class="mb-3">
                <label class="form-label">ب্যবহারকারী ব্যানার লিঙ্ক (Landscape Backdrop):</label>
                <input type="text" name="backdrop" id="formBackdrop" class="form-control" value="{{movie.movie_data.backdrop}}">
            </div>

            <div class="row">
                <div class="col-6 mb-3">
                    <label class="form-label">IMDb রেটিং:</label>
                    <input type="text" name="rating" id="formRating" class="form-control" value="{{movie.movie_data.rating}}">
                </div>
                <div class="col-6 mb-3">
                    <label class="form-label">জনরা (Genres):</label>
                    <input type="text" name="genres" id="formGenres" class="form-control" value="{{movie.movie_data.genres}}">
                </div>
            </div>

            <div class="mb-3">
                <label class="form-label">কাহিনী সংক্ষেপ (Plot):</label>
                <textarea name="plot" id="formPlot" class="form-control" rows="4">{{movie.movie_data.plot}}</textarea>
            </div>
            <div class="mb-4">
                <label class="form-label">স্ক্রিনশটস (প্রতি লাইনে একটি লিঙ্ক):</label>
                <textarea name="screenshots" id="formScreens" class="form-control" rows="3">{% for s in movie.movie_data.screenshots %}{{s}}&#10;{% endfor %}</textarea>
            </div>

            <div class="d-flex flex-column gap-2">
                <button type="submit" class="btn btn-success w-100">সংরক্ষণ করুন (Save & Update)</button>
                <a href="{{prefix}}/admin" class="btn btn-secondary w-100 text-center">বাতিল করুন</a>
            </div>
        </form>
    </div>

    <script>
        document.getElementById('syncBtn').addEventListener('click', function() {
            let val = document.getElementById('tmdbInput').value.trim();
            if(!val) { alert("TMDB লিঙ্ক বা আইডি দিন!"); return; }
            let statusDiv = document.getElementById('syncStatus');
            statusDiv.innerHTML = "⏳ তথ্য সংগ্রহ করা হচ্ছে...";
            
            fetch('{{prefix}}/api/tmdb-fetch', {
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
                    if(data.screenshots) document.getElementById('formScreens').value = data.screenshots.join('\\n');
                    statusDiv.innerHTML = "✅ সঠিক তথ্য অটোফিল হয়েছে! ল্যাঙ্গুয়েজ ট্যাগ চেক করে নিচের 'সংরক্ষণ করুন' বাটন চাপুন।";
                }
            })
            .catch(err => { statusDiv.innerHTML = "❌ কানেকশন এরর!"; });
        });
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
