import os
import threading
import random
import json
import io
import asyncio
import re
import html
import time
import urllib.parse
import urllib.request
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

# Koyeb সাব-পাথ ফ্রেমওয়ার্ক
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

# গ্লোবাল সেটিংস অবজেক্ট (ক্যাশিং এর জন্য)
system_settings = None

# --- অ্যাডমিন ও ডিরেক্ট লিংক সেটিংস লোডার ---
def load_settings(force_reload=False):
    global system_settings
    if system_settings is not None and not force_reload:
        return system_settings

    default_settings = {
        'direct_links': [],  
        'revenue_share': 20,
        'download_timer': 5,
        'blogger_url': MAIN_WEBSITE_URL,
        'notification_channel_id': "",
        'admin_ids': [],
        'update_channel_url': "https://t.me/BDMovieZone",
        'group_channel_url': "https://t.me/BDMovieZoneGroup",
        'custom_caption_template': (
            "🎬 <b>{title}</b>\n\n"
            "🗣️ Language: <b>{lang}</b>\n"
            "🎭 Genres: <b>{genres}</b>\n"
            "💿 Quality: <b>{quality}</b>\n\n"
            "⚠️ <i>কপিরাইটের কারণে ফাইলটি আগামী ৫ মিনিটের মধ্যে ডিলিট হয়ে যাবে। "
            "এখনই ফাইলটি আপনার Saved Messages-এ ফরোয়ার্ড করে রাখুন।</i>"
        )
    }
    
    config = None
    if db_mongo is not None:
        try:
            config = db_mongo['settings'].find_one({'_id': 'system_config'})
        except Exception: pass
        
    if not config and os.path.exists("settings.json"):
        try:
            with open("settings.json", "r", encoding="utf-8") as f:
                config = json.load(f)
        except Exception: pass

    if config:
        for key, val in default_settings.items():
            if key not in config:
                config[key] = val
        system_settings = config
        return config

    system_settings = default_settings
    return default_settings

def save_settings(settings):
    global system_settings
    system_settings = settings
    if db_mongo is not None:
        try:
            db_mongo['settings'].update_one({'_id': 'system_config'}, {'$set': settings}, upsert=True)
            return
        except Exception: pass
    try:
        with open("settings.json", "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=4, ensure_ascii=False)
    except Exception: pass

# Initial load
system_settings = load_settings()

# --- ডেটা রিড ও ডাইনামিক অটো-মার্জিং মেকানিজম ---
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
    current_time = time.time()
    data['updated_at'] = current_time

    existing_by_id_index = -1
    for i, m in enumerate(movies):
        if m.get('_id') == movie_id:
            existing_by_id_index = i
            break

    if existing_by_id_index != -1:
        movies[existing_by_id_index] = data
        if db_mongo is not None:
            try:
                db_mongo['movies'].update_one({'_id': movie_id}, {'$set': data}, upsert=True)
            except Exception:
                pass
    else:
        existing_by_title_index = -1
        for i, m in enumerate(movies):
            if m['movie_data']['title'].lower().strip() == data['movie_data']['title'].lower().strip():
                existing_by_title_index = i
                break

        if existing_by_title_index != -1:
            existing_movie = movies[existing_by_title_index]
            if data['type'] == 'movie':
                for quality, link in data['dl_links'].items():
                    if link:
                        existing_movie['dl_links'][quality] = link
            else:
                existing_ep_names = [ep['name'] for ep in existing_movie.get('episodes', [])]
                for ep in data.get('episodes', []):
                    if ep['name'] not in existing_ep_names:
                        existing_movie.setdefault('episodes', []).append(ep)
            
            existing_movie['updated_at'] = current_time
            movies[existing_by_title_index] = existing_movie

            if db_mongo is not None:
                try:
                    db_mongo['movies'].update_one({'_id': existing_movie['_id']}, {'$set': existing_movie}, upsert=True)
                except Exception:
                    pass
        else:
            data['_id'] = movie_id
            movies.append(data)
            if db_mongo is not None:
                try:
                    db_mongo['movies'].update_one({'_id': movie_id}, {'$set': data}, upsert=True)
                except Exception:
                    pass
        
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

# টেলিগ্রামে ডাইরেক্ট চ্যানেল পোস্ট পাঠানোর জন্য সিঙ্ক-হ্যান্ডলার
def send_telegram_photo_sync(chat_id, photo_url, caption, reply_markup=None):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    payload = {
        "chat_id": chat_id,
        "photo": photo_url,
        "caption": caption,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = json.dumps(reply_markup)
    
    req = urllib.request.Request(
        url, 
        data=json.dumps(payload).encode('utf-8'), 
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            return json.loads(response.read().decode())
    except Exception as e:
        print(f"Sync Telegram Post Failed: {e}")
        return {"ok": False, "description": str(e)}

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
    movies.sort(key=lambda x: x.get('updated_at', 0), reverse=True)
    return jsonify(movies)

@web_app.route('/api/settings', methods=['GET'])
@web_app.route(f'{PREFIX}/api/settings', methods=['GET'])
def get_settings_api():
    settings = load_settings()
    return jsonify(settings)

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

@web_app.route('/api/tmdb-search', methods=['POST'])
@web_app.route(f'{PREFIX}/api/tmdb-search', methods=['POST'])
def tmdb_search_endpoint():
    if not session.get('admin_logged_in'):
        return jsonify({"error": "Unauthorized"}), 401
    data = request.json or {}
    query = data.get('query', '').strip()
    is_tv = data.get('is_tv', False)
    
    endpoint = "tv" if is_tv else "movie"
    url = f"https://api.themoviedb.org/3/search/{endpoint}?api_key={TMDB_API_KEY}&query={urllib.parse.quote(query)}"
    
    async def fetch():
        async with aiohttp.ClientSession() as s:
            async with s.get(url) as r:
                if r.status == 200: return await r.json()
        return None
        
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    res = loop.run_until_complete(fetch())
    return jsonify(res.get('results', []) if res else [])


# ==================== ওয়েব অ্যাডমিন প্যানেল ভিউজ ====================

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
    movies.sort(key=lambda x: x.get('updated_at', 0), reverse=True) 
    settings = load_settings()
    
    admin_ids_txt = ", ".join(str(aid) for aid in settings.get('admin_ids', []))
    
    return render_template_string(DASHBOARD_HTML, movies=movies, settings=settings, admin_ids_txt=admin_ids_txt, prefix=PREFIX)

@web_app.route('/admin/save-settings', methods=['POST'])
@web_app.route(f'{PREFIX}/admin/save-settings', methods=['POST'])
def admin_save_settings():
    if not session.get('admin_logged_in'):
        return redirect(f"{PREFIX}/admin/login")
        
    links_raw = request.form.get('direct_links', '')
    links_list = [l.strip() for l in re.split(r'[\r\n]+', links_raw) if l.strip().startswith('http')]
    
    admin_raw = request.form.get('admin_ids', '')
    admin_list = []
    for uid in admin_raw.replace('\n', ',').split(','):
        uid = uid.strip()
        if uid.isdigit() or (uid.startswith('-') and uid[1:].isdigit()):
            admin_list.append(int(uid))

    settings = {
        'direct_links': links_list,
        'revenue_share': int(request.form.get('revenue_share', 20)),
        'download_timer': int(request.form.get('download_timer', 5)),
        'blogger_url': request.form.get('blogger_url', '').strip(),
        'notification_channel_id': request.form.get('notification_channel_id', '').strip(),
        'admin_ids': admin_list,
        'update_channel_url': request.form.get('update_channel_url', '').strip(),
        'group_channel_url': request.form.get('group_channel_url', '').strip(),
        'custom_caption_template': request.form.get('custom_caption_template', '').strip()
    }
    
    save_settings(settings)
    load_settings(force_reload=True) # মেমোরি ক্যাশ ফোর্স রিফ্রেশ
    return redirect(f"{PREFIX}/admin")

@web_app.route('/admin/send-channel/<movie_id>')
@web_app.route(f'{PREFIX}/admin/send-channel/<movie_id>')
def send_to_channel(movie_id):
    if not session.get('admin_logged_in'):
        return redirect(f"{PREFIX}/admin/login")
        
    movies = load_movies_db()
    movie = next((m for m in movies if m.get('_id') == movie_id), None)
    if not movie:
        return "Movie/Series not found", 404
        
    settings = load_settings()
    chan_id = settings.get('notification_channel_id', '').strip()
    blog_url = settings.get('blogger_url', '').strip()
    
    if not chan_id:
        return "Error: অনুগ্রহ করে ড্যাশবোর্ড থেকে Notification Channel ID সেট করুন!", 400
    if not blog_url:
        return "Error: অনুগ্রহ করে ড্যাশবোর্ড থেকে Blogger Website URL সেট করুন!", 400

    movie_meta = movie.get('movie_data', {})
    title = movie_meta.get('title', 'N/A')
    lang = movie_meta.get('lang', 'N/A')
    genres = movie_meta.get('genres', 'N/A')
    plot = movie_meta.get('plot', 'No storyline available.')
    poster = movie_meta.get('poster', 'https://via.placeholder.com/300x450')

    if len(plot) > 350:
        plot = plot[:347] + "..."

    qualities = []
    links = movie.get('dl_links', {})
    if links.get('480p'): qualities.append("480p")
    if links.get('720p'): qualities.append("720p")
    if links.get('1080p'): qualities.append("1080p")
    quality_str = " | ".join(qualities) if qualities else "Not specified"

    caption = (
        f"🎬 <b>{title}</b>\n\n"
        f"🗣️ <b>Language:</b> {lang}\n"
        f"🎭 <b>Genres:</b> {genres}\n"
        f"💿 <b>Available Quality:</b> {quality_str}\n\n"
        f"📝 <b>Storyline:</b> {plot}"
    )

    reply_markup = {
        "inline_keyboard": [
            [{"text": "📥 Watch / Download", "url": blog_url}]
        ]
    }

    res = send_telegram_photo_sync(chan_id, poster, caption, reply_markup)
    if res.get('ok'):
        return redirect(f"{PREFIX}/admin?msg=success_posted")
    else:
        err_desc = res.get('description', 'Unknown API Error')
        return f"Failed to send post. Telegram Error: {err_desc}", 500

# ==================== কোয়ালিটি সিলেকশন হাব ও ডাউনলোড মেকানিজম ====================

# ১. ডাউনলোড মেইন হাব
@web_app.route('/download/<movie_id>')
@web_app.route(f'{PREFIX}/download/<movie_id>')
def movie_download_hub(movie_id):
    movies = load_movies_db()
    movie = next((m for m in movies if m.get('_id') == movie_id), None)
    if not movie:
        return "Content not found on server.", 404
        
    return render_template_string(HUB_HTML, movie=movie, prefix=PREFIX)

# ২. প্রগ্রেস ও নিয়ন গ্লো কাউন্টডাউন টাইমার উইজেট পেইজ
@web_app.route('/download/<movie_id>/<quality>')
@web_app.route(f'{PREFIX}/download/<movie_id>/<quality>')
def movie_download_landing(movie_id, quality):
    movies = load_movies_db()
    movie = next((m for m in movies if m.get('_id') == movie_id), None)
    if not movie:
        return "Requested content not found.", 404
        
    settings = load_settings()
    
    raw_direct_links = settings.get('direct_links', [])
    valid_direct_links = [l.strip() for l in raw_direct_links if l.strip().startswith('http')]
    
    # অ্যাডমিন প্যানেলের লিংক থেকে যেকোনো একটি র্যান্ডমলি সিলেক্ট করা হচ্ছে
    selected_direct_link = random.choice(valid_direct_links) if valid_direct_links else ""
    
    file_key = movie.get('dl_links', {}).get(quality)
    if not file_key:
        return f"Sorry, {quality} file is currently unavailable.", 404
        
    tg_bot_link = f"https://t.me/{BOT_USERNAME}?start={file_key}"
    
    # যদি ডিরেক্ট এডমিন লিংক না থাকে তবে সরাসরি বটের লিংকে রিডাইরেক্ট হবে
    if not selected_direct_link:
        selected_direct_link = tg_bot_link

    return render_template_string(
        DOWNLOAD_HTML, 
        movie=movie, 
        quality=quality, 
        timer=int(settings.get('download_timer', 5)), 
        direct_link=selected_direct_link, 
        tg_bot_link=tg_bot_link
    )

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

def clean_movie_filename(filename):
    name, _ = os.path.splitext(filename)
    
    name = re.sub(r'\[.*?\]', ' ', name)
    name = re.sub(r'\(.*?\)', ' ', name)
    
    name = re.sub(r'\b[\w\-]+\.(com|net|org|app|cc|in|xyz|vip|ws|info|live|co|club|to|co\.in)\b', ' ', name, flags=re.IGNORECASE)
    name = re.sub(r'\b(bdmoviezone|vegamovies|katmoviehd|bolly4u|9xmovies|extramovies|worldfree4u|yts|yify|psa|pahe|galaxyrg|megusta|tigole|qxr|vxt|rarbg|extratorrent)\b', ' ', name, flags=re.IGNORECASE)
    
    name = re.sub(r'[\._\-+]', ' ', name)
    
    year_match = re.search(r'\b(19\d{2}|20\d{2})\b', name)
    year = None
    if year_match:
        year = year_match.group(1)
        year_idx = name.find(year)
        name = name[:year_idx]
        
    technical_keywords = [
        r'\b480p\b', r'\b720p\b', r'\b1080p\b', r'\b2160p\b', r'\b4k\b',
        r'\bbluray\b', r'\bweb[- ]?dl\b', r'\bweb[- ]?rip\b', r'\bhd[- ]?rip\b', r'\bdvdrip\b', r'\bhd[- ]?tv\b', r'\bhdtc\b', r'\bhc\b', r'\bcam\b', r'\bcrip\b',
        r'\bdual[- ]?audio\b', r'\bmulti[- ]?audio\b', r'\benglish\b', r'\bhindi\b', r'\bbangla\b', r'\bbengali\b', r'\btamil\b', r'\btelugu\b', r'\bmalayalam\b', r'\bkannada\b',
        r'\bhin\b', r'\beng\b', r'\bben\b', r'\besub\b', r'\bsub\b', r'\bsubtitles\b', r'\bhevc\b', r'\bx264\b', r'\bx265\b', r'\bh264\b', r'\bh265\b', r'\b10bit\b', r'\baac\b',
        r'\bdd5\b', r'\bac3\b', r'\bmp3\b', r'\bdts\b', r'\bnetflix\b', r'\bamazon\b', r'\bdisney\b', r'\bhotstar\b', r'\bzee5\b', r'\bhoichoi\b', r'\bchorki\b'
    ]
    
    earliest_idx = len(name)
    for keyword in technical_keywords:
        match = re.search(keyword, name, flags=re.IGNORECASE)
        if match:
            if match.start() < earliest_idx:
                earliest_idx = match.start()
                
    name = name[:earliest_idx]
    name = re.sub(r'\s+', ' ', name).strip()
    
    return name, year

def detect_file_quality(filename):
    fn_lower = filename.lower()
    if "1080" in fn_lower: return "1080p"
    elif "720" in fn_lower: return "720p"
    elif "480" in fn_lower: return "480p"
    return "720p"

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
    
    if len(text.split()) > 1:
        param = text.split()[1]
        if param.startswith("msg_"):
            db_msg_id = int(param.split("_")[1])
            try:
                db_message = await client.get_messages(DATABASE_CHANNEL_ID, db_msg_id)
                if not (db_message.document or db_message.video):
                    await client.send_message(chat_id, "❌ ফাইলটি খুঁজে পাওয়া যায়নি বা মুছে ফেলা হয়েছে।")
                    return

                file_id = db_message.document.file_id if db_message.document else db_message.video.file_id
                file_type = 'document' if db_message.document else 'video'
                
                movies = load_movies_db()
                matched_movie = None
                matched_quality = "HD"
                file_key = f"msg_{db_msg_id}"
                
                for m in movies:
                    dl_links = m.get('dl_links', {})
                    for q, link in dl_links.items():
                        if link == file_key:
                            matched_movie = m
                            matched_quality = q
                            break
                    if matched_movie: break
                
                settings = load_settings()
                up_channel = settings.get('update_channel_url', 'https://t.me/BDMovieZone')
                grp_channel = settings.get('group_channel_url', 'https://t.me/BDMovieZoneGroup')
                
                if matched_movie:
                    m_meta = matched_movie.get('movie_data', {})
                    title = m_meta.get('title', 'Unknown Movie')
                    lang = m_meta.get('lang', 'N/A')
                    genres = m_meta.get('genres', 'N/A')
                else:
                    title = db_message.document.file_name if db_message.document else (db_message.video.file_name or "Movie File")
                    lang = "N/A"
                    genres = "Movie"
                
                caption_tpl = settings.get('custom_caption_template', '')
                if not caption_tpl:
                    caption_tpl = (
                        "🎬 <b>{title}</b>\n"
                        "🗣️ Language: <b>{lang}</b>\n"
                        "🎭 Genres: <b>{genres}</b>\n"
                        "💿 Quality: <b>{quality}</b>\n\n"
                        "⚠️ <i>কপিরাইটের কারণে ফাইলটি আগামী ৫ মিনিটের মধ্যে ডিলিট হয়ে যাবে। "
                        "এখনই ফাইলটি আপনার Saved Messages-এ ফরোয়ার্ড করে রাখুন।</i>"
                    )
                
                caption = caption_tpl.format(title=title, lang=lang, genres=genres, quality=matched_quality)
                
                buttons = [
                    [
                        InlineKeyboardButton("📢 Join Update Channel", url=up_channel),
                        InlineKeyboardButton("💬 Support Group", url=grp_channel)
                    ],
                    [
                        InlineKeyboardButton("🌐 Visit Our Website", url=settings.get('blogger_url', MAIN_WEBSITE_URL))
                    ]
                ]
                
                if file_type == 'document':
                    user_msg = await client.send_document(chat_id, file_id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
                else:
                    user_msg = await client.send_video(chat_id, file_id, caption=caption, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(buttons))
                
                warning_text = f"⚠️ কপিরাইটের কারণে ফাইলটি আগামী **{int(AUTO_DELETE_DELAY/60)} মিনিটের** মধ্যে ডিলিট হয়ে যাবে। এখনই ফাইলটি আপনার **Saved Messages**-এ ফরোয়ার্ড করে রাখুন।"
                sent_warning = await client.send_message(chat_id, warning_text)
                
                asyncio.create_task(delete_messages_after_delay(chat_id, [user_msg.id, sent_warning.id], AUTO_DELETE_DELAY))
            except Exception as e:
                print(f"Error delivering branded file: {e}")
                await client.send_message(chat_id, f"❌ ফাইলটি লোড করা যাচ্ছে না বা ডিলেট হয়ে গেছে।")
        return

    active_settings = load_settings()
    authorized_admins = [OWNER_ID] + active_settings.get('admin_ids', [])
    
    admin_btn = []
    if chat_id in authorized_admins:
        admin_btn = [
            [InlineKeyboardButton("⚙️ এডমিন প্যানেল", url=MAIN_WEBSITE_URL + "admin")],
            [InlineKeyboardButton("🌐 লাইভ মুভি সাইট", url=MAIN_WEBSITE_URL)]
        ]
    else:
        admin_btn = [
            [InlineKeyboardButton("🌐 ভিজিট করুন মুভি সাইট", url=MAIN_WEBSITE_URL)]
        ]

    await client.send_message(
        chat_id, 
        f"👋 **BD Movie Zone আল্ট্রা-ফাস্ট ইন্টেলিজেন্ট সিস্টেম!**\n\n"
        "👉 **অটো-পোস্টিং নিয়ম:** যেকোনো মুভি/সিরিজের ডাউনলোড ফাইল সরাসরি এই চ্যাটে ফরোয়ার্ড করে দিন। "
        "বট স্বয়ংক্রিয়ভাবে সাইটে পোস্ট পাবলিশ করে দেবে।",
        reply_markup=InlineKeyboardMarkup(admin_btn)
    )

@app.on_message((filters.document | filters.video) & filters.private)
async def auto_file_poster_handler(client, message):
    chat_id = message.chat.id
    
    active_settings = load_settings()
    authorized_admins = [OWNER_ID] + active_settings.get('admin_ids', [])
    
    if chat_id not in authorized_admins:
        await message.reply_text("❌ দুঃখিত! শুধুমাত্র বটের মালিক বা অনুমোদিত এডমিনরা ফাইল ডাইরেক্ট ফাইল পাবলিশ করতে পারবেন।")
        return

    filename = message.document.file_name if message.document else message.video.file_name
    if not filename:
        filename = message.caption if message.caption else "Unknown Movie"
        
    status_msg = await message.reply_text("⏳ **ফাইল ডিটেক্ট করা হয়েছে! নাম পরিষ্কার করা হচ্ছে...**")
    cleaned_title, release_year = clean_movie_filename(filename)
    detected_quality = detect_file_quality(filename)
    
    await status_msg.edit_text(f"🔍 **মুভির নাম:** `{cleaned_title}`\n💿 **কোয়ালিটি:** `{detected_quality}`\n\n⏳ TMDB ডাটাবেজে সার্চ করা হচ্ছে...")
    
    url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={urllib.parse.quote(cleaned_title)}"
    if release_year:
        url += f"&year={release_year}"
        
    movie_meta = None
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status == 200:
                res_json = await resp.json()
                results = res_json.get('results', [])
                
                # 'query_res' টাইপো পরিবর্তন করে 'results' করা হয়েছে
                if not results and release_year:
                    fallback_url = f"https://api.themoviedb.org/3/search/movie?api_key={TMDB_API_KEY}&query={urllib.parse.quote(cleaned_title)}"
                    async with session.get(fallback_url) as fb_resp:
                        if fb_resp.status == 200:
                            fb_json = await fb_resp.json()
                            results = fb_json.get('results', [])
                            
                if results:
                    top_result = results[0]
                    m_id = top_result['id']
                    detail_url = f"https://api.themoviedb.org/3/movie/{m_id}?api_key={TMDB_API_KEY}&append_to_response=images"
                    async with session.get(detail_url) as d_resp:
                        if d_resp.status == 200:
                            details = await d_resp.json()
                            actual_year = details.get('release_date', 'N/A').split('-')[0]
                            title_with_year = f"{details.get('title')} ({actual_year})"
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
            'title': f"{cleaned_title} ({release_year})" if release_year else cleaned_title,
            'poster': 'https://via.placeholder.com/300x450?text=No+Poster+Found',
            'backdrop': 'https://via.placeholder.com/1280x720?text=No+Backdrop',
            'rating': 'N/A', 'genres': 'Movie', 'plot': 'No synopsis fetched.',
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


# ==================== এডমিন প্যানেল HTML টেমপ্লেটস ====================

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
        
        .action-btn-group { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px; }
        .action-btn { flex: 1; min-width: 100px; padding: 10px; border-radius: 8px; font-size: 11px; font-weight: bold; text-align: center; text-decoration: none !important; }
        .btn-edit { background: linear-gradient(135deg, #0284c7, #0ea5e9); color: #fff; }
        .btn-channel { background: linear-gradient(135deg, #10b981, #059669); color: #fff; }
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
        
        {% if request.args.get('msg') == 'success_posted' %}
        <div class="alert alert-success alert-dismissible fade show" role="alert" style="border-radius:10px;">
            🎉 <b>পোস্টটি আপনার আপডেট টেলিগ্রাম চ্যানেলে সফলভাবে পাঠানো হয়েছে!</b>
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        </div>
        {% endif %}

        <!-- সিস্টেম ডাইনামিক কনফিগারেশন উইজেট -->
        <div class="card p-3 mb-4 shadow">
            <h6 class="text-warning mb-3" style="font-weight: 800;">🔗 Settings &amp; Dynamic Integration Configuration</h6>
            <form action="{{prefix}}/admin/save-settings" method="POST">
                
                <div class="row">
                    <div class="col-md-6 mb-3">
                        <label class="form-label text-warning font-weight-bold small">🌐 Blogger Website URL:</label>
                        <input type="url" name="blogger_url" class="form-control" value="{{settings.blogger_url}}" placeholder="https://yourdomain.blogspot.com" required>
                        <small class="text-muted small">চ্যানেল নোটিফিকেশন বাটনে এই লিংকটি সংযুক্ত হবে।</small>
                    </div>
                    <div class="col-md-6 mb-3">
                        <label class="form-label text-warning font-weight-bold small">📢 Notification Channel ID:</label>
                        <input type="text" name="notification_channel_id" class="form-control" value="{{settings.notification_channel_id}}" placeholder="-1001234567890" required>
                        <small class="text-muted small">যে আপডেট চ্যানেলে আপনি সরাসরি পোস্ট করতে চান।</small>
                    </div>
                </div>

                <div class="row">
                    <div class="col-md-6 mb-3">
                        <label class="form-label text-info font-weight-bold small">📢 Update Channel Link (For Bot Button):</label>
                        <input type="url" name="update_channel_url" class="form-control" value="{{settings.update_channel_url}}" placeholder="https://t.me/yourchannel" required>
                    </div>
                    <div class="col-md-6 mb-3">
                        <label class="form-label text-info font-weight-bold small">💬 Support Group Link (For Bot Button):</label>
                        <input type="url" name="group_channel_url" class="form-control" value="{{settings.group_channel_url}}" placeholder="https://t.me/yourgroup" required>
                    </div>
                </div>

                <div class="mb-3">
                    <label class="form-label text-info font-weight-bold small">📝 Custom Bot Caption Template:</label>
                    <textarea name="custom_caption_template" class="form-control" rows="4" placeholder="HTML Caption Template here..." required>{{settings.custom_caption_template}}</textarea>
                    <small class="text-muted small">বট যখন ইউজারকে ফাইল পাঠাবে, তখন এই ফরম্যাটে ক্যাপশন যাবে। টেমপ্লেট ভেরিয়েবল: <code>{title}</code>, <code>{lang}</code>, <code>{genres}</code>, <code>{quality}</code></small>
                </div>

                <div class="mb-3">
                    <label class="form-label text-info font-weight-bold small">👥 Authorized Admin Telegram IDs (কমা দিয়ে লিখুন):</label>
                    <input type="text" name="admin_ids" class="form-control" value="{{admin_ids_txt}}" placeholder="12345678, 87654321">
                    <small class="text-muted small">যাদেরকে বটের মাধ্যমে সরাসরি ফাইল পোস্টিং করার অনুমতি দিতে চান।</small>
                </div>

                <div class="mb-3">
                    <label class="form-label text-muted small">ডিরেক্ট লিঙ্কসমূহ / Popunder Ads (প্রতি লাইনে একটি লিংক):</label>
                    <textarea name="direct_links" class="form-control" rows="3" placeholder="https://link.com" required>{% for link in settings.direct_links %}{{link}}&#10;{% endfor %}</textarea>
                    <small class="text-muted small">ডাউনলোডের সময় ইউজার এই ডিরেক্ট লিংকগুলোর মধ্য দিয়ে যাবে (স্বয়ংক্রিয় রোটেশন হবে)।</small>
                </div>
                
                <div class="row">
                    <div class="col-md-12 mb-3">
                        <label class="form-label text-info font-weight-bold small">⏱️ ডাউনলোড প্রগ্রেস টাইমার (সেকেন্ডে):</label>
                        <input type="number" name="download_timer" class="form-control" value="{{settings.download_timer}}" min="1" max="60" required>
                    </div>
                </div>

                <div class="mb-3" style="display:none;">
                    <input type="hidden" name="revenue_share" value="{{settings.revenue_share}}">
                </div>
                
                <button type="submit" class="btn btn-warning w-100 text-dark py-2" style="border-radius:8px; font-weight: 800; font-size:13px;">আপডেট সেটিংস ও লিংক রোটেশন</button>
            </form>
        </div>

        <div class="mb-4">
            <input type="text" id="searchBox" class="form-control py-3 px-4" placeholder="🔍 সার্চ মুভি বা সিরিজ...">
        </div>

        <!-- লাইভ কার্ড লিস্ট -->
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
                         <a href="{{prefix}}/admin/send-channel/{{m._id}}" class="action-btn btn-channel">📢 Send to Channel</a>
                         <a href="{{prefix}}/admin/edit/{{m._id}}" class="action-btn btn-edit">Edit / Live Sync</a>
                         <a href="{{prefix}}/admin/delete/{{m._id}}" onclick="return confirm('মুছে ফেলতে চান?')" class="action-btn btn-delete">Delete</a>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
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
        
        .live-search-container { background: #121520; border-radius: 12px; padding: 15px; border: 1px solid rgba(255,255,255,0.08); margin-bottom: 20px; }
        .search-results-grid { display: flex; gap: 12px; overflow-x: auto; padding-bottom: 10px; scrollbar-width: thin; }
        .search-result-item { width: 100px; flex-shrink: 0; cursor: pointer; text-align: center; }
        .search-result-item img { width: 100%; height: 140px; border-radius: 8px; object-fit: cover; border: 1.5px solid rgba(255,255,255,0.1); transition: 0.2s; }
        .search-result-item img:hover { border-color: #fbbf24; transform: scale(1.05); }
        .search-result-title { font-size: 10px; color: #cbd5e1; margin-top: 5px; height: 30px; overflow: hidden; text-overflow: ellipsis; line-height: 1.2; }
    </style>
</head>
<body>
    <div class="container">
        <h4 class="text-info mb-3" style="font-weight: 800;">🛠️ এডিট ও ল্যাঙ্গুয়েজ আপডেট</h4>
        
        <div class="live-search-container">
            <h6 class="text-warning mb-2" style="font-weight: 800;">🔍 TMDB ইনস্ট্যান্ট কুইক সার্চ এডিটর</h6>
            <p class="text-muted small">মুভির নাম, TMDB ID অথবা TMDB লিংক দিয়ে "অনুসন্ধান" বোতামে চাপুন। আইডি বা লিংক দিলে সরাসরি আপডেট হয়ে যাবে:</p>
            <div class="input-group mb-3">
                <input type="text" id="liveSearchQuery" class="form-control bg-dark text-white border-secondary" placeholder="মুভির নাম, আইডি বা লিংক দিন...">
                <button type="button" id="liveSearchBtn" class="btn btn-warning text-dark font-weight-bold">অনুসন্ধান</button>
            </div>
            
            <div id="liveSearchResults" class="search-results-grid" style="display: none;"></div>
        </div>

        <form action="{{prefix}}/admin/edit/{{movie._id}}" method="POST" class="form-card">
            <div class="mb-3">
                <label class="form-label">মুভি টাইটেল:</label>
                <input type="text" name="title" id="formTitle" class="form-control bg-dark text-white" value="{{movie.movie_data.title}}" required>
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
                <label class="form-label">ব্যানার লিঙ্ক (Landscape Backdrop):</label>
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
        document.getElementById('liveSearchBtn').addEventListener('click', performTmdSearch);
        document.getElementById('liveSearchQuery').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                performTmdSearch();
            }
        });

        function performTmdSearch() {
            let input = document.getElementById('liveSearchQuery').value.trim();
            if (!input) {
                alert("অনুগ্রহ করে মুভি বা সিরিজের নাম, TMDB ID অথবা TMDB লিংক দিন!");
                return;
            }

            let resultContainer = document.getElementById('liveSearchResults');
            resultContainer.style.display = "flex";

            let isUrl = input.includes("themoviedb.org");
            let isOnlyNumber = /^[0-9]+$/.test(input); // Syntax warning resolved by replacing \d with [0-9]

            if (isUrl || isOnlyNumber) {
                resultContainer.innerHTML = "<div style='color:#fbbf24; font-size:13px; font-weight:bold; padding:10px;'>⚡ সরাসরি আইডি/লিংক ডিটেক্ট করা হয়েছে! ডাটা সিঙ্ক করা হচ্ছে...</div>";
                
                let isTv = {% if movie.type == 'series' %}true{% else %}false{% endif %};
                if (isUrl) {
                    if (input.includes("/tv/")) {
                        isTv = true;
                    } else if (input.includes("/movie/")) {
                        isTv = false;
                    }
                }

                fetch('{{prefix}}/api/tmdb-fetch', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        tmdb_input: input,
                        is_tv: isTv
                    })
                })
                .then(res => res.json())
                .then(data => {
                    if (data.error) {
                        resultContainer.innerHTML = "<div style='color:#ef4444; font-size:13px; padding:10px;'>❌ ডাটা সিঙ্ক ব্যর্থ হয়েছে! লিংক বা আইডি সঠিক কিনা যাচাই করুন।</div>";
                    } else {
                        autofillForm(data);
                        resultContainer.style.display = "none";
                        alert("🎉 সঠিক তথ্য নিখুঁতভাবে ফর্মের ঘরে বসে গেছে! এবার নিচে থাকা 'সংরক্ষণ করুন' বাটন চাপুন।");
                    }
                })
                .catch(err => {
                    resultContainer.innerHTML = "<div style='color:#ef4444; font-size:13px; padding:10px;'>❌ কানেকশন এরর!</div>";
                });
                return;
            }

            resultContainer.innerHTML = "<div style='color:#fbbf24; font-size:13px; font-weight:bold; padding:10px;'>⚡ অনুসন্ধান করা হচ্ছে...</div>";

            fetch('{{prefix}}/api/tmdb-search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: input,
                    is_tv: {% if movie.type == 'series' %}true{% else %}false{% endif %}
                })
            })
            .then(res => res.json())
            .then(results => {
                if (!results || results.length === 0) {
                    resultContainer.innerHTML = "<div style='color:#ef4444; font-size:13px; padding:10px;'>❌ কোনো ফলাফল পাওয়া যায়নি!</div>";
                    return;
                }

                resultContainer.innerHTML = "";
                results.forEach(item => {
                    let id = item.id;
                    let title = item.title || item.name;
                    let release = item.release_date || item.first_air_date || '';
                    let year = release ? release.split('-')[0] : 'N/A';
                    let posterPath = item.poster_path ? 'https://image.tmdb.org/t/p/w185' + item.poster_path : 'https://via.placeholder.com/100x140?text=No+Poster';

                    let itemIsTv = {% if movie.type == 'series' %}true{% else %}false{% endif %};

                    let div = document.createElement('div');
                    div.className = "search-result-item";
                    div.innerHTML = `
                        <img src="${posterPath}" alt="${title}" onclick="autofillWithTmdId('${id}', ${itemIsTv})">
                        <div class="search-result-title">${title} (${year})</div>
                    `;
                    resultContainer.appendChild(div);
                });
            })
            .catch(err => {
                resultContainer.innerHTML = "<div style='color:#ef4444; font-size:13px; padding:10px;'>❌ অনুসন্ধান ব্যর্থ হয়েছে!</div>";
            });
        }

        function autofillWithTmdId(id, isTv) {
            let resultContainer = document.getElementById('liveSearchResults');
            resultContainer.innerHTML = "<div style='color:#fbbf24; font-size:13px; font-weight:bold; padding:10px;'>⚡ সিঙ্ক করা হচ্ছে... অনুগ্রহ করে অপেক্ষা করুন...</div>";
            
            fetch('{{prefix}}/api/tmdb-fetch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tmdb_input: id,
                    is_tv: isTv
                })
            })
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    alert("ডাটা সিঙ্ক ব্যর্থ হয়েছে!");
                } else {
                    autofillForm(data);
                    resultContainer.style.display = "none";
                    alert("🎉 সঠিক তথ্য নিখুঁতভাবে ফর্মের ঘরে বসে গেছে! এবার 'সংরক্ষণ করুন' বাটন চাপুন।");
                }
            })
            .catch(err => { alert("কানেকশন এরর!"); });
        }

        function autofillForm(data) {
            document.getElementById('formTitle').value = data.title || "";
            document.getElementById('formPoster').value = data.poster || "";
            document.getElementById('formBackdrop').value = data.backdrop || "";
            document.getElementById('formRating').value = data.rating || "";
            document.getElementById('formGenres').value = data.genres || "";
            document.getElementById('formPlot').value = data.plot || "";
            if (data.screenshots) {
                document.getElementById('formScreens').value = data.screenshots.join('\\n');
            } else {
                document.getElementById('formScreens').value = "";
            }
        }
    </script>
</body>
</html>
"""

# ==================== কোয়ালিটি হাব টেমপ্লেট (HUB_HTML) ====================

HUB_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Download - {{movie.movie_data.title}}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        body {
            background: radial-gradient(circle at top, #0f1526 0%, #03050a 100%);
            color: #fff;
            font-family: 'Plus Jakarta Sans', sans-serif;
            min-height: 100vh;
            margin: 0;
            padding: 40px 20px;
            display: flex;
            align-items: center;
            justify-content: center;
            position: relative;
            overflow-x: hidden;
        }

        .backdrop-blur {
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            background-image: url('{{movie.movie_data.backdrop}}');
            background-size: cover;
            background-position: center;
            filter: blur(50px) brightness(0.2);
            z-index: -1;
        }

        .movie-hub-card {
            background: rgba(13, 19, 33, 0.75);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 24px;
            width: 100%;
            max-width: 580px;
            padding: 30px;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
            text-align: center;
        }

        .movie-poster {
            width: 130px;
            height: 185px;
            border-radius: 16px;
            object-fit: cover;
            border: 2px solid rgba(255, 255, 255, 0.1);
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            margin-bottom: 20px;
        }

        .movie-title {
            font-size: 22px;
            font-weight: 800;
            letter-spacing: -0.5px;
            margin-bottom: 12px;
            line-height: 1.3;
        }

        .meta-tags {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            justify-content: center;
            margin-bottom: 25px;
        }

        .meta-badge {
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.06);
            padding: 5px 12px;
            border-radius: 30px;
            font-size: 11px;
            font-weight: 600;
            color: #94a3b8;
        }

        .meta-rating {
            background: rgba(251, 191, 36, 0.1);
            color: #fbbf24;
            border-color: rgba(255, 191, 36, 0.2);
        }

        .section-divider {
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 2px;
            color: #64748b;
            margin: 20px 0;
            display: flex;
            align-items: center;
            gap: 10px;
            justify-content: center;
            font-weight: 800;
        }
        .section-divider::before, .section-divider::after {
            content: '';
            height: 1px;
            width: 40px;
            background: rgba(255,255,255,0.08);
        }

        .download-grid {
            display: flex;
            flex-direction: column;
            gap: 12px;
        }

        .download-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 16px;
            padding: 12px 18px;
            transition: all 0.3s ease;
        }

        .download-row:hover {
            background: rgba(255, 255, 255, 0.04);
            border-color: rgba(255, 255, 255, 0.08);
            transform: translateY(-2px);
        }

        .quality-info {
            text-align: left;
        }

        .quality-label {
            font-size: 14px;
            font-weight: 800;
            color: #cbd5e1;
        }

        .size-label {
            font-size: 11px;
            color: #64748b;
            font-weight: 600;
            margin-top: 2px;
        }

        .premium-btn {
            display: inline-flex;
            align-items: center;
            gap: 6px;
            padding: 10px 18px;
            border-radius: 50px;
            font-size: 11px;
            font-weight: 800;
            text-decoration: none !important;
            color: #fff !important;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            border: none;
            cursor: pointer;
        }

        .premium-btn:hover {
            transform: scale(1.05);
        }

        .btn-sunset {
            background: linear-gradient(135deg, #f59e0b 0%, #ea580c 100%);
            box-shadow: 0 4px 15px rgba(245, 158, 11, 0.25);
        }
        .btn-sunset:hover { box-shadow: 0 6px 20px rgba(245, 158, 11, 0.45); }

        .btn-electric {
            background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
            color: #030712 !important;
            box-shadow: 0 4px 15px rgba(0, 242, 254, 0.25);
        }
        .btn-electric:hover { box-shadow: 0 6px 20px rgba(0, 242, 254, 0.45); }

        .btn-royal {
            background: linear-gradient(135deg, #b156ff 0%, #7200d6 100%);
            box-shadow: 0 4px 15px rgba(177, 86, 255, 0.25);
        }
        .btn-royal:hover { box-shadow: 0 6px 20px rgba(177, 86, 255, 0.45); }

        .season-tabs {
            display: flex;
            gap: 8px;
            margin-bottom: 20px;
            background: rgba(255, 255, 255, 0.03);
            padding: 6px;
            border-radius: 12px;
            border: 1px solid rgba(255,255,255,0.05);
        }

        .season-tab-btn {
            flex: 1;
            padding: 10px;
            border-radius: 8px;
            background: transparent;
            border: none;
            color: #94a3b8;
            font-weight: 700;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s ease;
        }

        .season-tab-btn.active {
            background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
            color: #030712;
            box-shadow: 0 4px 12px rgba(0, 242, 254, 0.25);
        }

        .episode-card {
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid rgba(255, 255, 255, 0.04);
            border-radius: 12px;
            overflow: hidden;
            margin-bottom: 10px;
            transition: all 0.3s ease;
        }

        .episode-card.open {
            border-color: rgba(0, 242, 254, 0.2);
            background: rgba(255, 255, 255, 0.03);
        }

        .episode-bar {
            padding: 16px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            font-weight: 700;
            font-size: 14px;
            color: #cbd5e1;
        }

        .episode-icon {
            font-size: 11px;
            color: #94a3b8;
            transition: transform 0.3s ease;
        }

        .episode-content-box {
            display: none;
            padding: 15px;
            background: rgba(0, 0, 0, 0.25);
            border-top: 1px solid rgba(255, 255, 255, 0.03);
        }
    </style>
</head>
<body>

    <div class="backdrop-blur"></div>

    <div class="movie-hub-card shadow-lg">
        
        <img src="{{movie.movie_data.poster}}" alt="Poster" class="movie-poster">
        <div class="movie-title">{{movie.movie_data.title}}</div>
        
        <div class="meta-tags">
            <span class="meta-badge meta-rating">⭐️ {{movie.movie_data.rating}}</span>
            <span class="meta-badge">{{movie.movie_data.lang}}</span>
            <span class="meta-badge">{{movie.movie_data.genres}}</span>
        </div>

        <div class="section-divider">Select Quality / Episode</div>

        <div class="download-grid">
            {% if movie.type == 'movie' %}
                {% if movie.dl_links.get('480p') %}
                <div class="download-row">
                    <div class="quality-info">
                        <div class="quality-label">🎥 SD 480p Quality</div>
                        <div class="size-label">File Size: Normal | Format: MKV</div>
                    </div>
                    <a href="{{prefix}}/download/{{movie._id}}/480p" class="premium-btn btn-sunset">Download 480p</a>
                </div>
                {% endif %}

                {% if movie.dl_links.get('720p') %}
                <div class="download-row">
                    <div class="quality-info">
                        <div class="quality-label">🎬 HD 720p Quality</div>
                        <div class="size-label">File Size: Optimized | Format: MKV</div>
                    </div>
                    <a href="{{prefix}}/download/{{movie._id}}/720p" class="premium-btn btn-electric">Download 720p</a>
                </div>
                {% endif %}

                {% if movie.dl_links.get('1080p') %}
                <div class="download-row">
                    <div class="quality-info">
                        <div class="quality-label">🍿 Full HD 1080p Quality</div>
                        <div class="size-label">File Size: Full Quality | Format: MKV</div>
                    </div>
                    <a href="{{prefix}}/download/{{movie._id}}/1080p" class="premium-btn btn-royal">Download 1080p</a>
                </div>
                {% endif %}
            {% else %}
                {% if not movie.get('episodes') %}
                    <p class="text-muted small">No episodes uploaded yet.</p>
                {% else %}
                    {% for ep in movie.episodes %}
                    <div class="episode-card">
                        <div class="episode-bar" onclick="toggleEpisode('ep-{{loop.index}}', this)">
                            <span>⚡ {{ep.name}}</span>
                            <span class="episode-icon">▼</span>
                        </div>
                        <div id="ep-{{loop.index}}" class="episode-content-box">
                            <div class="d-flex flex-column gap-2">
                                {% if ep.links and ep.links.get('480p') %}
                                <a href="{{prefix}}/download/{{movie._id}}/480p" class="premium-btn btn-sunset w-100 justify-content-center">🎥 SD 480p Quality</a>
                                {% endif %}
                                {% if ep.links and ep.links.get('720p') %}
                                <a href="{{prefix}}/download/{{movie._id}}/720p" class="premium-btn btn-electric w-100 justify-content-center">🎬 HD 720p Quality</a>
                                {% endif %}
                                {% if ep.links and ep.links.get('1080p') %}
                                <a href="{{prefix}}/download/{{movie._id}}/1080p" class="premium-btn btn-royal w-100 justify-content-center">🍿 Full HD 1080p Quality</a>
                                {% endif %}
                            </div>
                        </div>
                    </div>
                    {% endfor %}
                {% endif %}
            {% endif %}
        </div>
        
        <p class="text-muted small mt-4 mb-0" style="font-size: 11px; opacity: 0.6;">⚡ Powered by BD Movie Zone Hub</p>
    </div>

    <script>
        function toggleEpisode(id, barElement) {
            const contentBox = document.getElementById(id);
            const icon = barElement.querySelector('.episode-icon');
            const card = barElement.parentElement;

            if (contentBox.style.display === "block") {
                contentBox.style.display = "none";
                icon.style.transform = "rotate(0deg)";
                card.classList.remove('open');
            } else {
                contentBox.style.display = "block";
                icon.style.transform = "rotate(180deg)";
                card.classList.add('open');
            }
        }
    </script>
</body>
</html>
"""

# ==================== প্রিমিয়াম নিয়ন প্রগ্রেস টাইমার টেমপ্লেট (DOWNLOAD_HTML) ====================

DOWNLOAD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Download - {{movie.movie_data.title}}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { 
            background: radial-gradient(circle, #0e111d 0%, #05060a 100%); 
            color: #fff; 
            font-family: 'Plus Jakarta Sans', sans-serif;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            overflow-x: hidden;
            position: relative;
        }
        
        .backdrop-bg {
            position: absolute;
            top: 0; left: 0; width: 100%; height: 100%;
            background-image: url('{{movie.movie_data.backdrop}}');
            background-size: cover;
            background-position: center;
            filter: blur(40px) brightness(0.25);
            z-index: -1;
        }

        .landing-card {
            background: rgba(15, 17, 26, 0.75);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.09);
            border-radius: 24px;
            width: 100%;
            max-width: 480px;
            padding: 30px;
            text-align: center;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7);
            position: relative;
        }

        .movie-poster {
            width: 130px;
            height: 185px;
            border-radius: 16px;
            object-fit: cover;
            border: 2px solid rgba(255, 255, 255, 0.12);
            box-shadow: 0 15px 30px rgba(0,0,0,0.6);
            margin-bottom: 20px;
        }

        .movie-title {
            font-size: 20px;
            font-weight: 800;
            color: #fff;
            margin-bottom: 8px;
            letter-spacing: -0.5px;
            line-height: 1.3;
        }

        .quality-badge {
            background: rgba(0, 242, 254, 0.08);
            color: #00f2fe;
            font-weight: 700;
            font-size: 12px;
            padding: 6px 16px;
            border-radius: 30px;
            display: inline-block;
            margin-bottom: 25px;
            border: 1px solid rgba(0, 242, 254, 0.2);
            letter-spacing: 0.5px;
        }

        .progress-ring-container {
            position: relative;
            width: 120px;
            height: 120px;
            margin: 15px auto;
        }

        .progress-ring {
            transform: rotate(-90deg);
        }

        .progress-ring__circle {
            transition: stroke-dashoffset 0.3s;
            transform-origin: 50% 50%;
        }

        .timer-display {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 28px;
            font-weight: 800;
            color: #00f2fe;
            text-shadow: 0 0 10px rgba(0, 242, 254, 0.5);
        }

        .status-text {
            font-size: 14px;
            color: #94a3b8;
            margin-top: 15px;
            font-weight: 600;
        }

        .btn-download {
            display: none;
            align-items: center;
            justify-content: center;
            gap: 10px;
            background: linear-gradient(135deg, #00f2fe 0%, #4facfe 100%);
            color: #030712 !important;
            font-weight: 800;
            font-size: 16px;
            padding: 16px 32px;
            border-radius: 50px;
            border: none;
            box-shadow: 0 0 20px rgba(0, 242, 254, 0.35);
            transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            width: 100%;
            text-transform: uppercase;
            letter-spacing: 1px;
            cursor: pointer;
            margin-top: 15px;
        }

        .btn-download:hover {
            transform: scale(1.03);
            box-shadow: 0 0 30px rgba(0, 242, 254, 0.6);
        }

        .btn-download svg {
            width: 20px;
            height: 20px;
            fill: currentColor;
        }
    </style>
</head>
<body>

    <div class="backdrop-bg"></div>

    <div class="landing-card shadow-lg">
        <img src="{{movie.movie_data.poster}}" alt="Poster" class="movie-poster">
        <div class="movie-title">{{movie.movie_data.title}}</div>
        <div class="quality-badge">Selected: {{quality}}</div>

        <div id="countdownBox">
            <div class="progress-ring-container">
                <svg class="progress-ring" width="120" height="120">
                    <circle class="progress-ring__background" stroke="rgba(255,255,255,0.05)" stroke-width="6" fill="transparent" r="50" cx="60" cy="60"/>
                    <circle class="progress-ring__circle" stroke="url(#gradient)" stroke-width="6" fill="transparent" r="50" cx="60" cy="60"/>
                </svg>
                <div class="timer-display" id="timerValue">{{timer}}</div>
            </div>
            <div class="status-text" id="statusLabel">Securing connection... Please wait</div>
        </div>

        <button id="downloadBtn" class="btn-download" onclick="triggerDownload()">
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.53c-.26-.81-1-1.4-1.9-1.4h-1v-3c0-.55-.45-1-1-1h-6v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z"/></svg>
            ⚡ Get Download File (Telegram)
        </button>
        
        <p class="text-muted small mt-4 mb-0" style="font-size: 11px; opacity:0.6;">⚠️ Disable adblocker if downloading is interrupted.</p>
    </div>

    <svg width="0" height="0">
        <defs>
            <linearGradient id="gradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stop-color="#00f2fe" />
                <stop offset="100%" stop-color="#4facfe" />
            </linearGradient>
        </defs>
    </svg>

    <script>
        const circle = document.querySelector('.progress-ring__circle');
        const radius = circle.r.baseVal.value;
        const circumference = radius * 2 * Math.PI;

        circle.style.strokeDasharray = `${circumference} ${circumference}`;
        circle.style.strokeDashoffset = `${circumference}`;

        function setProgress(percent) {
            const offset = circumference - (percent / 100 * circumference);
            circle.style.strokeDashoffset = offset;
        }

        let initialTimer = parseInt("{{timer}}") || 5;
        let countdown = initialTimer;
        
        setProgress(100);

        const interval = setInterval(() => {
            countdown--;
            document.getElementById('timerValue').innerText = countdown;
            
            let percent = (countdown / initialTimer) * 100;
            setProgress(percent);

            if (countdown <= 0) {
                clearInterval(interval);
                document.getElementById('countdownBox').style.display = 'none';
                document.getElementById('downloadBtn').style.display = 'inline-flex';
            }
        }, 1000);

        function triggerDownload() {
            var adLink = "{{direct_link}}";
            var tgLink = "{{tg_bot_link}}";
            
            if (adLink && adLink !== tgLink) {
                window.open(adLink, "_blank");
                setTimeout(() => {
                    window.location.href = tgLink;
                }, 1000); 
            } else {
                window.location.href = tgLink;
            }
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
