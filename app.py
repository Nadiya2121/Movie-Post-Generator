import os
import threading
import requests
import telebot
from telebot import types
from flask import Flask

# --- কনফিগারেশন এরিয়া ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8531734553:AAE8Ev_XmhH9zNXygZTF1PLpI0YuqTSMc28') 
TMDB_API_KEY = os.environ.get('TMDB_API_KEY', '7dc544d9253bccc3cfecc1c677f69819') 
BOT_USERNAME = os.environ.get('BOT_USERNAME', 'MoviePostGeneratorBot') 

# আপনার প্রাইভেট ডাটাবেজ চ্যানেলের আইডি (অবশ্যই -100 সহ)
DATABASE_CHANNEL_ID = int(os.environ.get('DATABASE_CHANNEL_ID', -1003506219023)) 

# ফাইল অটো-ডিলিট হওয়ার সময়সীমা (৫ মিনিট)
AUTO_DELETE_DELAY = 300 

web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is alive and running flawlessly!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# Telebot ইনিশিয়েট করা
bot = telebot.TeleBot(BOT_TOKEN)

# মাল্টি-ইউজার স্টেট ট্র্যাকিং ডিকশনারি
user_states = {}

# টেলিগ্রাফে ফটো আপলোড করার ফাংশন (টেলিগ্রাম ফটো থেকে পাবলিক লিঙ্ক তৈরি করার জন্য)
def upload_to_telegraph(file_id):
    try:
        file_info = bot.get_file(file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        files = {'file': ('photo.jpg', downloaded_file, 'image/jpeg')}
        response = requests.post('https://telegra.ph/upload', files=files).json()
        if isinstance(response, list) and len(response) > 0:
            return "https://telegra.ph" + response[0]['src']
    except Exception as e:
        print(f"Telegraph upload failed: {e}")
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

# স্টার্ট কমান্ড হ্যান্ডলার
@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    if len(text.split()) > 1:
        param = text.split()[1]
        if param.startswith("msg_"):
            try:
                msg_id = int(param.split("_")[1])
                sent_file = bot.copy_message(chat_id=chat_id, from_chat_id=DATABASE_CHANNEL_ID, message_id=msg_id)
                
                warning_text = (
                    "⚠️ **গুরুত্বপূর্ণ সতর্কবার্তা!**\n\n"
                    f"কপিরাইট সুরক্ষার স্বার্থে এই ফাইলটি আগামী **{int(AUTO_DELETE_DELAY/60)} মিনিটের** মধ্যে স্বয়ংক্রিয়ভাবে মুছে ফেলা হবে।\n\n"
                    "তার আগেই ফাইলটি আপনার **Saved Messages**-এ ফরোয়ার্ড করে রাখুন।"
                )
                sent_warning = bot.send_message(chat_id, warning_text, parse_mode="Markdown")
                
                if sent_file and sent_warning:
                    delete_messages_after_delay(chat_id, [sent_file.message_id, sent_warning.message_id], AUTO_DELETE_DELAY)
                    
            except Exception:
                bot.send_message(chat_id, "❌ ফাইলটি লোড করা যাচ্ছে না বা ডিলিট হয়ে গেছে।")
        return

    user_states[chat_id] = {}
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_movie = types.InlineKeyboardButton("🎬 মুভি পোস্ট", callback_data="type_movie")
    btn_series = types.InlineKeyboardButton("📺 ওয়েব সিরিজ পোস্ট", callback_data="type_series")
    markup.add(btn_movie, btn_series)
    
    bot.send_message(chat_id, 
                     "👋 **BD Movie Zone ফাইল স্টোর ও ব্লগার পোস্ট জেনারেটর প্যানেল!**\n\n"
                     "কোনো লিঙ্ক ছাড়া সরাসরি ফাইল ফরোয়ার্ড করে পোস্ট তৈরি করতে ক্যাটাগরি সিলেক্ট করুন:", 
                     parse_mode="Markdown", reply_markup=markup)

# callback query বাটন হ্যান্ডলার
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    chat_id = call.message.chat.id
    
    if call.data == "type_movie":
        user_states[chat_id] = {'type': 'movie'}
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_auto = types.InlineKeyboardButton("🔍 TMDB অটো সার্চ", callback_data="mode_auto")
        btn_manual = types.InlineKeyboardButton("✏️ ম্যানুয়াল পোস্ট", callback_data="mode_manual")
        markup.add(btn_auto, btn_manual)
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, 
                              text="🎬 **মুভি পোস্ট জেনারেশন:**\n\nমুভি ডাটা কিভাবে ইনপুট করতে চান?", reply_markup=markup)
        
    elif call.data == "type_series":
        user_states[chat_id] = {'type': 'series'}
        markup = types.InlineKeyboardMarkup(row_width=2)
        btn_auto = types.InlineKeyboardButton("🔍 TMDB অটো সার্চ", callback_data="mode_auto")
        btn_manual = types.InlineKeyboardButton("✏️ ম্যানুয়াল পোস্ট", callback_data="mode_manual")
        markup.add(btn_auto, btn_manual)
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, 
                              text="📺 **ওয়েব সিরিজ পোস্ট জেনারেশন:**\n\nসিরিজ ডাটা কিভাবে ইনপুট করতে চান?", reply_markup=markup)

    elif call.data == "mode_auto":
        user_states[chat_id]['step'] = 'waiting_for_search'
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, 
                              text="🔍 অনুগ্রহ করে নামটি ইংরেজিতে টাইপ করে পাঠান:")
        
    elif call.data == "mode_manual":
        user_states[chat_id]['step'] = 'waiting_for_manual_title'
        user_states[chat_id]['movie_data'] = {}
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, 
                              text="✏️ **ম্যানুয়াল পোস্ট শুরু হচ্ছে...**\n\nপ্রথমে পোস্টের মূল টাইটেল/নাম লিখে পাঠান:")

    elif call.data.startswith("select_"):
        parts = call.data.split("_")
        movie_id = parts[1]
        is_tv = parts[2] == "tv"
        fetch_tmdb_details(chat_id, movie_id, is_tv, call.message.message_id)

    elif call.data.startswith("lang_"):
        selected_lang = call.data.split("_")[1]
        if selected_lang == "custom":
            user_states[chat_id]['step'] = 'waiting_for_custom_lang'
            bot.send_message(chat_id, "✏️ আপনার কাস্টম ল্যাঙ্গুয়েজটি টাইপ করে পাঠান (উদা: Tamil [Hindi]):")
        else:
            save_lang_and_proceed(chat_id, selected_lang)
        
    elif call.data == "generate_series_code":
        if chat_id in user_states and 'episodes' in user_states[chat_id] and len(user_states[chat_id]['episodes']) > 0:
            generate_series_html_output(chat_id)
        else:
            bot.answer_callback_query(call.id, "কোনো ফাইল ফরোয়ার্ড করা হয়নি!", show_alert=True)

# ল্যাঙ্গুয়েজ প্রসেস পরবর্তী ধাপ
def save_lang_and_proceed(chat_id, language):
    user_states[chat_id]['movie_data']['lang'] = language
    is_manual = 'is_manual' in user_states[chat_id]

    if is_manual:
        user_states[chat_id]['step'] = 'waiting_for_manual_genres'
        bot.send_message(chat_id, "🎭 মুভির জনরা/ক্যাটাগরি পাঠান (উদা: Action, Comedy, Sci-Fi):")
    else:
        post_type = user_states[chat_id].get('type')
        if post_type == 'movie':
            user_states[chat_id]['step'] = 'waiting_for_480p'
            bot.send_message(chat_id, f"✅ ভাষা সেভ হয়েছে: **{language}**\n\n👉 এখন মুভির **480p (SD)** ফাইলটি ফরোয়ার্ড করুন (অথবা বাদ দিতে /skip লিখুন):")
        else:
            user_states[chat_id]['step'] = 'waiting_for_season'
            bot.send_message(chat_id, f"✅ ভাষা সেভ হয়েছে: **{language}**\n\n👉 এবার সিজন নাম্বারটি লিখে পাঠান (উদা: 1, 2, 3):")

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

    # ম্যানুয়াল পোস্টার রিসিভার (টেলিগ্রাফ)
    elif state == 'waiting_for_manual_poster' and message.content_type == 'photo':
        bot.send_message(chat_id, "⏳ পোস্টার আপলোড হচ্ছে...")
        photo_id = message.photo[-1].file_id
        poster_url = upload_to_telegraph(photo_id)
        
        if poster_url:
            user_states[chat_id]['movie_data']['poster'] = poster_url
            user_states[chat_id]['step'] = 'waiting_for_manual_backdrop'
            bot.send_message(chat_id, "📸 এবার হিরো স্লাইডারের জন্য মুভির **চ্যাপ্টা ব্যানার (Landscape Backdrop Photo)** টি সরাসরি ইমেজ হিসেবে পাঠান:")
        else:
            bot.send_message(chat_id, "❌ পোস্টার আপলোড ব্যর্থ হয়েছে। পুনরায় পাঠান:")

    # ম্যানুয়াল স্লাইডার ব্যানার রিসিভার
    elif state == 'waiting_for_manual_backdrop' and message.content_type == 'photo':
        bot.send_message(chat_id, "⏳ ব্যানার আপলোড হচ্ছে...")
        photo_id = message.photo[-1].file_id
        backdrop_url = upload_to_telegraph(photo_id)
        
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

    # --- মুভির ডাউনলোড ফাইল রিসিভার ---
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
                             "এখন এপিসোড বা কমপ্লিট ব্যাচ জিপ ফাইলটি ফরোয়ার্ড করুন:", reply_markup=markup)
            
        elif state == 'waiting_for_episodes':
            if message.content_type in ['document', 'video']:
                # ডাটাবেজে ফাইল পাঠানো হচ্ছে
                forwarded_msg = bot.forward_message(chat_id=DATABASE_CHANNEL_ID, from_chat_id=chat_id, message_id=message.message_id)
                file_msg_id = f"msg_{forwarded_msg.message_id}"
                
                # পরবর্তী ধাপে ইউজারের কাছে ফাইলের কাস্টম নাম চাওয়া
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

<div style="background: #0d0e12; padding: 20px; border-radius: 8px; border: 1px solid #222; text-align: center; margin: 30px 0;">
    <h3 style="color: #fff; text-transform: uppercase; margin-top: 0;">Download Links:</h3>
    <div style="display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; margin-top: 15px;">
        {"<a href='" + link_480 + "' target='_blank' style='background: #222; color: #fff; padding: 12px 25px; border-radius: 6px; font-weight: bold; text-decoration: none; border: 1px solid #444; transition: 0.3s; font-size:13px;'>📥 Download 480p (SD)</a>" if link_480 else ""}
        {"<a href='" + link_720 + "' target='_blank' style='background: #cc0000; color: #fff; padding: 12px 25px; border-radius: 6px; font-weight: bold; text-decoration: none; transition: 0.3s; font-size:13px;'>📥 Download 720p (HD)</a>" if link_720 else ""}
        {"<a href='" + link_1080 + "' target='_blank' style='background: #38bdf8; color: #000; padding: 12px 25px; border-radius: 6px; font-weight: bold; text-decoration: none; transition: 0.3s; font-size:13px;'>📥 Download 1080p (FullHD)</a>" if link_1080 else ""}
    </div>
</div>
<!-- MOVIE POST END -->"""

    bot.send_message(chat_id, "🎉 **আপনার মুভি পোস্টের HTML কোড প্রস্তুত হয়েছে!**\nনিচের কোডটি কপি করে নিন:")
    bot.send_message(chat_id, f"`{html_code}`", parse_mode="Markdown")
    user_states[chat_id] = {} 

# ওয়েব সিরিজ কোড জেনারেটর (কালারফুল গ্রেডিয়েন্ট এবং নিওন গ্লোয়িং গ্রিড বাটন স্টাইল)
def generate_series_html_output(chat_id):
    data = user_states[chat_id]['movie_data']
    season = user_states[chat_id]['season']
    episodes = user_states[chat_id]['episodes']

    episode_buttons_html = ""
    for ep in episodes:
        link = f"https://t.me/{BOT_USERNAME}?start={ep['key']}"
        # প্রিমিয়াম কালারফুল ডাবল-টোন ডিজাইন বাটন কোড
        episode_buttons_html += f"""        <a href="{link}" target="_blank" style="background: linear-gradient(135deg, #1e1b4b, #111217); color: #fff; padding: 14px 10px; border-radius: 8px; font-weight: 800; text-decoration: none; border: 2px solid #38bdf8; text-align: center; transition: 0.3s; font-size: 13px; box-shadow: 0 4px 10px rgba(56, 189, 248, 0.2); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 5px; min-height: 50px;">
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

<!-- আধুনিক এবং কালারফুল নিওন গ্রিড ডাউনলোড এরিয়া -->
<div style="background: #0d0e12; padding: 25px; border-radius: 12px; border: 1.5px solid #222; margin: 30px 0;">
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
