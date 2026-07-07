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

# --- অ্যাডমিন ও ডিরেক্ট লিংক সেটিংস লোডার ---
def load_settings():
    default_settings = {
        'direct_links': ["https://omg10.com/4/11047054"],
        'revenue_share': 20,
        'download_timer': 5,
        'website_url': MAIN_WEBSITE_URL,
        'update_channel_id': "-1003506219023",
        'admin_ids_str': str(OWNER_ID)
    }
    if db_mongo is not None:
        try:
            config = db_mongo['settings'].find_one({'_id': 'system_config'})
            if config: 
                for key, val in default_settings.items():
                    config.setdefault(key, val)
                return config
        except Exception: pass
    if os.path.exists("settings.json"):
        try:
            with open("settings.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                for key, val in default_settings.items():
                    data.setdefault(key, val)
                return data
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

# কাস্টম ইউজার সেফগার্ড সহ ডাইনামিক ওয়েবসাইট লিঙ্ক প্রোটেকশন ফাংশন
def get_website_url():
    settings = load_settings()
    url = settings.get('website_url', '').strip()
    if not url:
        url = MAIN_WEBSITE_URL
    url = url.rstrip('/')
    if url.endswith('/admin'):
        url = url[:-6]
    return url + '/'

# মাল্টিপল অ্যাডমিন আইডি সংগ্রহের ফাংশন
def get_admin_ids():
    settings = load_settings()
    admin_str = settings.get('admin_ids_str', '').strip()
    admins = [OWNER_ID]
    if admin_str:
        for uid in admin_str.split(','):
            try:
                admins.append(int(uid.strip()))
            except ValueError:
                pass
    return list(set(admins))

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
            except Exception: pass
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
                except Exception: pass
        else:
            data['_id'] = movie_id
            movies.append(data)
            if db_mongo is not None:
                try:
                    db_mongo['movies'].update_one({'_id': movie_id}, {'$set': data}, upsert=True)
                except Exception: pass
        
    with open("movies_db.json", "w", encoding="utf-8") as f:
        json.dump(movies, f, indent=4, ensure_ascii=False)

def delete_movie_from_db(movie_id):
    if db_mongo is not None:
        try:
            db_mongo['movies'].delete_one({'_id': movie_id})
            return
        except Exception: pass
    movies = load_movies_db()
    movies = [m for m in movies if m.get('_id') != movie_id]
    with open("movies_db.json", "w", encoding="utf-8") as f:
        json.dump(movies, f, indent=4, ensure_ascii=False)

# ==================== পাবলিক ডাইনামিক মুভি পোর্টাল (হোমপেজ) ====================

@web_app.route('/')
@web_app.route(f'{PREFIX}/')
def home_portal():
    movies = load_movies_db()
    movies.sort(key=lambda x: x.get('updated_at', 0), reverse=True) 
    return render_template_string(PORTAL_HTML, movies=movies, prefix=PREFIX)

@web_app.route('/movie/<movie_id>')
@web_app.route(f'{PREFIX}/movie/<movie_id>')
def view_movie_public(movie_id):
    movies = load_movies_db()
    movie = next((m for m in movies if m.get('_id') == movie_id), None)
    if not movie:
        return "মুভিটি ডাটাবেজে পাওয়া যায়নি!", 404
    settings = load_settings()
    return render_template_string(MOVIE_DETAIL_HTML, movie=movie, settings=settings, bot_username=BOT_USERNAME, prefix=PREFIX)


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
    posted_status = request.args.get('posted')
    return render_template_string(DASHBOARD_HTML, movies=movies, settings=settings, posted_status=posted_status, prefix=PREFIX)

@web_app.route('/admin/save-settings', methods=['POST'])
@web_app.route(f'{PREFIX}/admin/save-settings', methods=['POST'])
def admin_save_settings():
    if not session.get('admin_logged_in'):
        return redirect(f"{PREFIX}/admin/login")
    links_raw = request.form.get('direct_links', '')
    links_list = [l.strip() for l in links_raw.split('\n') if l.strip().startswith('http')]
    settings = {
        'direct_links': links_list,
        'revenue_share': int(request.form.get('revenue_share', 20)),
        'download_timer': int(request.form.get('download_timer', 5)),
        'website_url': request.form.get('website_url', '').strip(),
        'update_channel_id': request.form.get('update_channel_id', '').strip(),
        'admin_ids_str': request.form.get('admin_ids_str', '').strip()
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

@web_app.route('/admin/post-channel/<movie_id>')
@web_app.route(f'{PREFIX}/admin/post-channel/<movie_id>')
def post_to_channel(movie_id):
    if not session.get('admin_logged_in'):
        return redirect(f"{PREFIX}/admin/login")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    success = loop.run_until_complete(send_movie_to_channel_job(movie_id))
    
    if success:
        return redirect(f"{PREFIX}/admin?posted=success")
    else:
        return redirect(f"{PREFIX}/admin?posted=failed")

async def send_movie_to_channel_job(movie_id):
    movies = load_movies_db()
    movie = next((m for m in movies if m.get('_id') == movie_id), None)
    if not movie:
        return False
    
    settings = load_settings()
    channel_id = settings.get('update_channel_id', '').strip()
    if not channel_id:
        return False
        
    # ইউজারনেম নাকি সংখ্যাভিত্তিক আইডি তা যাচাই করে পাঠানো
    if channel_id.startswith('-') or channel_id.isdigit():
        try:
            channel_id = int(channel_id)
        except ValueError:
            pass
        
    m_meta = movie['movie_data']
    web_link = f"{get_website_url()}movie/{movie_id}"
    
    caption = (
        f"🎬 <b>{m_meta['title']}</b>\n\n"
        f"⭐ Rating: <b>{m_meta['rating']}</b>\n"
        f"🗣️ Language: <b>{m_meta['lang']}</b>\n"
        f"🎭 Genres: <b>{m_meta['genres']}</b>\n\n"
        f"📝 <b>Plot:</b> {m_meta['plot'][:250]}...\n\n"
        f"📥 নিচের বাটনে ক্লিক করে সরাসরি ওয়েবসাইট থেকে ডাউনলোড করুন।"
    )
    
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 ডাউনলোড লিংক (Download Link)", url=web_link)]
    ])
    
    try:
        if m_meta['poster'] and m_meta['poster'].startswith('http'):
            await app.send_photo(chat_id=channel_id, photo=m_meta['poster'], caption=caption, reply_markup=markup, parse_mode=ParseMode.HTML)
        else:
            await app.send_message(chat_id=channel_id, text=caption, reply_markup=markup, parse_mode=ParseMode.HTML)
        return True
    except Exception as e:
        print(f"Failed to post to channel: {e}")
        return False

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
                user_msg_id = await client.copy_message(chat_id, DATABASE_CHANNEL_ID, db_msg_id)
                warning_text = f"⚠️ কপিরাইটের কারণে ফাইলটি আগামী **{int(AUTO_DELETE_DELAY/60)} মিনিটের** মধ্যে ডিলিট হয়ে যাবে। এখনই ফাইলটি আপনার **Saved Messages**-এ ফরোয়ার্ড করে রাখুন।"
                sent_warning = await client.send_message(chat_id, warning_text)
                asyncio.create_task(delete_messages_after_delay(chat_id, [user_msg_id.id, sent_warning.id], AUTO_DELETE_DELAY))
            except Exception as e:
                await client.send_message(chat_id, f"❌ ফাইলটি লোড করা যাচ্ছে না বা ডিলেট হয়ে গেছে।")
        return

    live_site_url = get_website_url()
    admin_btn = []
    
    # অ্যাডমিন আইডি লিষ্টিং ভেরিফিকেশন
    if chat_id in get_admin_ids():
        admin_btn = [
            [InlineKeyboardButton("⚙️ অ্যাডমিন কন্ট্রোল প্যানেল (Login)", url=live_site_url + "admin")],
            [InlineKeyboardButton("🌐 আমার লাইভ মুভি সাইট", url=live_site_url)]
        ]
    else:
        admin_btn = [
            [InlineKeyboardButton("🌐 ভিজিট করুন মুভি সাইট", url=live_site_url)]
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
    
    if chat_id not in get_admin_ids():
        await message.reply_text("❌ দুঃখিত! আপনি বটের অনুমোদিত অ্যাডমিন তালিকায় নেই।")
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

    live_site_url = get_website_url()
    success_text = (
        f"🎉 **পোস্টটি সফলভাবে তৈরি ও লাইভ পাবলিশ করা হয়েছে!**\n\n"
        f"🎬 **নাম:** `{movie_meta['title']}`\n"
        f"💿 **কোয়ালিটি লিংক যুক্ত হয়েছে:** `{detected_quality}`\n"
        f"🗣 **ল্যাঙ্গুয়েজ ট্যাগ:** `N/A` (এখনই প্যানেল থেকে ট্যাগ বসান)\n\n"
        f"💡 একই মুভির ভিন্ন কোয়ালিটি লিংক এড করতে চাইলে শুধু ফাইলটি ফরোয়ার্ড করলেই হবে, ডাটা অটোমেটিক মার্জ হয়ে যাবে।"
    )
    
    # এখানে সরাসরি নির্দিষ্ট মুভির পাবলিক পেজ `/movie/id` দেওয়া হয়েছে
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛠️ ল্যাঙ্গুয়েজ ট্যাগ বসান (অ্যাডমিন প্যানেল)", url=live_site_url + "admin")],
        [InlineKeyboardButton("🌐 সাইটে পোস্টটি দেখুন", url=live_site_url + "movie/" + m_id_unique)]
    ])
    
    await status_msg.delete()
    await message.reply_text(success_text, reply_markup=markup)

async def delete_messages_after_delay(chat_id, message_ids, delay):
    await asyncio.sleep(delay)
    for msg_id in message_ids:
        try: await app.delete_messages(chat_id, msg_id)
        except Exception: pass


# ==================== এডমিন প্যানেল ও ওয়েবসাইট টেমপ্লেটসমূহ ====================

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
        .action-btn { flex: 1; min-width: 90px; padding: 10px; border-radius: 8px; font-size: 12px; font-weight: bold; text-align: center; text-decoration: none !important; }
        .btn-edit { background: linear-gradient(135deg, #0284c7, #0ea5e9); color: #fff; }
        .btn-channel { background: linear-gradient(135deg, #2563eb, #3b82f6); color: #fff; }
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
        {% if posted_status == 'success' %}
        <div class="alert alert-success alert-dismissible fade show" role="alert">
            <strong>🎉 চমৎকার!</strong> পোস্টটি সফলভাবে টেলিগ্রাম চ্যানেলে পাবলিশ করা হয়েছে।
        </div>
        {% elif posted_status == 'failed' %}
        <div class="alert alert-danger alert-dismissible fade show" role="alert">
            <strong>❌ ব্যর্থ হয়েছে!</strong> চ্যানেল আইডি চেক করুন অথবা নিশ্চিত করুন বটটি আপনার চ্যানেলের এডমিন রয়েছে।
        </div>
        {% endif %}

        <div class="card p-3 mb-4 shadow">
            <h6 class="text-warning mb-3" style="font-weight: 800;">🔗 Configuration Panel</h6>
            <form action="{{prefix}}/admin/save-settings" method="POST">
                <div class="mb-3">
                    <label class="form-label text-muted small">🌐 আমার ওয়েবসাইট লিংক (Website URL):</label>
                    <input type="url" name="website_url" class="form-control" value="{{settings.website_url}}" placeholder="উদা: https://mysite.koyeb.app/view/Movie-Post-Generator/" required>
                </div>

                <div class="mb-3">
                    <label class="form-label text-muted small">👥 কন্ট্রোলিং অ্যাডমিন আইডি সমূহ (কমা দিয়ে লিখুন):</label>
                    <input type="text" name="admin_ids_str" class="form-control" value="{{settings.admin_ids_str}}" placeholder="উদা: 8297458824, 12345678" required>
                    <small class="text-muted small">এখানে যে টেলিগ্রাম ইউজার আইডিগুলো কমা দিয়ে দেবেন তারা এই বটের এডমিন অ্যাক্সেস পাবেন।</small>
                </div>

                <div class="mb-3">
                    <label class="form-label text-muted small">📢 টেলিগ্রাম আপডেট চ্যানেল আইডি (Update Channel ID):</label>
                    <input type="text" name="update_channel_id" class="form-control" value="{{settings.update_channel_id}}" placeholder="উদা: -100xxxxxxxxxx বা @MyChannel" required>
                </div>

                <div class="mb-3">
                    <label class="form-label text-muted small">ডিরেক্ট লিঙ্কসমূহ (প্রতি লাইনে একটি শর্টলিঙ্ক):</label>
                    <textarea name="direct_links" class="form-control" rows="2" placeholder="https://link.com" required>{% for link in settings.direct_links %}{{link}}&#10;{% endfor %}</textarea>
                </div>
                
                <div class="mb-3">
                    <label class="form-label text-info font-weight-bold small">⏱️ ডাউনলোড প্রগ্রেস টাইমার (সেকেন্ডে):</label>
                    <input type="number" name="download_timer" class="form-control" value="{{settings.download_timer}}" min="1" max="60" required>
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
                         <a href="{{prefix}}/admin/edit/{{m._id}}" class="action-btn btn-edit">Edit / Sync</a>
                         <a href="{{prefix}}/admin/post-channel/{{m._id}}" class="action-btn btn-channel">📢 Post Channel</a>
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
            <p class="text-muted small">মুভিটির সঠিক নাম লিখে "অনুসন্ধান" করুন এবং সঠিক পোস্টারটির উপর টাচ করলেই সব ডেটা পরিবর্তন হয়ে যাবে:</p>
            <div class="input-group mb-3">
                <input type="text" id="liveSearchQuery" class="form-control bg-dark text-white border-secondary" placeholder="মুভির নাম লিখুন...">
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
        document.getElementById('liveSearchBtn').addEventListener('click', function() {
            let query = document.getElementById('liveSearchQuery').value.trim();
            if(!query) { alert("সার্চ করতে মুভির নাম লিখুন!"); return; }
            
            let resultContainer = document.getElementById('liveSearchResults');
            resultContainer.style.display = "flex";
            resultContainer.innerHTML = "<div style='color:#e2e8f0; font-size:12px; padding:10px;'>⏳ লোড হচ্ছে...</div>";
            
            fetch('{{prefix}}/api/tmdb-search', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    query: query,
                    is_tv: {% if movie.type == 'series' %}true{% else %}false{% endif %}
                })
            })
            .then(res => res.json())
            .then(data => {
                resultContainer.innerHTML = "";
                if(data.length === 0) {
                    resultContainer.innerHTML = "<div style='color:#ef4444; font-size:12px; padding:10px;'>❌ কোনো ফলাফল পাওয়া যায়নি!</div>";
                    return;
                }
                data.forEach(item => {
                    let title = item.title || item.name;
                    let year = (item.release_date || item.first_air_date || 'N/A').split('-')[0];
                    let posterPath = item.poster_path ? 'https://image.tmdb.org/t/p/w185' + item.poster_path : 'https://via.placeholder.com/100x140?text=No+Poster';
                    
                    let div = document.createElement('div');
                    div.className = "search-result-item";
                    div.innerHTML = `
                        <img src="${posterPath}" alt="Poster" onclick="autofillWithTmdId('${item.id}')">
                        <div class="search-result-title">${title} (${year})</div>
                    `;
                    resultContainer.appendChild(div);
                });
            })
            .catch(err => {
                resultContainer.innerHTML = "<div style='color:#ef4444; font-size:12px; padding:10px;'>❌ কানেশন ত্রুটি ঘটেছে!</div>";
            });
        });

        function autofillWithTmdId(id) {
            let resultContainer = document.getElementById('liveSearchResults');
            resultContainer.innerHTML = "<div style='color:#fbbf24; font-size:13px; font-weight:bold; padding:10px;'>⚡ সিঙ্ক করা হচ্ছে... অনুগ্রহ করে ১ সেকেন্ড অপেক্ষা করুন...</div>";
            
            fetch('{{prefix}}/api/tmdb-fetch', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    tmdb_input: id,
                    is_tv: {% if movie.type == 'series' %}true{% else %}false{% endif %}
                })
            })
            .then(res => res.json())
            .then(data => {
                if(data.error) {
                    alert("ডাটা সিঙ্ক ব্যর্থ হয়েছে!");
                } else {
                    document.getElementById('formTitle').value = data.title;
                    document.getElementById('formPoster').value = data.poster;
                    document.getElementById('formBackdrop').value = data.backdrop;
                    document.getElementById('formRating').value = data.rating;
                    document.getElementById('formGenres').value = data.genres;
                    document.getElementById('formPlot').value = data.plot;
                    if(data.screenshots) document.getElementById('formScreens').value = data.screenshots.join('\\n');
                    
                    resultContainer.style.display = "none";
                    alert("🎉 সঠিক তথ্য নিখুঁতভাবে ফর্মের ঘরে বসে গেছে! এবার 'সংরক্ষণ করুন' বাটন চাপুন।");
                }
            })
            .catch(err => { alert("কানেকশন এরর!"); });
        }
    </script>
</body>
</html>
"""


# ==================== পাবলিক ডাইনামিক মুভি পোর্টাল (হোমপেজ থিম) ====================

PORTAL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BD Movie Zone - Premium Streaming & Download Directory</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        body { background-color: #06070d; color: #f1f5f9; font-family: 'Plus Jakarta Sans', sans-serif; padding-top: 30px; }
        .site-brand { font-size: 24px; font-weight: 800; color: #38bdf8; text-decoration: none !important; letter-spacing: 0.5px; }
        .hero-section { background: radial-gradient(circle, rgba(15,17,26,0.6) 0%, rgba(6,7,13,1) 100%); padding: 50px 0; text-align: center; }
        .hero-title { font-size: 34px; font-weight: 800; color: #fff; margin-bottom: 12px; }
        .movie-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 18px; margin-top: 30px; }
        .movie-card {
            background: #0f111a;
            border-radius: 16px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.05);
            transition: 0.2s;
            cursor: pointer;
            position: relative;
        }
        .movie-card:hover { transform: translateY(-5px); border-color: #38bdf8; }
        .card-poster { width: 100%; height: 230px; object-fit: cover; }
        .card-details { padding: 12px; }
        .card-title { font-size: 14px; font-weight: 700; color: #fff; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-bottom: 5px; }
        .card-meta { display: flex; justify-content: space-between; align-items: center; font-size: 11px; color: #94a3b8; }
        .lang-badge { background: rgba(56, 189, 248, 0.15); color: #38bdf8; padding: 2px 8px; border-radius: 12px; font-weight: bold; }
    </style>
</head>
<body>

    <div class="container mb-4 d-flex justify-content-between align-items-center">
        <a href="{{prefix}}/" class="site-brand">🎬 BD MOVIE ZONE</a>
    </div>

    <div class="hero-section">
        <div class="container">
            <h1 class="hero-title">Unlimited Movies &amp; Series</h1>
            <p class="text-muted small">একদম বিজ্ঞাপনমুক্ত হাই-স্পিড আল্ট্রা ফাস্ট ফাইল ডাউনলোড সিস্টেম!</p>
        </div>
    </div>

    <div class="container mb-5">
        <div class="movie-grid">
            {% for m in movies %}
            <div class="movie-card shadow-sm" onclick="location.href='{{prefix}}/movie/{{m._id}}'">
                <img src="{{m.movie_data.poster}}" class="card-poster" alt="Poster">
                <div class="card-details">
                    <div class="card-title">{{m.movie_data.title}}</div>
                    <div class="card-meta">
                        <span class="lang-badge">{{m.movie_data.lang}}</span>
                        <span>⭐ {{m.movie_data.rating}}</span>
                    </div>
                </div>
            </div>
            {% endfor %}
        </div>
    </div>

</body>
</html>
"""


# ==================== পাবলিক রেসপন্সিভ ডাউনলোড পেজ HTML ====================

MOVIE_DETAIL_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{movie.movie_data.title}} - BD Movie Zone</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;600;700;800&display=swap" rel="stylesheet">
    <style>
        body {
            background-color: #06070d;
            color: #f1f5f9;
            font-family: 'Plus Jakarta Sans', sans-serif;
            overflow-x: hidden;
            position: relative;
        }
        .backdrop-bg {
            position: absolute;
            top: 0; left: 0; width: 100%; height: 50vh;
            background: url('{{movie.movie_data.backdrop}}') no-repeat center top;
            background-size: cover;
            filter: blur(15px) brightness(0.25);
            z-index: -1;
        }
        .movie-card {
            background: rgba(15, 17, 26, 0.7);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 24px;
            backdrop-filter: blur(20px);
            padding: 24px;
            margin-top: 100px;
        }
        .poster-img {
            width: 100%;
            border-radius: 16px;
            box-shadow: 0 10px 25px rgba(0,0,0,0.5);
            border: 1px solid rgba(255,255,255,0.1);
        }
        .movie-title {
            font-size: 26px;
            font-weight: 800;
            color: #fff;
            margin-bottom: 12px;
        }
        .meta-tag {
            background: rgba(56, 189, 248, 0.12);
            color: #38bdf8;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: bold;
            display: inline-block;
            margin-right: 8px;
            margin-bottom: 8px;
        }
        .download-btn {
            background: linear-gradient(135deg, #fbbf24, #f59e0b);
            color: #000;
            font-weight: 800;
            padding: 14px;
            border-radius: 14px;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            cursor: pointer;
            border: none;
            transition: 0.2s;
            box-shadow: 0 4px 15px rgba(245, 158, 11, 0.2);
            width: 100%;
            margin-bottom: 12px;
            text-decoration: none !important;
        }
        .download-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(245, 158, 11, 0.35);
            color: #000;
        }
        .timer-overlay {
            position: fixed;
            top: 0; left: 0; width: 100%; height: 100%;
            background: rgba(4, 5, 10, 0.85);
            backdrop-filter: blur(20px);
            z-index: 9999;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            visibility: hidden;
            opacity: 0;
            transition: 0.3s ease-in-out;
        }
        .timer-overlay.active {
            visibility: visible;
            opacity: 1;
        }
        .timer-wrapper {
            position: relative;
            width: 120px;
            height: 120px;
        }
        .timer-svg {
            transform: rotate(-90deg);
            width: 120px;
            height: 120px;
        }
        .timer-bg {
            fill: none;
            stroke: rgba(255, 255, 255, 0.08);
            stroke-width: 6;
        }
        .timer-bar {
            fill: none;
            stroke: #38bdf8;
            stroke-width: 6;
            stroke-linecap: round;
            stroke-dasharray: 283; 
            stroke-dashoffset: 0;
            transition: stroke-dashoffset 1s linear;
        }
        .timer-text {
            position: absolute;
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            font-size: 28px;
            font-weight: 800;
            color: #fff;
        }
        .unlocked-btn {
            background: linear-gradient(135deg, #10b981, #059669);
            color: #fff;
            padding: 14px 28px;
            border-radius: 14px;
            font-weight: 800;
            display: none;
            text-decoration: none !important;
            animation: pulseGlow 1.5s infinite alternate;
        }
        @keyframes pulseGlow {
            0% { box-shadow: 0 0 10px rgba(16, 185, 129, 0.5); }
            100% { box-shadow: 0 0 25px rgba(16, 185, 129, 0.8); }
        }
    </style>
</head>
<body>

    <div class="backdrop-bg"></div>

    <div class="container pb-5">
        <div class="movie-card shadow-lg">
            <div class="row">
                <div class="col-md-4 text-center">
                    <img src="{{movie.movie_data.poster}}" class="poster-img mb-4 mb-md-0" alt="Poster">
                </div>
                <div class="col-md-8">
                    <h1 class="movie-title">{{movie.movie_data.title}}</h1>
                    <div class="mb-3">
                        <span class="meta-tag">⭐ {{movie.movie_data.rating}}</span>
                        <span class="meta-tag">🗣️ {{movie.movie_data.lang}}</span>
                        <span class="meta-tag">🎭 {{movie.movie_data.genres}}</span>
                    </div>

                    <h6 class="text-white font-weight-bold mb-2" style="font-size: 15px;">Synopsis / কাহিনী সংক্ষেপ:</h6>
                    <p class="text-muted small mb-4" style="line-height:1.6;">{{movie.movie_data.plot}}</p>

                    <h6 class="text-warning font-weight-bold mb-3" style="font-size:15px; letter-spacing:0.5px;">📥 DOWNLOAD LINKS:</h6>
                    
                    {% if movie.dl_links.get('480p') %}
                    <button class="download-btn" onclick="startDownloadTimer('{{movie.dl_links.get('480p')}}', '480p')">
                        🚀 Download 480p (Standard)
                    </button>
                    {% endif %}
                    
                    {% if movie.dl_links.get('720p') %}
                    <button class="download-btn" onclick="startDownloadTimer('{{movie.dl_links.get('720p')}}', '720p')">
                        ⚡ Download 720p (HD Quality)
                    </button>
                    {% endif %}
                    
                    {% if movie.dl_links.get('1080p') %}
                    <button class="download-btn" onclick="startDownloadTimer('{{movie.dl_links.get('1080p')}}', '1080p')">
                        🔥 Download 1080p (Full Ultra HD)
                    </button>
                    {% endif %}
                </div>
            </div>
            
            {% if movie.movie_data.screenshots %}
            <div class="row mt-5">
                 <h6 class="text-white font-weight-bold mb-3">📸 Screen Captures:</h6>
                 {% for s in movie.movie_data.screenshots %}
                 <div class="col-6 col-md-3 mb-3">
                      <img src="{{s}}" class="img-fluid rounded border border-secondary" style="object-fit: cover; width:100%; height:120px;" alt="Screenshot">
                 </div>
                 {% endfor %}
            </div>
            {% endif %}
        </div>
    </div>

    <!-- গ্লোয়িং এনিমেটেড মডাল উইজেট -->
    <div id="timerOverlay" class="timer-overlay">
        <div class="text-center" id="overlayHeader">
            <h5 class="text-white font-weight-bold mb-1">Generating Download Link...</h5>
            <p class="text-muted small">অনুগ্ৰহ করে কয়েক সেকেন্ড অপেক্ষা করুন</p>
        </div>
        
        <div class="timer-wrapper my-4" id="timerCircleBox">
            <svg class="timer-svg" viewBox="0 0 100 100">
                <circle class="timer-bg" cx="50" cy="50" r="45"></circle>
                <circle class="timer-bar" cx="50" cy="50" r="45" id="timerBar"></circle>
            </svg>
            <div class="timer-text" id="timerText">{{settings.download_timer}}</div>
        </div>

        <a href="" id="finalDownloadBtn" class="unlocked-btn">⚡ Get File (টেলিগ্রামে ডাউনলোড করুন)</a>
    </div>

    <script>
        const timerDuration = parseInt('{{settings.download_timer}}');
        const shortlinks = {{settings.direct_links | tojson}};
        const botUsername = '{{bot_username}}';

        function startDownloadTimer(fileKey, quality) {
            let overlay = document.getElementById('timerOverlay');
            let timerBar = document.getElementById('timerBar');
            let timerText = document.getElementById('timerText');
            let finalBtn = document.getElementById('finalDownloadBtn');
            let circleBox = document.getElementById('timerCircleBox');
            let header = document.getElementById('overlayHeader');

            overlay.classList.add('active');
            circleBox.style.display = 'block';
            header.style.display = 'block';
            finalBtn.style.display = 'none';
            timerText.innerText = timerDuration;
            timerBar.style.strokeDashoffset = 0;

            const totalDash = 283; 
            let timeLeft = timerDuration;

            let interval = setInterval(() => {
                timeLeft--;
                timerText.innerText = timeLeft;
                let offset = totalDash - (timeLeft / timerDuration) * totalDash;
                timerBar.style.strokeDashoffset = offset;

                if (timeLeft <= 0) {
                    clearInterval(interval);
                    circleBox.style.display = 'none';
                    header.style.display = 'none';
                    
                    let tgLink = `https://t.me/${botUsername}?start=${fileKey}`;
                    
                    finalBtn.href = tgLink;
                    finalBtn.style.display = 'block';
                    
                    finalBtn.onclick = function(e) {
                        if (shortlinks.length > 0) {
                            let randomLink = shortlinks[Math.floor(Math.random() * shortlinks.length)];
                            window.open(randomLink, '_blank');
                        }
                    };
                }
            }, 1000);
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
