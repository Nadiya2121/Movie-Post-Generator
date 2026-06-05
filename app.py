import os
import threading
import requests
import telebot
from telebot import types
from flask import Flask

# --- কনফিগারেশন এরিয়া ---
BOT_TOKEN = os.environ.get('BOT_TOKEN', 'YOUR_TELEGRAM_BOT_TOKEN') # পরিবেশ ভেরিয়েবল বা সরাসরি টোকেন দিন
TMDB_API_KEY = os.environ.get('TMDB_API_KEY', 'YOUR_TMDB_API_KEY') # TMDB এপিআই কী
BOT_USERNAME = os.environ.get('BOT_USERNAME', 'YOUR_BOT_USERNAME') # @ চিহ্ন ছাড়া বটের ইউজারনেম

# আপনার প্রাইভেট ডাটাবেজ চ্যানেলের আইডি (আইডিটি অবশ্যই -100 দিয়ে শুরু হতে হবে)
# উদাহরণ: -100123456789 (চ্যানেলে বটকে অ্যাডমিন বানিয়ে পোস্ট পারমিশন দিতে হবে)
DATABASE_CHANNEL_ID = int(os.environ.get('DATABASE_CHANNEL_ID', -100123456789)) 

# ফাইল অটো-ডিলিট হওয়ার সময়সীমা (৫ মিনিট = ৩০০ সেকেন্ড)
AUTO_DELETE_DELAY = 300 

# Flask অ্যাপ তৈরি (Koyeb/Render পোর্ট সচল রাখার জন্য)
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "Bot is alive and running flawlessly!"

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# Telebot ইনিশিয়েট করা
bot = telebot.TeleBot(BOT_TOKEN)

# মাল্টি-ইউজার স্টেট ট্র্যাকিং ডিকশনারি (একসাথে শত শত ইউজার ব্যবহার করতে পারবে)
user_states = {}

# অটো-ডিলিট থ্রেড ফাংশন
def delete_messages_after_delay(chat_id, message_ids, delay):
    def delete():
        for msg_id in message_ids:
            try:
                bot.delete_message(chat_id, msg_id)
            except Exception:
                pass
    threading.Timer(delay, delete).start()

# স্টার্ট কমান্ড হ্যান্ডলার
@bot.message_handler(commands=['start'])
def handle_start(message):
    chat_id = message.chat.id
    text = message.text.strip()
    
    # ইউজার লিঙ্কে ক্লিক করে আসলে (উদা: /start msg_1234)
    if len(text.split()) > 1:
        param = text.split()[1]
        if param.startswith("msg_"):
            try:
                msg_id = int(param.split("_")[1])
                
                # আমাদের প্রাইভেট চ্যানেল থেকে ফাইলটি কপি করে ইউজারের ইনবক্সে পাঠানো
                sent_file = bot.copy_message(chat_id=chat_id, from_chat_id=DATABASE_CHANNEL_ID, message_id=msg_id)
                
                # সতর্কবার্তা মেসেজ
                warning_text = (
                    "⚠️ **গুরুত্বপূর্ণ সতর্কবার্তা!**\n\n"
                    f"কপিরাইট সুরক্ষার স্বার্থে এই ফাইলটি আগামী **{int(AUTO_DELETE_DELAY/60)} মিনিটের** মধ্যে স্বয়ংক্রিয়ভাবে মুছে ফেলা হবে।\n\n"
                    "তার আগেই ফাইলটি আপনার **Saved Messages**-এ ফরোয়ার্ড করে রাখুন।"
                )
                sent_warning = bot.send_message(chat_id, warning_text, parse_mode="Markdown")
                
                # অটো ডিলিট টাইমার ট্রিলিং
                if sent_file and sent_warning:
                    delete_messages_after_delay(chat_id, [sent_file.message_id, sent_warning.message_id], AUTO_DELETE_DELAY)
                    
            except Exception as e:
                bot.send_message(chat_id, "❌ ফাইলটি লোড করা যাচ্ছে না বা ডিলিট হয়ে গেছে।")
        return

    # সাধারণ এডমিন বা ইউজার প্যানেল স্টার্ট
    user_states[chat_id] = {}
    markup = types.InlineKeyboardMarkup(row_width=2)
    btn_movie = types.InlineKeyboardButton("🎬 মুভি পোস্ট (৩ কোয়ালিটি)", callback_data="type_movie")
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
        user_states[chat_id] = {'type': 'movie', 'step': 'waiting_for_search'}
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, 
                              text="🎬 **মুভি পোস্ট সিলেক্ট করা হয়েছে।**\n\n"
                                   "অনুগ্রহ করে মুভির নামটি ইংরেজিতে টাইপ করে পাঠান:")
        
    elif call.data == "type_series":
        user_states[chat_id] = {'type': 'series', 'step': 'waiting_for_search'}
        bot.edit_message_text(chat_id=chat_id, message_id=call.message.message_id, 
                              text="📺 **ওয়েব সিরিজ পোস্ট সিলেক্ট করা হয়েছে।**\n\n"
                                   "অনুগ্রহ করে সিরিজের নামটি ইংরেজিতে টাইপ করে পাঠান:")
        
    elif call.data.startswith("select_"):
        parts = call.data.split("_")
        movie_id = parts[1]
        is_tv = parts[2] == "tv"
        fetch_tmdb_details(chat_id, movie_id, is_tv, call.message.message_id)
        
    elif call.data == "generate_series_code":
        if chat_id in user_states and 'episodes' in user_states[chat_id]:
            generate_series_html_output(chat_id)
        else:
            bot.answer_callback_query(call.id, "কোনো এপিসোড ফরোয়ার্ড করা হয়নি!", show_alert=True)

# টেক্সট, ডকুমেন্ট ও ভিডিও মেসেজ হ্যান্ডলার
@bot.message_handler(content_types=['text', 'document', 'video'])
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

    # --- মুভির ফাইল রিসিভার ---
    if post_type == 'movie':
        file_msg_id = ""
        if message.content_type in ['document', 'video']:
            # সরাসরি ফাইলটি আমাদের প্রাইভেট ডাটাবেজ চ্যানেলে ফরোয়ার্ড করা হচ্ছে
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

    # --- ওয়েব সিরিজের ফাইল রিসিভার ---
    elif post_type == 'series':
        if state == 'waiting_for_season' and message.content_type == 'text':
            user_states[chat_id]['season'] = message.text.strip()
            user_states[chat_id]['episodes'] = []
            user_states[chat_id]['step'] = 'waiting_for_episodes'
            
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✅ কোড জেনারেট করুন", callback_data="generate_series_code"))
            bot.send_message(chat_id, 
                             f"🎬 **সিজন {message.text.strip()} সেট করা হয়েছে!**\n\n"
                             "এখন প্রথম এপিসোড থেকে শুরু করে একে একে ফাইলগুলো ফরোয়ার্ড করুন।\n"
                             "সবগুলো ফাইল ফরোয়ার্ড করা শেষ হলে নিচের বাটনটিতে ক্লিক করবেন:", reply_markup=markup)
            
        elif state == 'waiting_for_episodes':
            if message.content_type in ['document', 'video']:
                # চ্যানেলে ফরোয়ার্ড করে পার্মানেন্টলি সেভ করা
                forwarded_msg = bot.forward_message(chat_id=DATABASE_CHANNEL_ID, from_chat_id=chat_id, message_id=message.message_id)
                file_msg_id = f"msg_{forwarded_msg.message_id}"
                
                ep_num = len(user_states[chat_id]['episodes']) + 1
                user_states[chat_id]['episodes'].append({'num': ep_num, 'key': file_msg_id})
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("✅ কোড জেনারেট করুন", callback_data="generate_series_code"))
                bot.send_message(chat_id, f"✅ **Episode {ep_num} ফাইল যুক্ত হয়েছে!**\n"
                                          f"পরের এপিসোড ফরোয়ার্ড করুন অথবা কোড তৈরি করতে নিচের বাটন চাপুন:", reply_markup=markup)
            else:
                bot.send_message(chat_id, "⚠️ অনুগ্রহ করে শুধুমাত্র এপিসোডের ফাইলটি ফরোয়ার্ড করুন।")

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
            bot.send_message(chat_id, "❌ কোনো ফলাফল পাওয়া যায়নি! আবার চেষ্টা করুন:")
    except Exception:
        bot.send_message(chat_id, "⚠️ TMDB এপিআই সার্ভারে সংযোগ করা যাচ্ছে না।")

# সিলেক্ট করার পর ডিটেইলস সংগ্রহ করা
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
        poster = f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}" if data.get('poster_path') else 'https://via.placeholder.com/300x450'
        plot = data.get('overview', 'No description available.')

        user_states[chat_id]['movie_data'] = {
            'title': f"{title} ({year})",
            'poster': poster,
            'rating': rating,
            'lang': 'Dual Audio' if not is_tv else 'Multi Audio',
            'genres': genres,
            'plot': plot
        }

        if not is_tv:
            user_states[chat_id]['step'] = 'waiting_for_480p'
            bot.send_message(chat_id, f"✅ **মুভি সিলেক্ট করা হয়েছে:** {title}\n\n"
                                      "👉 এখন **480p (SD)** কোয়ালিটির ফাইলটি ফরোয়ার্ড করুন (অথবা বাদ দিতে /skip লিখুন):")
        else:
            user_states[chat_id]['step'] = 'waiting_for_season'
            bot.send_message(chat_id, f"✅ **সিরিজ সিলেক্ট করা হয়েছে:** {title}\n\n"
                                      "👉 এবার সিজন নাম্বারটি লিখে পাঠান (উদা: 1, 2, 3):")
            
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

    html_code = f"""<!-- MOVIE POST START -->
<div style="text-align: center; margin-bottom: 20px;">
    <img src="{data['poster']}" style="max-width: 350px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); width: 100%; height: auto;" alt="{data['title']}"/>
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

# ওয়েব সিরিজ কোড জেনারেটর
def generate_series_html_output(chat_id):
    data = user_states[chat_id]['movie_data']
    season = user_states[chat_id]['season']
    episodes = user_states[chat_id]['episodes']

    episode_buttons_html = ""
    for ep in episodes:
        link = f"https://t.me/{BOT_USERNAME}?start={ep['key']}"
        episode_buttons_html += f'        <a href="{link}" target="_blank" style="background: #1a1b22; color: #fff; padding: 12px; border-radius: 6px; font-weight: bold; text-decoration: none; border: 1px solid #333; text-align: center; transition: 0.3s; font-size:13px; display: inline-block;">Episode {ep["num"]}</a>\n'

    html_code = f"""<!-- TV SHOW POST START -->
<div style="text-align: center; margin-bottom: 20px;">
    <img src="{data['poster']}" style="max-width: 350px; border-radius: 12px; box-shadow: 0 4px 15px rgba(0,0,0,0.5); width: 100%; height: auto;" alt="{data['title']}"/>
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

<div style="background: #0d0e12; padding: 20px; border-radius: 8px; border: 1px solid #222; margin: 30px 0;">
    <h3 style="color: #fff; text-transform: uppercase; margin-top: 0; text-align: center;">Season {season} Download Links:</h3>
    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 10px; margin-top: 15px;">
{episode_buttons_html}    </div>
</div>
<!-- TV SHOW POST END -->"""

    bot.send_message(chat_id, f"🎉 **সিজন {season}-এর সব এপিসোডসহ ওয়েব সিরিজ পোস্টের HTML কোড প্রস্তুত হয়েছে!**\nনিচের কোডটি কপি করে নিন:")
    bot.send_message(chat_id, f"`{html_code}`", parse_mode="Markdown")
    user_states[chat_id] = {} 

# মূল এক্সেকিউশন
if __name__ == '__main__':
    # ১. প্রথমে ব্যাকগ্রাউন্ড থ্রেডে Flask Web Server রান করা (পোর্ট বাইন্ড করার জন্য)
    web_thread = threading.Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()
    
    # ২. এরপর মেইন থ্রেডে টেলিগ্রাম বটের পোলিং রান করা
    print("Web server is running and Telebot is listening successfully...")
    bot.infinity_polling()
