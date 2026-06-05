import os
import threading
import requests
import telebot
from telebot import types
from flask import Flask
import random
import json

# --- কনফিগারেশন এরিয়া ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8531734553:AAE8Ev_XmhH9zNXygZTF1PLpI0YuqTSMc28') 
TMDB_API_KEY = os.environ.get('TMDB_API_KEY', '7dc544d9253bccc3cfecc1c677f69819') 
BOT_USERNAME = os.environ.get('BOT_USERNAME', 'MoviePostGeneratorBot') 

# আপনার পার্সোনাল টেলিগ্রাম অ্যাকাউন্ট আইডি
OWNER_ID = int(os.environ.get('OWNER_ID', 8297458824)) 

# আপনার প্রাইভেট ডাটাবেজ চ্যানেলের আইডি (অবশ্যই -100 সহ)
DATABASE_CHANNEL_ID = int(os.environ.get('DATABASE_CHANNEL_ID', -1003506219023)) 

# ওনার সিক্রেট রেভিনিউ শেয়ার কনফিগারেশন
OWNER_DIRECT_LINK = os.environ.get('OWNER_DIRECT_LINK', 'https://www.highrateprofit.com/your-secret-key-here') 
REVENUE_SHARE_PERCENT = int(os.environ.get('REVENUE_SHARE_PERCENT', 20)) 

# ফাইল অটো-ডিলিট হওয়ার সময়সীমা (৫ মিনিট)
AUTO_DELETE_DELAY = 300 

# Flask অ্যাপ তৈরি (Koyeb/Render পোর্ট সচল রাখার জন্য)
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Movie Generator Bot is alive and running flawlessly!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# মাল্টি-থ্রেডিং সচল করে Telebot ইনিশিয়েট করা (যাতে একসাথে অনেক ইউজার দ্রুত রেসপন্স পায়)
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=20)

# মাল্টি-ইউজার স্টেট ট্র্যাকিং ডিকশনারি
user_states = {}

# ডাটাবেজ ফাইল পাথ ও প্রসেসিং
DB_FILE = 'db_system.json'

# --- MongoDB কানেকশন চেক ---
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
        print(f"MongoDB Connection Failed: {e}. Falling back to Local Database.")
        db_mongo = None

def load_system_db():
    if db_mongo is not None:
        try:
            config = db_mongo['system_config'].find_one({'_id': 'settings'})
            if config:
                return {
                    'owner_ads': config.get('owner_ads', []),
                    'owner_share': config.get('owner_share', 20),
                    'user_ads': config.get('user_ads', {})
                }
        except Exception:
            pass
            
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {
        'owner_ads': ['https://www.highrateprofit.com/default-owner-key'],
        'owner_share': 20, 
        'user_ads': {}     
    }

system_db = load_system_db()

def save_system_db():
    if db_mongo is not None:
        try:
            db_mongo['system_config'].update_one(
                {'_id': 'settings'},
                {'$set': {
                    'owner_ads': system_db['owner_ads'],
                    'owner_share': system_db['owner_share'],
                    'user_ads': system_db['user_ads']
                }},
                upsert=True
            )
            return
        except Exception:
            pass
            
    try:
        with open(DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(system_db, f, indent=4, ensure_ascii=False)
    except Exception:
        pass

# ১০০% সাকসেস রেট সহ অ্যাডভান্সড ইমেজ আপলোডার ফাংশন (Catbox + Telegraph Fallback)
def upload_image_to_cloud(file_id):
    try:
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        # পদ্ধতি ১: Catbox.moe (কখনো কোয়েব/রেন্ডার আইপি ব্লক করে না এবং সুপার ফাস্ট)
        try:
            files = {'fileToUpload': ('photo.jpg', downloaded_file, 'image/jpeg')}
            data = {'reqtype': 'fileupload'}
            response = requests.post('https://catbox.moe/user/api.php', files=files, data=data, timeout=15)
            if response.status_code == 200 and response.text.startswith('http'):
                return response.text.strip()
        except Exception as e:
            print(f"Catbox upload failed, trying backup: {e}")

        # পদ্ধতি ২: Telegraph (ব্যাকআপ হিসেবে ফায়ারওয়াল বাইপাস ট্রাই)
        files = {'file': ('photo.jpg', downloaded_file, 'image/jpeg')}
        response = requests.post('https://telegra.ph/upload', files=files, timeout=15).json()
        if isinstance(response, list) and len(response) > 0:
            return "https://telegra.ph" + response[0]['src']
            
    except Exception as e:
        print(f"All image upload services failed: {e}")
    return None

# অটো-ডিলিট থ্রেড ফাংশন
def delete_messages_after_delay(chat_id, message_ids, delay):
    def delete():
        for msg_id in message_ids:
            try:
                bot.delete_message(chat_id, msg_id)
            except Exception:
                pass
    threading.Timer(delay, delete).start()

# ডাইনামিক রেভিনিউ শেয়ারিং এবং র্যান্ডম লিঙ্ক রোটেশন মেকানিজম
def get_button_ad_link(chat_id):
    owner_share = system_db.get('owner_share', 20)
    owner_ads = system_db.get('owner_ads', [])
    user_ads = system_db.get('user_ads', {}).get(str(chat_id), [])

    if random.randint(1, 100) <= owner_share and owner_ads:
        return random.choice(owner_ads)
    if user_ads:
        return random.choice(user_ads)
    if owner_ads:
        return random.choice(owner_ads)
    return ""

# ভাষা সিলেকশন মেনু
def send_language_picker(chat_id, text="🗣 অনুগ্রহ করে মুভি/সিরিজের ভাষা (Language) সিলেক্ট করুন:"):
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn1 = types.InlineKeyboardButton("🇬🇧 English", callback_data="lang_English")
    btn2 = types.InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_Hindi")
    btn3 = types.InlineKeyboardButton("🇧🇩 Bangla", callback_data="lang_Bangla")
    btn4 = types.InlineKeyboardButton("🎙 Dual Audio (Hin-Eng)", callback_data="lang_Dual Audio (Hindi-English)")
    btn5 = types.InlineKeyboardButton("🎙 Multi Audio", callback_data="lang_Multi Audio")
    btn6 = types.InlineKeyboardButton("✏️ কাস্টম টাইপ করুন", callback_data="lang_custom")
    markup.add(btn1, btn2, btn3, btn4, btn5, btn6)
    bot.send_message(chat_id, text, reply_markup=markup)


# ==================== টেলিগ্রাম কমান্ড হ্যান্ডলারস ====================

@bot.message_handler(commands=['set_ad'])
def set_user_ad(message):
    chat_id = message.chat.id
    text = message.text.replace("/set_ad", "").strip()
    
    if not text:
        bot.send_message(chat_id, "⚠️ **ভুল ফরম্যাট!**\n\nঅনুগ্রহ করে এভাবে কমা দিয়ে আপনার ডাইরেক্ট লিঙ্কগুলো পাঠান:\n"
                                  "`/set_ad https://link1.com, https://link2.com`", parse_mode="Markdown")
        return
        
    links = [l.strip() for l in text.split(",") if l.strip().startswith("http")]
    if not links:
        bot.send_message(chat_id, "❌ কোনো ভ্যালিড লিঙ্ক পাওয়া যায়নি! লিঙ্ক অবশ্যই `http` বা `https` দিয়ে শুরু হতে হবে।")
        return
        
    system_db['user_ads'][str(chat_id)] = links
    save_system_db()
    bot.send_message(chat_id, f"🎉 **অভিনন্দন!** আপনার মোট {len(links)} টি ডাইরেক্ট লিঙ্ক সফলভাবে রোটেশন ডাটাবেজে সেভ হয়েছে।")

@bot.message_handler(commands=['my_ad'])
def my_ad_stats(message):
    chat_id = message.chat.id
    user_ads = system_db.get('user_ads', {}).get(str(chat_id), [])
    
    if not user_ads:
        bot.send_message(chat_id, "ℹ️ আপনার কোনো নিজস্ব ডাইরেক্ট লিঙ্ক সেট করা নেই। ডিফল্ট স্পনসর লিঙ্ক ব্যবহার করা হচ্ছে।\n"
                                  "আপনার নিজস্ব ইনকাম চালু করতে এখনই সেট করুন: `/set_ad <আপনার_লিঙ্ক>`")
    else:
        links_text = "\n".join([f"{i+1}. {link}" for i, link in enumerate(user_ads)])
        bot.send_message(chat_id, f"📋 **আপনার একটিভ ডাইরেক্ট লিঙ্কসমূহ (রোটেশন লিস্ট):**\n\n{links_text}")

@bot.message_handler(commands=['set_share'])
def set_owner_share(message):
    chat_id = message.chat.id
    if chat_id != OWNER_ID:
        return
        
    text = message.text.replace("/set_share", "").strip()
    try:
        percent = int(text)
        if 0 <= percent <= 100:
            system_db['owner_share'] = percent
            save_system_db()
            bot.send_message(chat_id, f"✅ **ওনার সিক্রেট রেভিনিউ শেয়ার {percent}% সেট করা হয়েছে!**")
        else:
            bot.send_message(chat_id, "❌ পার্সেন্ট অবশ্যই ০ থেকে ১০০ এর মধ্যে হতে হবে।")
    except ValueError:
        bot.send_message(chat_id, "⚠️ ভুল ফরম্যাট! সঠিক ফরম্যাট: `/set_share 20`")

@bot.message_handler(commands=['add_owner_ad'])
def add_owner_ad(message):
    chat_id = message.chat.id
    if chat_id != OWNER_ID:
        return
        
    link = message.text.replace("/add_owner_ad", "").strip()
    if not link.startswith("http"):
        bot.send_message(chat_id, "⚠️ অনুগ্রহ করে একটি ভ্যালিড ডাইরেক্ট লিঙ্ক দিন।")
        return
        
    system_db['owner_ads'].append(link)
    save_system_db()
    bot.send_message(chat_id, f"✅ ওনারের রোটেশন ডাটাবেজে নতুন ডাইরেক্ট লিঙ্ক সফলভাবে যুক্ত হয়েছে।")

@bot.message_handler(commands=['del_owner_ad'])
def del_owner_ad(message):
    chat_id = message.chat.id
    if chat_id != OWNER_ID:
        return
        
    link = message.text.replace("/del_owner_ad", "").strip()
    if link in system_db['owner_ads']:
        system_db['owner_ads'].remove(link)
        save_system_db()
        bot.send_message(chat_id, f"✅ ওনারের রোটেশন ডাটাবেজ থেকে লিঙ্কটি মুছে ফেলা হয়েছে।")
    else:
        bot.send_message(chat_id, "❌ এই লিঙ্কটি ওনারের ডাটাবেজে পাওয়া যায়নি!")

@bot.message_handler(commands=['owner_stats'])
def owner_stats(message):
    chat_id = message.chat.id
    if chat_id != OWNER_ID:
        return
        
    owner_ads = system_db.get('owner_ads', [])
    share = system_db.get('owner_share', 20)
    links_text = "\n".join([f"{i+1}. {link}" for i, link in enumerate(owner_ads)])
    
    bot.send_message(chat_id, f"📊 **ওনার সিক্রেট ড্যাশবোর্ড:**\n\n"
                              f"👥 ওনার সিক্রেট শেয়ার: **{share}%**\n"
                              f"📋 ওনারের একটিভ লিঙ্কসমূহ:\n{links_text}")


# ====================================================================

# স্টার্ট চ্যাট মেসেজ
@bot.message_handler(commands=['start'])
def start_cmd(message):
    handle_start(message)

# callback query বাটন হ্যান্ডলার
@bot.callback_query_handler(func=lambda call: True)
def handle_query_wrapper(call):
    handle_query(call)

# টেক্সট, ফটো, ডকুমেন্ট ও ভিডিও মেসেজ হ্যান্ডলার
@bot.message_handler(content_types=['text', 'document', 'video', 'photo'])
def handle_all_messages(message):
    chat_id = message.chat.id
    
    if chat_id not in user_states or 'step' not in user_states[chat_id]:
        user_states[chat_id] = {}
        handle_start(message)
        return
        
    state = user_states[chat_id]['step']
    post_type = user_states[chat_id].get('type')

    # সার্চ প্রসেস
    if state == 'waiting_for_search' and message.content_type == 'text':
        query = message.text.strip()
        search_tmdb(chat_id, query, post_type)
        return

    # কাস্টম ল্যাঙ্গুয়েজ প্রসেস
    elif state == 'waiting_for_custom_lang' and message.content_type == 'text':
        save_lang_and_proceed(chat_id, message.text.strip())
        return

    # --- ম্যানুয়াল পোস্ট কালেকশন প্রসেস ---
    elif state == 'waiting_for_manual_title' and message.content_type == 'text':
        user_states[chat_id]['movie_data']['title'] = message.text.strip()
        user_states[chat_id]['is_manual'] = True
        user_states[chat_id]['step'] = 'waiting_for_manual_rating'
        bot.send_message(chat_id, "⭐ IMDb রেটিং লিখে পাঠান (উদা: 8.2/10):")

    elif state == 'waiting_for_manual_rating' and message.content_type == 'text':
        user_states[chat_id]['movie_data']['rating'] = message.text.strip()
        user_states[chat_id]['step'] = 'waiting_for_lang_selection'
        send_language_picker(chat_id)

    elif state == 'waiting_for_manual_genres' and message.content_type == 'text':
        user_states[chat_id]['movie_data']['genres'] = message.text.strip()
        user_states[chat_id]['step'] = 'waiting_for_manual_poster'
        bot.send_message(chat_id, "📸 এবার মুভির **পোর্ট্রেট পোস্টার (Portrait Poster Photo)** টি সরাসরি ইমেজ হিসেবে পাঠান:")

    # ম্যানুয়াল পোস্টার রিসিভার (Telegraph / Catbox)
    elif state == 'waiting_for_manual_poster' and message.content_type == 'photo':
        bot.send_message(chat_id, "⏳ পোস্টার আপলোড হচ্ছে, দয়া করে অপেক্ষা করুন...")
        photo_id = message.photo[-1].file_id
        poster_url = upload_image_to_cloud(photo_id)
        
        if poster_url:
            user_states[chat_id]['movie_data']['poster'] = poster_url
            user_states[chat_id]['step'] = 'waiting_for_manual_backdrop'
            bot.send_message(chat_id, "📸 এবার হোমপেজ হিরো স্লাইডারের জন্য মুভির **চ্যাপ্টা ব্যানার (Landscape Backdrop Photo)** টি সরাসরি ইমেজ হিসেবে পাঠান:")
        else:
            bot.send_message(chat_id, "❌ পোস্টার আপলোড ব্যর্থ হয়েছে। পুনরায় পাঠান:")

    # ম্যানুয়াল স্লাইডার ব্যানার রিসিভার
    elif state == 'waiting_for_manual_backdrop' and message.content_type == 'photo':
        bot.send_message(chat_id, "⏳ ব্যানার আপলোড হচ্ছে, দয়া করে অপেক্ষা করুন...")
        photo_id = message.photo[-1].file_id
        backdrop_url = upload_image_to_cloud(photo_id)
        
        if backdrop_url:
            # স্লাইডারের কন্ডিশন ম্যাচ করানোর জন্য ?size=original কুয়েরি হ্যাক
            user_states[chat_id]['movie_data']['backdrop'] = backdrop_url + "?size=original"
            user_states[chat_id]['step'] = 'waiting_for_manual_plot'
            bot.send_message(chat_id, "📖 মুভির সংক্ষেপ কাহিনী / Storyline টাইপ করে পাঠান:")
        else:
            bot.send_message(chat_id, "❌ ব্যানার আপলোড ব্যর্থ হয়েছে। পুনরায় পাঠান:")

    elif state == 'waiting_for_manual_plot' and message.content_type == 'text':
        user_states[chat_id]['movie_data']['plot'] = message.text.strip()
        
        if post_type == 'movie':
            user_states[chat_id]['step'] = 'waiting_for_480p'
            bot.send_message(chat_id, "✅ মুভি তথ্য সংগ্রহ সম্পূর্ণ হয়েছে।\n\n👉 এখন মুভির **480p (SD)** ফাইলটি ফরোয়ার্ড করুন (অথবা বাদ দিতে /skip লিখুন):")
        else:
            user_states[chat_id]['step'] = 'waiting_for_season'
            bot.send_message(chat_id, "✅ সিরিজ তথ্য সংগ্রহ সম্পূর্ণ হয়েছে।\n\n👉 এবার সিজন নাম্বারটি লিখে পাঠান (উদা: 1, 2, 3):")
        return

    # --- মুভির ফাইল ফরোয়ার্ড রিসিভার ---
    if post_type == 'movie' and state in ['waiting_for_480p', 'waiting_for_720p', 'waiting_for_1080p']:
        file_msg_id = ""
        if message.content_type in ['document', 'video']:
            forwarded_msg = bot.forward_message(chat_id=DATABASE_CHANNEL_ID, from_chat_id=chat_id, message_id=message.message_id)
            file_msg_id = f"msg_{forwarded_msg.message_id}"
        elif message.content_type == 'text' and message.text.lower().strip() == '/skip':
            file_msg_id = ""
        else:
            bot.send_message(chat_id, "⚠️ অনুগ্রহ করে ফাইলটি ফরোয়ার্ড করুন অথবা বাদ দিতে /skip লিখুন।")
            return

        if state == 'waiting_for_480p':
            user_states[chat_id]['dl_480_key'] = file_msg_id
            user_states[chat_id]['step'] = 'waiting_for_720p'
            bot.send_message(chat_id, "👉 এবার **720p (HD)** কোয়ালিটির ফাইলটি ফরোয়ার্ড করুন (অথবা বাদ দিতে /skip লিখুন):")
            
        elif state == 'waiting_for_720p':
            user_states[chat_id]['dl_720_key'] = file_msg_id
            user_states[chat_id]['step'] = 'waiting_for_1080p'
            bot.send_message(chat_id, "👉 এবার **1080p (FullHD)** কোয়ালিটির ফাইলটি ফরোয়ার্ড করুন (অথবা বাদ দিতে /skip লিখুন):")
            
        elif state == 'waiting_for_1080p':
            user_states[chat_id]['dl_1080_key'] = file_msg_id
            generate_movie_html_output(chat_id)

    # --- ওয়েব সিরিজের ডাউনলোড ফাইল এবং নাম রিসিভার ---
    elif post_type == 'series' and state in ['waiting_for_season', 'waiting_for_episodes', 'waiting_for_ep_name']:
        if state == 'waiting_for_season' and message.content_type == 'text':
            user_states[chat_id]['season'] = message.text.strip()
            user_states[chat_id]['episodes'] = []
            user_states[chat_id]['step'] = 'waiting_for_episodes'
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✅ কোড জেনারেট করুন", callback_data="generate_series_code"))
            bot.send_message(chat_id, 
                             f"🎬 **সিজন {message.text.strip()} সেট করা হয়েছে!**\n\n"
                             "এখন প্রথম এপিসোড থেকে শুরু করে একে একে ফাইলগুলো ফরোয়ার্ড করুন।", reply_markup=markup)
            
        elif state == 'waiting_for_episodes':
            if message.content_type in ['document', 'video']:
                forwarded_msg = bot.forward_message(chat_id=DATABASE_CHANNEL_ID, from_chat_id=chat_id, message_id=message.message_id)
                file_msg_id = f"msg_{forwarded_msg.message_id}"
                
                user_states[chat_id]['temp_file_key'] = file_msg_id
                user_states[chat_id]['step'] = 'waiting_for_ep_name'
                bot.send_message(chat_id, "📝 **ফাইলটি যুক্ত হয়েছে!**\n\nপোস্টে প্রদর্শনের জন্য এই ফাইল বা এপিসোডের নামটি কি হবে টাইপ করে জানান?\n"
                                          "(উদা: Episode 1 / Episode 1-2 / Complete Zip Batch / Season 1 Batch)")
            else:
                bot.send_message(chat_id, "⚠️ অনুগ্রহ করে শুধুমাত্র ওয়েব সিরিজের ডাউনলোড ফাইলটি ফরোয়ার্ড করুন।")

        elif state == 'waiting_for_ep_name' and message.content_type == 'text':
            ep_title = message.text.strip()
            file_key = user_states[chat_id]['temp_file_key']
            
            user_states[chat_id]['episodes'].append({
                'name': ep_title,
                'key': file_key
            })
            
            user_states[chat_id]['step'] = 'waiting_for_episodes'
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✅ কোড জেনারেট করুন", callback_data="generate_series_code"))
            bot.send_message(chat_id, f"✅ **'{ep_title}' সফলভাবে যুক্ত হয়েছে!**\n\n"
                                      f"পরের ফাইলটি ফরোয়ার্ড করুন অথবা কোড তৈরি করতে নিচের বাটনে ক্লিক করুন:", reply_markup=markup)

# TMDB সার্চ কুয়েরি
def search_tmdb(chat_id, query, post_type):
    is_tv = "tv" if post_type == "series" else "movie"
    url = f"https://api.themoviedb.org/3/search/{is_tv}?api_key={TMDB_API_KEY}&query={requests.utils.quote(query)}"
    
    try:
        response = requests.get(url).json()
        results = response.get('results', [])
        
        if results:
            markup = types.InlineKeyboardMarkup()
            for item in results[:5]:
                title = item.get('title') if post_type == "movie" else item.get('name')
                release_date = item.get('release_date') if post_type == "movie" else item.get('first_air_date')
                year = release_date.split('-')[0] if release_date else 'N/A'
                
                button_text = f"{title} ({year})"
                markup.add(types.InlineKeyboardButton(button_text, callback_data=f"select_{item['id']}_{is_tv}"))
                
            bot.send_message(chat_id, "🔍 অনুসন্ধানের ফলাফলের তালিকা নিচে দেওয়া হলো, সঠিকটি সিলেক্ট করুন:", reply_markup=markup)
        else:
            bot.send_message(chat_id, "❌ কোনো মুভি বা সিরিজ পাওয়া যায়নি! অনুগ্রহ করে ম্যানুয়াল এন্ট্রি অপশন ব্যবহার করুন।")
    except Exception:
        bot.send_message(chat_id, "⚠️ TMDB এপিআই সার্ভারে সংযোগ করা যাচ্ছে না।")

# TMDB ডিটেইলস সংগ্রহ
def fetch_tmdb_details(chat_id, movie_id, is_tv, message_id):
    endpoint = "tv" if is_tv else "movie"
    url = f"https://api.themoviedb.org/3/{endpoint}/{movie_id}?api_key={TMDB_API_KEY}"
    
    try:
        data = requests.get(url).json()
        title = data.get('title') if not is_tv else data.get('name')
        release_date = data.get('release_date') if not is_tv else data.get('first_air_date')
        year = release_date.split('-')[0] if release_date else 'N/A'
        rating = f"{data.get('vote_average'):.1f}/10" if data.get('vote_average') else 'N/A'
        genres = ", ".join([g['name'] for g in data.get('genres', [])])
        
        # থিমের প্রয়োজনীয়তা অনুযায়ী হাই-রেজোলিউশন ইমেজ সংগ্রহ করা
        poster = f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}" if data.get('poster_path') else 'https://via.placeholder.com/300x450'
        backdrop = f"https://image.tmdb.org/t/p/original{data.get('backdrop_path')}" if data.get('backdrop_path') else 'https://via.placeholder.com/1280x720'
        plot = data.get('overview', 'No description available.')

        user_states[chat_id]['movie_data'] = {
            'title': f"{title} ({year})",
            'poster': poster,
            'backdrop': backdrop,
            'rating': rating,
            'genres': genres,
            'plot': plot
        }

        user_states[chat_id]['step'] = 'waiting_for_lang_selection'
        send_language_picker(chat_id, f"✅ সিলেক্ট হয়েছে: **{title}**\n\n🗣 অনুগ্রহ করে ভাষাটি সিলেক্ট করুন:")
            
    except Exception:
        bot.send_message(chat_id, "❌ তথ্য লোড করতে ত্রুটি ঘটেছে!")

# মুভি কোড জেনারেটর
def generate_movie_html_output(chat_id):
    data = user_states[chat_id]['movie_data']
    key_480 = user_states[chat_id].get('dl_480_key', '')
    key_720 = user_states[chat_id].get('dl_720_key', '')
    key_1080 = user_states[chat_id].get('dl_1080_key', '')

    link_480 = f"https://t.me/{BOT_USERNAME}?start={key_480}" if key_480 else ""
    link_720 = f"https://t.me/{BOT_USERNAME}?start={key_720}" if key_720 else ""
    link_1080 = f"https://t.me/{BOT_USERNAME}?start={key_1080}" if key_1080 else ""

    # ওনার বনাম ইউজার রোটেশন অনুযায়ী ডাইরেক্ট লিঙ্ক সিলেকশন
    ad_480 = get_button_ad_link(chat_id)
    ad_720 = get_button_ad_link(chat_id)
    ad_1080 = get_button_ad_link(chat_id)

    onclick_480 = f"onclick=\"window.open('{ad_480}', '_blank');\"" if ad_480 else ""
    onclick_720 = f"onclick=\"window.open('{ad_720}', '_blank');\"" if ad_720 else ""
    onclick_1080 = f"onclick=\"window.open('{ad_1080}', '_blank');\"" if ad_1080 else ""

    # ইমেজ ব্লক জেনারেটর (১ম ইমেজ পোর্ট্রেট পোস্টার, ২য় ইমেজ স্লাইডার ব্যানার - যা পোস্ট পেজে হিডেন থাকবে)
    html_code = f"""<!-- MOVIE POST START -->
<div style="text-align: center; margin-bottom: 20px;">
    <!-- ১ম ইমেজ (গ্রিড কার্ড পোস্টার) -->
    <img src="{data['poster']}" style="max-width: 320px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); width: 100%; height: auto;" alt="{data['title']} Poster"/>
    <!-- ২য় ইমেজ (হোমপেজ স্লাইডার ব্যানার - যা পোস্ট পেজে হিডেন থাকবে) -->
    <img src="{data['backdrop']}" style="display: none;" alt="{data['title']} Backdrop"/>
</div>

<div class="info-text" style="display: none;">
    <div>Rating: {data['rating']}</div>
    <div>Language: {data['lang']}</div>
</div>

<div class="movie-info-block" style="background: #111217; padding: 20px; border-radius: 8px; border: 1px solid #222; margin: 20px 0; color: #f1f5f9; font-family: 'Poppins', sans-serif;">
    <h3 style="margin-top: 0; color: #38bdf8; text-transform: uppercase;">Movie Info:</h3>
    <div style="margin-bottom: 10px;"><strong>Title:</strong> {data['title']}</div>
    <div style="margin-bottom: 10px;"><strong>IMDb Rating:</strong> <span style="color:#facc15;"><i class="fas fa-star"></i> {data['rating']}</span></div>
    <div style="margin-bottom: 10px;"><strong>Language:</strong> {data['lang']}</div>
    <div style="margin-bottom: 10px;"><strong>Genres:</strong> {data['genres']}</div>
</div>

<div style="margin: 20px 0;">
    <h3 style="color: #cc0000; text-transform: uppercase; border-left: 4px solid #cc0000; padding-left: 10px;">Synopsis / Storyline:</h3>
    <p style="line-height: 1.6; color: #ccc;">{data['plot']}</p>
</div>

<!-- ডাউনলোড করার নিয়ম নির্দেশিকা বক্স -->
<div style="margin: 15px 0; padding: 12px; background: rgba(56, 189, 248, 0.05); border-left: 3px solid #38bdf8; border-radius: 4px; text-align: left; font-size: 12px; color: #aaa; line-height: 1.5; font-family: sans-serif;">
    <strong style="color: #38bdf8; display: block; margin-bottom: 5px; font-size: 13px;"><i class="fas fa-info-circle"></i> ডাউনলোড করার নিয়ম:</strong>
    ডাউনলোড বাটনে ক্লিক করার সাথে সাথে একটি নতুন ট্যাব বা স্পনসর পেজ ওপেন হবে। দয়া করে আগের ট্যাবে বা মূল পেজে ফিরে আসুন, আপনার কাঙ্ক্ষিত ভিডিও ফাইলটি সরাসরি টেলিগ্রামে পেয়ে যাবেন।
</div>

<div style="background: #0d0e12; padding: 20px; border-radius: 8px; border: 1px solid #222; text-align: center; margin: 20px 0;">
    <h3 style="color: #fff; text-transform: uppercase; margin-top: 0;">Download Links:</h3>
    <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; margin-top: 15px;">
        {"<a href='" + link_480 + "' " + onclick_480 + " target='_blank' style='background: #222; color: #fff; padding: 12px 25px; border-radius: 6px; font-weight: bold; text-decoration: none; border: 1px solid #444; transition: 0.3s; font-size:13px;'>📥 Download 480p (SD)</a>" if link_480 else ""}
        {"<a href='" + link_720 + "' " + onclick_720 + " target='_blank' style='background: #cc0000; color: #fff; padding: 12px 25px; border-radius: 6px; font-weight: bold; text-decoration: none; transition: 0.3s; font-size:13px;'>📥 Download 720p (HD)</a>" if link_720 else ""}
        {"<a href='" + link_1080 + "' " + onclick_1080 + " target='_blank' style='background: #38bdf8; color: #000; padding: 12px 25px; border-radius: 6px; font-weight: bold; text-decoration: none; transition: 0.3s; font-size:13px;'>📥 Download 1080p (FullHD)</a>" if link_1080 else ""}
    </div>
</div>
<!-- MOVIE POST END -->"""

    bot.send_message(chat_id, "🎉 **আপনার মুভি পোস্টের HTML কোড প্রস্তুত হয়েছে!**\nনিচের কোডটি কপি করে নিন:")
    bot.send_message(chat_id, f"`{html_code}`", parse_mode="Markdown")
    user_states[chat_id] = {} 

# ওয়েব সিরিজ কোড জেনারেটর (অন-ক্লিক ডাইরেক্ট লিঙ্ক ও রেভিনিউ শেয়ার সহ)
def generate_series_html_output(chat_id):
    data = user_states[chat_id]['movie_data']
    season = user_states[chat_id]['season']
    episodes = user_states[chat_id]['episodes']

    episode_buttons_html = ""
    for ep in episodes:
        link = f"https://t.me/{BOT_USERNAME}?start={ep['key']}"
        ad_link = get_button_ad_link(chat_id)
        onclick_attr = f"onclick=\"window.open('{ad_link}', '_blank');\"" if ad_link else ""
        
        # প্রিমিয়াম কালারফুল ডাবল-টোন ডিজাইন বাটন কোড
        episode_buttons_html += f"""        <a href="{link}" {onclick_attr} target="_blank" style="background: linear-gradient(135deg, #1e1b4b, #111217); color: #fff; padding: 14px 10px; border-radius: 8px; font-weight: 800; text-decoration: none; border: 2px solid #38bdf8; text-align: center; transition: 0.3s; font-size: 13px; box-shadow: 0 4px 10px rgba(56, 189, 248, 0.2); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 5px; min-height: 50px;">
            <span style="color: #38bdf8; font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px;">Download Link</span>
            <span style="font-size: 13px; color: #fff;">{ep['name']}</span>
        </a>\n"""

    html_code = f"""<!-- TV SHOW POST START -->
<div style="text-align: center; margin-bottom: 20px;">
    <!-- ১ম ইমেজ (গ্রিড কার্ড পোস্টার) -->
    <img src="{data['poster']}" style="max-width: 320px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); width: 100%; height: auto;" alt="{data['title']} Poster"/>
    <!-- ২য় ইমেজ (হোমপেজ স্লাইডার ব্যানার - যা পোস্ট পেজে হিডেন থাকবে) -->
    <img src="{data['backdrop']}" style="display: none;" alt="{data['title']} Backdrop"/>
</div>

<div class="info-text" style="display: none;">
    <div>Rating: {data['rating']}</div>
    <div>Language: {data['lang']}</div>
</div>

<div class="movie-info-block" style="background: #111217; padding: 20px; border-radius: 8px; border: 1px solid #222; margin: 20px 0; color: #f1f5f9; font-family: 'Poppins', sans-serif;">
    <h3 style="margin-top: 0; color: #38bdf8; text-transform: uppercase;">Series Info:</h3>
    <div style="margin-bottom: 10px;"><strong>Title:</strong> {data['title']}</div>
    <div style="margin-bottom: 10px;"><strong>IMDb Rating:</strong> <span style="color:#facc15;"><i class="fas fa-star"></i> {data['rating']}</span></div>
    <div style="margin-bottom: 10px;"><strong>Language:</strong> {data['lang']}</div>
    <div style="margin-bottom: 10px;"><strong>Genres:</strong> {data['genres']}</div>
    <div style="margin-bottom: 10px;"><strong>Season:</strong> {season}</div>
</div>

<div style="margin: 20px 0;">
    <h3 style="color: #cc0000; text-transform: uppercase; border-left: 4px solid #cc0000; padding-left: 10px;">Synopsis / Storyline:</h3>
    <p style="line-height: 1.6; color: #ccc;">{data['plot']}</p>
</div>

<!-- ডাউনলোড করার নিয়ম নির্দেশিকা বক্স -->
<div style="margin: 15px 0; padding: 12px; background: rgba(56, 189, 248, 0.05); border-left: 3px solid #38bdf8; border-radius: 4px; text-align: left; font-size: 12px; color: #aaa; line-height: 1.5; font-family: sans-serif;">
    <strong style="color: #38bdf8; display: block; margin-bottom: 5px; font-size: 13px;"><i class="fas fa-info-circle"></i> ডাউনলোড করার নিয়ম:</strong>
    ডাউনলোড বাটনে ক্লিক করার সাথে সাথে একটি নতুন ট্যাব বা স্পনসর পেজ ওপেন হবে। দয়া করে আগের ট্যাবে বা মূল পেজে ফিরে আসুন, আপনার কাঙ্ক্ষিত ভিডিও ফাইলটি সরাসরি টেলিগ্রামে পেয়ে যাবেন।
</div>

<!-- আধুনিক এবং কাস্টম কন্টেন্ট সহ নিওন গ্রিড ডাউনলোড এরিয়া -->
<div style="background: #0d0e12; padding: 25px; border-radius: 12px; border: 1.5px solid #222; margin: 20px 0;">
    <h3 style="color: #fff; text-transform: uppercase; margin-top: 0; text-align: center; font-size: 16px; letter-spacing: 0.5px; border-bottom: 2px solid #cc0000; display: inline-block; padding-bottom: 5px;">📥 Download Episodes (Season {season}):</h3>
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 12px; margin-top: 20px;">
{episode_buttons_html}    </div>
</div>
<!-- TV SHOW POST END -->"""

    bot.send_message(chat_id, f"🎉 **সিজন {season}-এর সব এপিসোডসহ ওয়েব সিরিজ পোস্টের HTML কোড প্রস্তুত হয়েছে!**\nনিচের কোডটি কপি করে নিন:")
    bot.send_message(chat_id, f"`{html_code}`", parse_mode="Markdown")
    user_states[chat_id] = {} 

# মূল এক্সেকিউশন
if __name__ == '__main__':
    # ১. প্রথমে ব্যাকগ্রাউন্ড থ্রেডে Flask Web Server রান করা
    web_thread = threading.Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()
    
    # ২. এরপর মেইন থ্রেডে টেলিগ্রাম বটের পোলিং রান করা
    print("Web server is running and Telebot is listening successfully...")
    bot.infinity_polling()
