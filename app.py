import os
import threading
import random
import json
import io
import asyncio
import re
import xml.etree.ElementTree as ET
import html # এইচটিএমএল ট্যাগ সুরক্ষিতভাবে পার্স করার জন্য
import urllib.parse
import aiohttp # সম্পূর্ণ এসিঙ্ক্রোনাস এপিআই হ্যান্ডেল করার জন্য
from flask import Flask
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ParseMode # অফিশিয়াল এনাম পার্স মোড

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

http_session = None
web_app = Flask(__name__)
temp_codes = {}

@web_app.route('/')
def home():
    return "Ultra-Fast Async Pyrogram Movie Generator Bot is alive!"

# --- প্রফেশনাল কোড ভিউ ও কপি করার ডায়নামিক ওয়েব রাউট ---
@web_app.route('/code/<code_id>')
def view_code(code_id):
    code_data = None
    if db_mongo is not None:
        try:
            doc = db_mongo['shared_codes'].find_one({'_id': code_id})
            if doc:
                code_data = doc.get('code')
        except Exception:
            pass
    
    if not code_data:
        code_data = temp_codes.get(code_id)
        
    if not code_data:
        return "<h3 style='color: #ef4444; font-family: sans-serif; text-align: center; margin-top: 50px;'>❌ কোডটি পাওয়া যায়নি অথবা মেয়াদ শেষ হয়ে গেছে!</h3>", 404
        
    escaped_html = html.escape(code_data)
    
    web_page = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Copy Post Code - BD Movie Zone</title>
    <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;800&display=swap" rel="stylesheet">
    <style>
        * {{ box-sizing: border-box; }}
        body {{ 
            background-color: #08090c; 
            background-image: radial-gradient(at 0% 0%, rgba(56, 189, 248, 0.08) 0, transparent 50%), radial-gradient(at 100% 100%, rgba(236, 72, 153, 0.05) 0, transparent 50%);
            color: #f1f5f9; 
            font-family: 'Plus Jakarta Sans', sans-serif; 
            margin: 0; 
            padding: 20px; 
            display: flex; 
            flex-direction: column; 
            align-items: center; 
            justify-content: center; 
            min-height: 100vh; 
        }}
        .container {{ 
            background: rgba(17, 18, 24, 0.8); 
            backdrop-filter: blur(12px);
            border: 1px solid rgba(255, 255, 255, 0.08); 
            border-radius: 20px; 
            padding: 40px; 
            max-width: 850px; 
            width: 100%; 
            box-shadow: 0 20px 40px rgba(0,0,0,0.6); 
        }}
        h1 {{ 
            font-size: 24px; 
            font-weight: 800;
            background: linear-gradient(135deg, #38bdf8, #0ea5e9);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-top: 0; 
            text-align: center; 
            border-bottom: 1px solid rgba(255, 255, 255, 0.08); 
            padding-bottom: 20px; 
            letter-spacing: -0.5px;
        }}
        .btn {{ 
            background: linear-gradient(135deg, #38bdf8, #0284c7); 
            color: #ffffff; 
            font-weight: 600; 
            border: none; 
            padding: 16px 28px; 
            border-radius: 12px; 
            cursor: pointer; 
            font-size: 16px; 
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1); 
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 10px;
            width: 100%; 
            margin-bottom: 24px; 
            text-align: center; 
            font-family: 'Plus Jakarta Sans', sans-serif; 
            box-shadow: 0 4px 15px rgba(56, 189, 248, 0.25);
        }}
        .btn:hover {{ 
            transform: translateY(-2px); 
            box-shadow: 0 8px 25px rgba(56, 189, 248, 0.4); 
            filter: brightness(1.1);
        }}
        .btn:active {{
            transform: translateY(1px);
        }}
        pre {{ 
            background: #030406; 
            padding: 20px; 
            border-radius: 12px; 
            overflow-x: auto; 
            max-height: 400px; 
            border: 1px solid rgba(255, 255, 255, 0.05); 
            font-size: 14px; 
            color: #34d399; 
        }}
        pre::-webkit-scrollbar {{
            width: 8px;
            height: 8px;
        }}
        pre::-webkit-scrollbar-track {{
            background: #030406;
        }}
        pre::-webkit-scrollbar-thumb {{
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
        }}
        pre::-webkit-scrollbar-thumb:hover {{
            background: rgba(255, 255, 255, 0.2);
        }}
        code {{ 
            font-family: 'Fira Code', Consolas, Monaco, monospace; 
        }}
        .footer {{ 
            margin-top: 24px; 
            font-size: 13px; 
            color: #64748b; 
            text-align: center; 
            font-weight: 500;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📋 BD Movie Zone - HTML Code Export</h1>
        <button class="btn" id="copyBtn" onclick="copyToClipboard()">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
            <span id="btnText">Click to Copy Code</span>
        </button>
        <pre><code id="codeBlock">{escaped_html}</code></pre>
    </div>
    <div class="footer">Powered by BD Movie Zone Bot Engine</div>
    <script>
        function copyToClipboard() {{
            var codeText = document.getElementById("codeBlock").innerText;
            navigator.clipboard.writeText(codeText).then(function() {{
                var btn = document.getElementById("copyBtn");
                var btnText = document.getElementById("btnText");
                btnText.innerHTML = "Code Copied Successfully!";
                btn.style.background = "linear-gradient(135deg, #10b981, #059669)";
                btn.style.boxShadow = "0 8px 25px rgba(16, 185, 129, 0.35)";
                setTimeout(function() {{
                    btnText.innerHTML = "Click to Copy Code";
                    btn.style.background = "linear-gradient(135deg, #38bdf8, #0284c7)";
                    btn.style.boxShadow = "0 4px 15px rgba(56, 189, 248, 0.25)";
                }}, 2500);
            }}).catch(function(err) {{
                alert("Failed to copy: " + err);
            }});
        }}
    </script>
</body>
</html>"""
    return web_page

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

app = Client(
    "movie_post_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# --- লিংক ডিসপ্যাচার ---
async def send_html_code(client, chat_id, html_code, filename="post_code.html"):
    code_id = "".join(random.choice("abcdefghijklmnopqrstuvwxyz0123456789") for _ in range(8))
    
    if db_mongo is not None:
        try:
            db_mongo['shared_codes'].update_one(
                {'_id': code_id},
                {'$set': {'code': html_code}},
                upsert=True
            )
        except Exception as e:
            print(f"MongoDB save code failed: {e}")
            temp_codes[code_id] = html_code
    else:
        temp_codes[code_id] = html_code

    app_url = os.environ.get('APP_URL', 'https://your-bot-domain.koyeb.app').rstrip('/')
    share_link = f"{app_url}/code/{code_id}"

    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 এক ক্লিকে কোড কপি করুন", url=share_link)]
    ])
    
    await client.send_message(
        chat_id,
        "🔗 **আপনার ব্লগার HTML কোডটি প্রস্তুত করা হয়েছে!**\n\n"
        "নিচের বাটনে ক্লিক করে কোড পেইজে যান এবং সেখান থেকে এক ক্লিকে কোডটি কপি করে সরাসরি ব্লগারে বসিয়ে দিন।",
        reply_markup=markup
    )

user_states = {}
DB_FILE = 'db_system.json'

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
                    'user_ads': config.get('user_ads', {}),
                    'autopost_configs': config.get('autopost_configs', {})
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
        'user_ads': {},
        'autopost_configs': {}
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
                    'user_ads': system_db['user_ads'],
                    'autopost_configs': system_db.get('autopost_configs', {})
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

async def upload_image_to_cloud(file_id):
    global http_session
    if not http_session:
        return None
        
    try:
        get_file_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
        async with http_session.get(get_file_url, timeout=10) as resp:
            res = await resp.json()
        if not res.get('ok'):
            return None
        file_path = res['result']['file_path']
        
        download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
        async with http_session.get(download_url, timeout=12) as resp:
            img_data = await resp.read()
        if not img_data:
            return None

        # ImgBB
        if IMGBB_API_KEY and IMGBB_API_KEY != "YOUR_IMGBB_API_KEY":
            try:
                url = "https://api.imgbb.com/1/upload"
                form_data = aiohttp.FormData()
                form_data.add_field('key', IMGBB_API_KEY)
                form_data.add_field('image', img_data, filename='photo.jpg', content_type='image/jpeg')
                
                async with http_session.post(url, data=form_data, timeout=15) as resp:
                    if resp.status == 200:
                        res_data = await resp.json()
                        if res_data.get('success'):
                            return res_data['data']['url']
            except Exception as e:
                print(f"ImgBB failed: {e}")

        # Catbox
        try:
            url = "https://catbox.moe/user/api.php"
            form_data = aiohttp.FormData()
            form_data.add_field('reqtype', 'fileupload')
            form_data.add_field('fileToUpload', img_data, filename='photo.jpg', content_type='image/jpeg')
            
            async with http_session.post(url, data=form_data, timeout=10) as resp:
                res_text = await resp.text()
                if resp.status == 200 and res_text.startswith('http'):
                    return res_text.strip()
        except Exception as e:
            print(f"Catbox failed: {e}")

    except Exception as e:
        print(f"Image upload services failed: {e}")
    return None


# --- ডাইনামিক ও প্রিমিয়াম ক্যাপশন জেনারেটর ---
def generate_premium_caption(chat_id, quality=None, episode_name=None):
    data = user_states[chat_id].get('movie_data', {})
    title = data.get('title', 'Unknown')
    rating = data.get('rating', 'N/A')
    lang = data.get('lang', 'N/A')
    
    if episode_name:
        caption = (
            f"📺 <b>{title}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⭐️ <b>IMDb:</b> {rating}\n"
            f"🗣 <b>Language:</b> {lang}\n"
            f"💿 <b>Episode:</b> {episode_name}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📥 <i>Downloaded via @{BOT_USERNAME}</i>"
        )
    else:
        caption = (
            f"🎬 <b>{title}</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"⭐️ <b>IMDb:</b> {rating}\n"
            f"🗣 <b>Language:</b> {lang}\n"
            f"💿 <b>Quality:</b> {quality}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"📥 <i>Downloaded via @{BOT_USERNAME}</i>"
        )
    return caption


# এসিঙ্ক্রোনাস ডাটাবেজ চ্যানেল আপলোডার (HTML ক্যাপশন সম্বলিত)
async def save_file_to_db_channel(from_chat_id, message_id, file_type, file_id, caption=""):
    global http_session
    if not http_session:
        return None
        
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument" if file_type == 'document' else f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
        payload = {
            "chat_id": DATABASE_CHANNEL_ID,
            "caption": caption,
            "parse_mode": "HTML"
        }
        if file_type == 'document':
            payload["document"] = file_id
        else:
            payload["video"] = file_id
        
        async with http_session.post(url, json=payload, timeout=15) as resp:
            res = await resp.json()
        if res.get('ok'):
            return res['result']['message_id']
    except Exception as e:
        print(f"Async HTTP send file_id failed: {e}")

    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/forwardMessage"
        payload = {
            "chat_id": DATABASE_CHANNEL_ID,
            "from_chat_id": from_chat_id,
            "message_id": message_id
        }
        async with http_session.post(url, json=payload, timeout=15) as resp:
            res = await resp.json()
        if res.get('ok'):
            return res['result']['message_id']
    except Exception as e:
        print(f"Async HTTP Forward Failed: {e}")
    return None

async def send_file_to_user(to_chat_id, msg_id):
    global http_session
    if not http_session:
        return None
        
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/copyMessage"
        payload = {
            "chat_id": to_chat_id,
            "from_chat_id": DATABASE_CHANNEL_ID,
            "message_id": msg_id
        }
        async with http_session.post(url, json=payload, timeout=15) as resp:
            res = await resp.json()
        if res.get('ok'):
            return res['result']['message_id']
    except Exception as e:
        print(f"Async HTTP copyMessage failed: {e}")
    return None

async def delete_messages_after_delay(chat_id, message_ids, delay):
    await asyncio.sleep(delay)
    for msg_id in message_ids:
        try:
            await app.delete_messages(chat_id, msg_id)
        except Exception:
            pass

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
    return OWNER_DIRECT_LINK if OWNER_DIRECT_LINK else ""

async def send_language_picker(client, chat_id, text="🗣 অনুগ্রহ করে মুভি/সিরিজের ভাষা (Language) সিলেক্ট করুন:"):
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧 English", callback_data="lang_English"), InlineKeyboardButton("🇮🇳 Hindi", callback_data="lang_Hindi")],
        [InlineKeyboardButton("🇧🇩 Bangla", callback_data="lang_Bangla"), InlineKeyboardButton("🎙 Dual Audio (Hin-Eng)", callback_data="lang_Dual Audio (Hindi-English)")],
        [InlineKeyboardButton("🎙 Multi Audio", callback_data="lang_Multi Audio"), InlineKeyboardButton("✏️ কাস্টম টাইপ করুন", callback_data="lang_custom")]
    ])
    await client.send_message(chat_id, text, reply_markup=markup)


# ==================== টেলিগ্রাম কমান্ড হ্যান্ডলারস ====================

@app.on_message(filters.command("set_ad") & filters.private)
async def set_user_ad(client, message):
    chat_id = message.chat.id
    text = message.text.replace("/set_ad", "").strip()
    
    if not text:
        await message.reply_text("⚠️ **ভুল ফরম্যাট!**\n\nঅনুগ্রহ করে এভাবে কমা দিয়ে আপনার ডাইরেক্ট লিঙ্কগুলো পাঠান:\n"
                                 "`/set_ad https://link1.com, https://link2.com`", parse_mode=ParseMode.MARKDOWN)
        return
        
    links = [l.strip() for l in text.split(",") if l.strip().startswith("http")]
    if not links:
        await message.reply_text("❌ কোনো ভ্যালিড লিঙ্ক পাওয়া যায়নি! লিঙ্ক অবশ্যই `http` বা `https` দিয়ে শুরু হতে হবে।")
        return
        
    system_db['user_ads'][str(chat_id)] = links
    save_system_db()
    await message.reply_text(f"🎉 **অভিনন্দন!** আপনার মোট {len(links)} টি ডাইরেক্ট লিঙ্ক সফলভাবে রোটেশন ডাটাবেজে সেভ হয়েছে।")

@app.on_message(filters.command("my_ad") & filters.private)
async def my_ad_stats(client, message):
    chat_id = message.chat.id
    user_ads = system_db.get('user_ads', {}).get(str(chat_id), [])
    
    if not user_ads:
        await message.reply_text("ℹ️ আপনার কোনো নিজস্ব ডাইরেক্ট লিঙ্ক সেট করা নেই। ডিফল্ট স্পনসর লিঙ্ক ব্যবহার করা হচ্ছে।\n"
                                 "আপনার নিজস্ব ইনকাম চালু করতে এখনই সেট করুন: `/set_ad <আপনার_লিঙ্ক>`")
    else:
        links_text = "\n".join([f"{i+1}. {link}" for i, link in enumerate(user_ads)])
        await message.reply_text(f"📋 **আপনার একটিভ ডাইরেক্ট লিঙ্কসমূহ (রোটেশন লিস্ট):**\n\n{links_text}")

@app.on_message(filters.command("set_share") & filters.private)
async def set_owner_share(client, message):
    chat_id = message.chat.id
    if chat_id != OWNER_ID:
        return
        
    text = message.text.replace("/set_share", "").strip()
    try:
        percent = int(text)
        if 0 <= percent <= 100:
            system_db['owner_share'] = percent
            save_system_db()
            await message.reply_text(f"✅ **ওনার সিক্রেট রেভিনিউ শেয়ার {percent}% সেট করা হয়েছে!**")
        else:
            await message.reply_text("❌ পার্সেন্ট অবশ্যই ০ থেকে ১০০ এর মধ্যে হতে হবে।")
    except ValueError:
        await message.reply_text("⚠️ ভুল ফরম্যাট! সঠিক ফরম্যাট: `/set_share 20`")

@app.on_message(filters.command("add_owner_ad") & filters.private)
async def add_owner_ad(client, message):
    chat_id = message.chat.id
    if chat_id != OWNER_ID:
        return
        
    link = message.text.replace("/add_owner_ad", "").strip()
    if not link.startswith("http"):
        await message.reply_text("⚠️ অনুগ্রহ করে একটি ভ্যালিড ডাইরেক্ট লিঙ্ক দিন।")
        return
        
    system_db['owner_ads'].append(link)
    save_system_db()
    await message.reply_text(f"✅ ওনারের রোটেশন ডাটাবেজে নতুন ডাইরেক্ট লিঙ্ক সফলভাবে যুক্ত হয়েছে।")

@app.on_message(filters.command("del_owner_ad") & filters.private)
async def del_owner_ad(client, message):
    chat_id = message.chat.id
    if chat_id != OWNER_ID:
        return
        
    link = message.text.replace("/del_owner_ad", "").strip()
    if link in system_db['owner_ads']:
        system_db['owner_ads'].remove(link)
        save_system_db()
        await message.reply_text(f"✅ ওনারের রোটেশন ডাটাবেজ থেকে লিঙ্কটি মুছে ফেলা হয়েছে।")
    else:
        await message.reply_text("❌ এই লিঙ্কটি ওনারের ডাটাবেজে পাওয়া যায়নি!")

@app.on_message(filters.command("owner_stats") & filters.private)
async def owner_stats_handler(client, message):
    chat_id = message.chat.id
    if chat_id != OWNER_ID:
        return
        
    owner_ads = system_db.get('owner_ads', [])
    share = system_db.get('owner_share', 20)
    links_text = "\n".join([f"{i+1}. {link}" for i, link in enumerate(owner_ads)])
    
    await message.reply_text(f"📊 **ওনার সিক্রেট ড্যাশবোর্ড:**\n\n"
                              f"👥 ওনার সিক্রেট শেয়ার: **{share}%**\n"
                              f"📋 ওনারের একটিভ লিঙ্কসমূহ:\n{links_text}")


# ==================== ৩-কম্যান্ড অটো-পোস্ট সেটআপ এরিয়া ====================

@app.on_message(filters.command("set_website") & filters.private)
async def set_user_website(client, message):
    chat_id = message.chat.id
    text = message.text.replace("/set_website", "").strip()
    if not text or not text.startswith("http"):
        await message.reply_text("⚠️ **ভুল ফরম্যাট!**\n\nঅনুগ্রহ করে এভাবে আপনার ওয়েবসাইটের লিঙ্ক দিন:\n`/set_website https://yourblog.com`")
        return
    
    feed_url = f"{text.rstrip('/')}/feeds/posts/default"
    if 'autopost_configs' not in system_db:
        system_db['autopost_configs'] = {}
    
    if str(chat_id) not in system_db['autopost_configs']:
        system_db['autopost_configs'][str(chat_id)] = {}
        
    system_db['autopost_configs'][str(chat_id)]['website'] = text
    system_db['autopost_configs'][str(chat_id)]['feed'] = feed_url
    system_db['autopost_configs'][str(chat_id)]['last_post_id'] = None
    save_system_db()
    await message.reply_text(f"✅ **ওয়েবসাইট সেটআপ সম্পন্ন!**\n\n🌐 লিঙ্ক: `{text}`\n⚙️ ফিড: `{feed_url}`")

@app.on_message(filters.command("set_tutorial") & filters.private)
async def set_user_tutorial(client, message):
    chat_id = message.chat.id
    text = message.text.replace("/set_tutorial", "").strip()
    if not text or not text.startswith("http"):
        await message.reply_text("⚠️ **ভুল ফরম্যাট!**\n\nঅনুগ্রহ করে এভাবে আপনার ভিডিও বা পোস্ট টিউটোরিয়াল লিঙ্ক দিন:\n`/set_tutorial https://t.me/yourchannel/123`")
        return
        
    if 'autopost_configs' not in system_db:
        system_db['autopost_configs'] = {}
    if str(chat_id) not in system_db['autopost_configs']:
        system_db['autopost_configs'][str(chat_id)] = {}
        
    system_db['autopost_configs'][str(chat_id)]['tutorial'] = text
    save_system_db()
    await message.reply_text(f"✅ **ডাউনলোড টিউটোরিয়াল সেটআপ সম্পন্ন!**\n\n🎥 লিঙ্ক: `{text}`")

@app.on_message(filters.command("set_channel") & filters.private)
async def set_user_channel(client, message):
    chat_id = message.chat.id
    text = message.text.replace("/set_channel", "").strip()
    if not text:
        await message.reply_text("⚠️ **ভুল ফরম্যাট!**\n\nঅনুগ্রহ করে আপনার প্রাইভেট বা পাবলিক চ্যানেল আইডি দিন:\n`/set_channel -100123456789`")
        return
        
    if not (text.startswith("-100") or text.startswith("@")):
        await message.reply_text("❌ **ভুল চ্যানেল আইডি!**\n\nচ্যানেল আইডি অবশ্যই `-100` দিয়ে শুরু হতে হবে অথবা পাবলিক হলে `@` দিয়ে শুরু হতে হবে।")
        return
        
    if 'autopost_configs' not in system_db:
        system_db['autopost_configs'] = {}
    if str(chat_id) not in system_db['autopost_configs']:
        system_db['autopost_configs'][str(chat_id)] = {}
        
    system_db['autopost_configs'][str(chat_id)]['channel'] = text
    save_system_db()
    await message.reply_text(f"✅ **চ্যানেল আইডি সেটআপ সম্পন্ন!**\n\n📢 আইডি: `{text}`\n\n⚠️ *গুরুত্বপূর্ণ: নিশ্চিত করুন যে বটটিকে আপনার এই চ্যানেলে পোস্ট করার পারমিশন সহ Admin এড করেছেন।*")

@app.on_message(filters.command("my_setup") & filters.private)
async def view_user_setup(client, message):
    chat_id = message.chat.id
    configs = system_db.get('autopost_configs', {}).get(str(chat_id), {})
    
    if not configs:
        await message.reply_text("❌ আপনার কোনো অটো-পোস্ট সেটআপ পাওয়া যায়নি। শুরু করতে কম্যান্ডগুলো ব্যবহার করুন:\n\n"
                                 "১. ওয়েবসাইট: `/set_website <লিঙ্ক>`\n"
                                 "২. চ্যানেল আইডি: `/set_channel <আইডি>`\n"
                                 "৩. টিউটোরিয়াল (ঐচ্ছিক): `/set_tutorial <লিঙ্ক>`")
        return
        
    website = configs.get('website', 'Not Set ❌')
    channel = configs.get('channel', 'Not Set ❌')
    tutorial = configs.get('tutorial', 'Not Set ❌')
    
    await message.reply_text(f"⚙️ **আপনার অটো-পোস্ট কনফিগারেশন:**\n\n"
                             f"🌐 **ওয়েবসাইট:** `{website}`\n"
                             f"📢 **চ্যানেল আইডি:** `{channel}`\n"
                             f"🎥 **টিউটোরিয়াল:** `{tutorial}`\n\n"
                             f"💡 *সবগুলো সঠিকভাবে সেটআপ করা থাকলে ওয়েবসাইট পোস্টে অটো-পোস্টিং সচল হবে।*")

@app.on_message(filters.command("del_setup") & filters.private)
async def delete_user_setup(client, message):
    chat_id = message.chat.id
    if 'autopost_configs' in system_db and str(chat_id) in system_db['autopost_configs']:
        del system_db['autopost_configs'][str(chat_id)]
        save_system_db()
        await message.reply_text("✅ আপনার অটো-পোস্ট কনফিগারেশন সম্পূর্ণরূপে ডাটাবেজ থেকে মুছে ফেলা হয়েছে।")
    else:
        await message.reply_text("❌ আপনার কোনো একটিভ কনফিগারেশন পাওয়া যায়নি।")


# ==================== স্টার্ট ও বাটন হ্যান্ডলারস ====================

@app.on_message(filters.command("start") & filters.private)
async def handle_start(client, message):
    chat_id = message.chat.id
    text = message.text.strip() if message.text else ""
    
    if len(text.split()) > 1:
        param = text.split()[1]
        if param.startswith("msg_"):
            user_msg_id = await send_file_to_user(chat_id, int(param.split("_")[1]))
            
            if user_msg_id:
                warning_text = (
                    "⚠️ **গুরুত্বপূর্ণ সতর্কবার্তা!**\n\n"
                    f"কপিরাইট সুরক্ষার স্বার্থে এই ফাইলটি আগামী **{int(AUTO_DELETE_DELAY/60)} মিনিটের** মধ্যে স্বয়ংক্রিয়ভাবে মুছে ফেলা হবে।\n\n"
                    "তার আগেই ফাইলটি আপনার **Saved Messages**-এ ফরোয়ার্ড করে রাখুন।"
                )
                sent_warning = await client.send_message(chat_id, warning_text, parse_mode=ParseMode.MARKDOWN)
                asyncio.create_task(delete_messages_after_delay(chat_id, [user_msg_id, sent_warning.id], AUTO_DELETE_DELAY))
            else:
                await client.send_message(chat_id, "❌ ফাইলটি লোড করা যাচ্ছে না বা ডিলিট হয়ে গেছে।")
        return

    user_states[chat_id] = {}
    markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎬 মুভি পোস্ট", callback_data="type_movie"),
         InlineKeyboardButton("📺 ওয়েব সিরিজ পোস্ট", callback_data="type_series")]
    ])
    
    await client.send_message(chat_id, 
                     "👋 **BD Movie Zone আল্ট্রা-ফাস্ট ফাইল স্টোর ও blogger পোস্ট জেনারেটর প্যানেল!**\n\n"
                     "সরাসরি ফাইল ফরোয়ার্ড করে পোস্ট তৈরি করতে ক্যাটাগরি সিলেক্ট করুন:", 
                     reply_markup=markup)

@app.on_callback_query()
async def handle_query(client, callback_query):
    chat_id = callback_query.message.chat.id
    data = callback_query.data
    
    if data == "type_movie":
        user_states[chat_id] = {'type': 'movie'}
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 TMDB/IMDb লিঙ্ক বা নাম", callback_data="mode_auto"),
             InlineKeyboardButton("✏️ ম্যানুয়াল পোস্ট", callback_data="mode_manual")]
        ])
        await callback_query.edit_message_text("🎬 **মুভি পোস্ট জেনারেশন:**\n\nমুভি ডাটা কিভাবে ইনপুট করতে চান?", reply_markup=markup)
        
    elif data == "type_series":
        user_states[chat_id] = {'type': 'series'}
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 TMDB/IMDb লিঙ্ক বা নাম", callback_data="mode_auto"),
             InlineKeyboardButton("✏️ ম্যানুয়াল পোস্ট", callback_data="mode_manual")]
        ])
        await callback_query.edit_message_text("📺 **ওয়েব সিরিজ পোস্ট জেনারেশন:**\n\nসিরিজ ডাটা কিভাবে ইনপুট করতে চান?", reply_markup=markup)

    elif data == "mode_auto":
        user_states[chat_id]['step'] = 'waiting_for_search'
        await callback_query.edit_message_text("🔍 অনুগ্রহ করে মুভি/সিরিজের ইংরেজি নাম লিখুন অথবা সরাসরি TMDB/IMDb লিঙ্কটি পাঠান:")
        
    elif data == "mode_manual":
        user_states[chat_id]['step'] = 'waiting_for_manual_title'
        user_states[chat_id]['movie_data'] = {}
        await callback_query.edit_message_text("✏️ **ম্যানুয়াল পোস্ট শুরু হচ্ছে...**\n\nপ্রথমে পোস্টের মূল টাইটেল/নাম লিখে পাঠান:")

    elif data.startswith("select_"):
        parts = data.split("_")
        movie_id = parts[1]
        is_tv = parts[2] == "tv"
        await fetch_tmdb_details(client, chat_id, movie_id, is_tv)

    elif data.startswith("lang_"):
        selected_lang = data.split("_")[1]
        if selected_lang == "custom":
            user_states[chat_id]['step'] = 'waiting_for_custom_lang'
            await client.send_message(chat_id, "✏️ আপনার কাস্টম ল্যাঙ্গুয়েজটি টাইপ করে পাঠান (উদা: Tamil [Hindi]):")
        else:
            await save_lang_and_proceed(client, chat_id, selected_lang)
        
    elif data == "generate_series_code":
        if chat_id in user_states and 'episodes' in user_states[chat_id] and len(user_states[chat_id]['episodes']) > 0:
            await generate_series_html_output(client, chat_id)
        else:
            await callback_query.answer("কোনো ফাইল ফরোয়ার্ড করা হয়নি!", show_alert=True)

async def save_lang_and_proceed(client, chat_id, language):
    user_states[chat_id]['movie_data']['lang'] = language
    is_manual = 'is_manual' in user_states[chat_id]

    if is_manual:
        user_states[chat_id]['step'] = 'waiting_for_manual_genres'
        await client.send_message(chat_id, "🎭 মুভির জনরা/ক্যাটাগরি পাঠান (উদা: Action, Comedy, Sci-Fi):")
    else:
        post_type = user_states[chat_id].get('type')
        if post_type == 'movie':
            user_states[chat_id]['step'] = 'waiting_for_480p'
            await client.send_message(chat_id, f"✅ ভাষা সেভ হয়েছে: **{language}**\n\n👉 এখন মুভির **480p (SD)** ফাইলটি ফরোয়ার্ড করুন (অথবা বাদ দিতে /skip লিখুন):")
        else:
            user_states[chat_id]['step'] = 'waiting_for_season'
            await client.send_message(chat_id, f"✅ ভাষা সেভ হয়েছে: **{language}**\n\n👉 এবার সিজন নাম্বারটি লিখে পাঠান (উদা: 1, 2, 3):")


# ==================== Message Processing Area ====================

@app.on_message(filters.private)
async def handle_all_messages(client, message):
    chat_id = message.chat.id
    
    if chat_id not in user_states or 'step' not in user_states[chat_id]:
        user_states[chat_id] = {}
        await handle_start(client, message)
        return
        
    state = user_states[chat_id]['step']
    post_type = user_states[chat_id].get('type')

    # সার্চ বা লিঙ্ক প্রসেস
    if state == 'waiting_for_search' and message.text:
        text_input = message.text.strip()
        
        # লিঙ্ক ডিটেকশন রেগুলার এক্সপ্রেশন
        tmdb_movie_regex = r"themoviedb\.org/movie/(\d+)"
        tmdb_tv_regex = r"themoviedb\.org/tv/(\d+)"
        imdb_regex = r"imdb\.com/title/(tt\d+)"
        
        match_movie = re.search(tmdb_movie_regex, text_input)
        match_tv = re.search(tmdb_tv_regex, text_input)
        match_imdb = re.search(imdb_regex, text_input)
        
        if match_movie:
            movie_id = match_movie.group(1)
            await client.send_message(chat_id, "⏳ TMDB মুভি লিঙ্ক সনাক্ত করা হয়েছে। তথ্য লোড করা হচ্ছে...")
            await fetch_tmdb_details(client, chat_id, movie_id, is_tv=False)
        elif match_tv:
            tv_id = match_tv.group(1)
            await client.send_message(chat_id, "⏳ TMDB সিরিজ লিঙ্ক সনাক্ত করা হয়েছে। তথ্য লোড করা হচ্ছে...")
            await fetch_tmdb_details(client, chat_id, tv_id, is_tv=True)
        elif match_imdb:
            imdb_id = match_imdb.group(1)
            await client.send_message(chat_id, "⏳ IMDb লিঙ্ক সনাক্ত করা হয়েছে। TMDB আইডিতে রূপান্তর করা হচ্ছে...")
            # IMDb আইডিকে TMDB তে কনভার্ট করুন
            tmdb_id, resolved_type = await resolve_imdb_to_tmdb(imdb_id)
            if tmdb_id:
                # ইউজারের সিলেক্ট করা ক্যাটাগরি লিঙ্কের ক্যাটাগরির সাথে সামঞ্জস্য করুন
                user_states[chat_id]['type'] = resolved_type
                is_tv = (resolved_type == "series")
                await fetch_tmdb_details(client, chat_id, tmdb_id, is_tv=is_tv)
            else:
                await client.send_message(chat_id, "❌ দুঃখিত! এই IMDb আইডি দিয়ে কোনো মুভি বা সিরিজ খুঁজে পাওয়া যায়নি। দয়া করে সঠিক লিঙ্ক অথবা নাম দিয়ে সার্চ করুন।")
        else:
            # সাধারণ নাম দিয়ে সার্চ করুন
            await search_tmdb(client, chat_id, text_input, post_type)
        return

    # কাস্টম ল্যাঙ্গুয়েজ প্রসেস
    elif state == 'waiting_for_custom_lang' and message.text:
        await save_lang_and_proceed(client, chat_id, message.text.strip())
        return

    # --- ম্যানুয়াল পোস্ট কন্টেন্ট রিসিভার ---
    elif state == 'waiting_for_manual_title' and message.text:
        user_states[chat_id]['movie_data']['title'] = message.text.strip()
        user_states[chat_id]['movie_data']['screenshots'] = [] # ম্যানুয়াল স্ক্রিনশটের জন্য এম্পটি লিস্ট
        user_states[chat_id]['is_manual'] = True
        user_states[chat_id]['step'] = 'waiting_for_manual_rating'
        await client.send_message(chat_id, "⭐ IMDb রেটিং লিখে পাঠান (উদা: 8.2/10):")

    elif state == 'waiting_for_manual_rating' and message.text:
        user_states[chat_id]['movie_data']['rating'] = message.text.strip()
        user_states[chat_id]['step'] = 'waiting_for_lang_selection'
        await send_language_picker(client, chat_id)

    elif state == 'waiting_for_manual_genres' and message.text:
        user_states[chat_id]['movie_data']['genres'] = message.text.strip()
        user_states[chat_id]['step'] = 'waiting_for_manual_poster'
        await client.send_message(chat_id, "📸 এবার মুভির **পোর্ট্রেট পোস্টার (Portrait Poster Photo)** টি সরাসরি ইমেজ হিসেবে পাঠান:")

    # ম্যানুয়াল পোস্টার রিসিভার
    elif state == 'waiting_for_manual_poster' and message.photo:
        await client.send_message(chat_id, "⏳ পোস্টার আপলোড হচ্ছে, দয়া করে অপেক্ষা করুন...")
        photo_id = message.photo.file_id
        poster_url = await upload_image_to_cloud(photo_id)
        
        if poster_url:
            user_states[chat_id]['movie_data']['poster'] = poster_url
            user_states[chat_id]['step'] = 'waiting_for_manual_backdrop'
            await client.send_message(chat_id, "📸 এবার হোমপেজ হিরো স্লাইডারের জন্য মুভির **চ্যাপ্টা ব্যানার (Landscape Backdrop Photo)** টি সরাসরি ইমেজ হিসেবে পাঠান:")
        else:
            await client.send_message(chat_id, "❌ পোস্টার আপলোড ব্যর্থ হয়েছে। পুনরায় পাঠান:")

    # ম্যানুয়াল স্লাইডার ব্যানার রিসিভার
    elif state == 'waiting_for_manual_backdrop' and message.photo:
        await client.send_message(chat_id, "⏳ ব্যানার আপলোড হচ্ছে, দয়া করে অপেক্ষা করুন...")
        photo_id = message.photo.file_id
        backdrop_url = await upload_image_to_cloud(photo_id)
        
        if backdrop_url:
            user_states[chat_id]['movie_data']['backdrop'] = backdrop_url + "?size=original"
            user_states[chat_id]['step'] = 'waiting_for_manual_plot'
            await client.send_message(chat_id, "📖 মুভির সংক্ষেপ কাহিনী / Storyline টাইপ করে পাঠান:")
        else:
            await client.send_message(chat_id, "❌ ব্যানার আপলোড ব্যর্থ হয়েছে। পুনরায় পাঠান:")

    elif state == 'waiting_for_manual_plot' and message.text:
        user_states[chat_id]['movie_data']['plot'] = message.text.strip()
        user_states[chat_id]['movie_data']['screenshots'] = []
        user_states[chat_id]['step'] = 'waiting_for_manual_screenshots'
        await client.send_message(chat_id, "📸 এবার মুভি/সিরিজের কিছু **স্ক্রিনশট (Landscape Screenshots)** সরাসরি ইমেজ হিসেবে পাঠান।\n\nআপনি একের পর এক একাধিক ইমেজ পাঠাতে পারেন।\n\n👉 কাজ শেষ হলে বা স্ক্রিনশট না দিতে চাইলে লিখুন:\n"
                                           "সমাপ্ত করতে: `/done` টাইপ করুন\n"
                                           "বাদ দিতে: `/skip` টাইপ করুন")
        return

    # ম্যানুয়াল স্ক্রিনশট রিসিভার (লুপ ও অপশনাল)
    elif state == 'waiting_for_manual_screenshots':
        if message.photo:
            await client.send_message(chat_id, "⏳ স্ক্রিনশট প্রসেস ও আপলোড হচ্ছে...")
            photo_id = message.photo.file_id
            screenshot_url = await upload_image_to_cloud(photo_id)
            if screenshot_url:
                user_states[chat_id]['movie_data']['screenshots'].append(screenshot_url)
                await client.send_message(chat_id, f"✅ স্ক্রিনশট সফলভাবে যুক্ত হয়েছে! (মোট যুক্ত হয়েছে: {len(user_states[chat_id]['movie_data']['screenshots'])} টি)\n\nপরের স্ক্রিনশট ইমেজটি পাঠান, অথবা সমাপ্ত করতে `/done` এবং বাদ দিতে `/skip` টাইপ করুন।")
            else:
                await client.send_message(chat_id, "❌ স্ক্রিনশট আপলোড করতে সমস্যা হয়েছে। দয়া করে আবার চেষ্টা করুন বা অন্য ইমেজ পাঠান।")
            return
        elif message.text:
            text_val = message.text.strip().lower()
            if text_val in ['/done', '/skip']:
                if post_type == 'movie':
                    user_states[chat_id]['step'] = 'waiting_for_480p'
                    await client.send_message(chat_id, "✅ স্ক্রিনশট ইনপুট সেভ করা হয়েছে।\n\n👉 এখন মুভির **480p (SD)** ফাইলটি ফরোয়ার্ড করুন (অথবা বাদ দিতে /skip লিখুন):")
                else:
                    user_states[chat_id]['step'] = 'waiting_for_season'
                    await client.send_message(chat_id, "✅ স্ক্রিনশট ইনপুট সেভ করা হয়েছে।\n\n👉 এবার সিজন নাম্বারটি লিখে পাঠান (উদা: 1, 2, 3):")
                return
            else:
                await client.send_message(chat_id, "⚠️ ভুল ইনপুট! অনুগ্রহ করে স্ক্রিনশটের জন্য একটি ছবি পাঠান অথবা সমাপ্ত করতে `/done` এবং বাদ দিতে `/skip` টাইপ করুন।")
                return

    # --- মুভির ফাইল ফরোয়ার্ড রিসিভার ---
    if post_type == 'movie' and state in ['waiting_for_480p', 'waiting_for_720p', 'waiting_for_1080p']:
        file_msg_id = ""
        if message.document or message.video:
            file_type = 'document' if message.document else 'video'
            file_id = message.document.file_id if message.document else message.video.file_id
            
            if state == 'waiting_for_480p':
                quality_str = "480p (SD)"
            elif state == 'waiting_for_720p':
                quality_str = "720p (HD)"
            else:
                quality_str = "1080p (FullHD)"
                
            dynamic_caption = generate_premium_caption(chat_id, quality=quality_str)
            db_msg_id = await save_file_to_db_channel(chat_id, message.id, file_type, file_id, dynamic_caption)
            if db_msg_id:
                file_msg_id = f"msg_{db_msg_id}"
            else:
                await client.send_message(chat_id, "❌ ফাইলটি ডাটাবেজ চ্যানেলে সেভ করা যায়নি! অনুগ্রহ করে নিশ্চিত করুন যে বটটি চ্যানেলে এডমিন হিসেবে আছে।")
                return
        elif message.text and message.text.lower().strip() == '/skip':
            file_msg_id = ""
        else:
            await client.send_message(chat_id, "⚠️ অনুগ্রহ করে ফাইলটি ফরোয়ার্ড করুন অথবা বাদ দিতে /skip লিখুন।")
            return

        if state == 'waiting_for_480p':
            user_states[chat_id]['dl_480_key'] = file_msg_id
            user_states[chat_id]['step'] = 'waiting_for_720p'
            await client.send_message(chat_id, "👉 এবার **720p (HD)** কোয়ালিটির ফাইলটি ফরোয়ার্ড করুন (অথবা বাদ দিতে /skip লিখুন):")
            
        elif state == 'waiting_for_720p':
            user_states[chat_id]['dl_720_key'] = file_msg_id
            user_states[chat_id]['step'] = 'waiting_for_1080p'
            await client.send_message(chat_id, "👉 এবার **1080p (FullHD)** কোয়ালিটির ফাইলটি ফরোয়ার্ড করুন (অথবা বাদ দিতে /skip লিখুন):")
            
        elif state == 'waiting_for_1080p':
            user_states[chat_id]['dl_1080_key'] = file_msg_id
            await generate_movie_html_output(client, chat_id)

    # --- ওয়েব সিরিজের ফাইল ও নাম রিসিভার ---
    elif post_type == 'series' and state in ['waiting_for_season', 'waiting_for_episodes', 'waiting_for_ep_name']:
        if state == 'waiting_for_season' and message.text:
            user_states[chat_id]['season'] = message.text.strip()
            user_states[chat_id]['episodes'] = []
            user_states[chat_id]['step'] = 'waiting_for_episodes'
            
            markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ কোড জেনারেট করুন", callback_data="generate_series_code")]
            ])
            await client.send_message(chat_id, 
                             f"🎬 **সিজন {message.text.strip()} সেট করা হয়েছে!**\n\n"
                             "এখন প্রথম এপিসোড থেকে শুরু করে একে একে ফাইলগুলো ফরোয়ার্ড করুন।", reply_markup=markup)
            
        elif state == 'waiting_for_episodes':
            if message.document or message.video:
                user_states[chat_id]['temp_file_id'] = message.document.file_id if message.document else message.video.file_id
                user_states[chat_id]['temp_file_type'] = 'document' if message.document else 'video'
                user_states[chat_id]['temp_message_id'] = message.id
                
                user_states[chat_id]['step'] = 'waiting_for_ep_name'
                await client.send_message(chat_id, "📝 **ফাইলটি রিসিভ হয়েছে!**\n\nপোস্টে প্রদর্শনের জন্য এই ফাইল বা এপিসোডের নামটি কি হবে টাইপ করে জানান?\n"
                                          "(উদা: Episode 1 / Episode 1-2 / Complete Zip Batch / Season 1 Batch)")
            else:
                await client.send_message(chat_id, "⚠️ অনুগ্রহ করে শুধুমাত্র ওয়েব সিরিজের ডাউনলোড ফাইলটি ফরোয়ার্ড করুন।")

        elif state == 'waiting_for_ep_name' and message.text:
            ep_title = message.text.strip()
            
            file_id = user_states[chat_id]['temp_file_id']
            file_type = user_states[chat_id]['temp_file_type']
            orig_msg_id = user_states[chat_id]['temp_message_id']
            
            dynamic_caption = generate_premium_caption(chat_id, episode_name=ep_title)
            db_msg_id = await save_file_to_db_channel(chat_id, orig_msg_id, file_type, file_id, dynamic_caption)
            
            if db_msg_id:
                file_key = f"msg_{db_msg_id}"
                user_states[chat_id]['episodes'].append({
                    'name': ep_title,
                    'key': file_key
                })
                
                user_states[chat_id]['step'] = 'waiting_for_episodes'
                
                markup = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ কোড জেনারেট করুন", callback_data="generate_series_code")]
                ])
                await client.send_message(chat_id, f"✅ **'{ep_title}' সফলভাবে যুক্ত হয়েছে!**\n\n"
                                          f"পরের ফাইলটি ফরোয়ার্ড করুন অথবা কোড তৈরি করতে নিচের বাটনে ক্লিক করুন:", reply_markup=markup)
            else:
                await client.send_message(chat_id, "❌ ফাইলটি ডাটাবেজ চ্যানেলে সেভ করা যায়নি!")

# TMDB সার্চ কুয়েরি
async def search_tmdb(client, chat_id, query, post_type):
    global http_session
    if not http_session:
        return
    
    is_tv = "tv" if post_type == "series" else "movie"
    url = f"https://api.themoviedb.org/3/search/{is_tv}?api_key={TMDB_API_KEY}&query={urllib.parse.quote(query)}"
    
    try:
        async with http_session.get(url, timeout=10) as resp:
            response = await resp.json()
        results = response.get('results', [])
        
        if results:
            markup_buttons = []
            for item in results[:5]:
                title = item.get('title') if post_type == "movie" else item.get('name')
                release_date = item.get('release_date') if post_type == "movie" else item.get('first_air_date')
                year = release_date.split('-')[0] if release_date else 'N/A'
                
                button_text = f"{title} ({year})"
                markup_buttons.append([InlineKeyboardButton(button_text, callback_data=f"select_{item['id']}_{is_tv}")])
                
            await client.send_message(chat_id, "🔍 অনুসন্ধানের ফলাফেলের তালিকা নিচে দেওয়া হলো, সঠিকটি সিলেক্ট করুন:", reply_markup=InlineKeyboardMarkup(markup_buttons))
        else:
            await client.send_message(chat_id, "❌ কোনো মুভি বা সিরিজ পাওয়া যায়নি! অনুগ্রহ করে ম্যানুয়াল এন্ট্রি অপশন ব্যবহার করুন।")
    except Exception as e:
        print(f"Async TMDB Search Error: {e}")
        await client.send_message(chat_id, "⚠️ TMDB এপিআই সার্ভারে সংযোগ করা যাচ্ছে না।")

# IMDb আইডিকে TMDB আইডিতে সমাধান করার জন্য হেল্পার ফাংশন
async def resolve_imdb_to_tmdb(imdb_id):
    global http_session
    if not http_session:
        return None, None
    url = f"https://api.themoviedb.org/3/find/{imdb_id}?api_key={TMDB_API_KEY}&external_source=imdb_id"
    try:
        async with http_session.get(url, timeout=10) as resp:
            data = await resp.json()
        movie_results = data.get('movie_results', [])
        tv_results = data.get('tv_results', [])
        
        if movie_results:
            return movie_results[0]['id'], 'movie'
        elif tv_results:
            return tv_results[0]['id'], 'series'
    except Exception as e:
        print(f"IMDb translation failed: {e}")
    return None, None

# TMDB ডিটেইলস সংগ্রহ (ক্যারেক্টারের বদলে অটোমেটিক ব্যাকড্রপ স্ক্রিনশট ফেচিং সহ)
async def fetch_tmdb_details(client, chat_id, movie_id, is_tv):
    global http_session
    if not http_session:
        return
        
    endpoint = "tv" if is_tv else "movie"
    # কাস্টের বদলে সরাসরি TMDB থেকে অতিরিক্ত ইমেজ ডেটা আনা হচ্ছে
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

        # অটোমেটিক স্ক্রিনশট ফিল্টারিং (ল্যান্ডস্কেপ ব্যাকড্রপস থেকে সেরা ৪টি ছবি নির্বাচন করা হচ্ছে)
        images_data = data.get('images', {})
        backdrops = images_data.get('backdrops', [])
        processed_screenshots = []
        for bg in backdrops[:4]: # সর্বোচ্চ ৪টি চমৎকার স্ক্রিনশট
            file_path = bg.get('file_path')
            if file_path:
                processed_screenshots.append(f"https://image.tmdb.org/t/p/w780{file_path}")

        user_states[chat_id]['movie_data'] = {
            'title': f"{title} ({year})",
            'poster': poster,
            'backdrop': backdrop,
            'rating': rating,
            'genres': genres,
            'plot': plot,
            'screenshots': processed_screenshots
        }

        user_states[chat_id]['step'] = 'waiting_for_lang_selection'
        await send_language_picker(client, chat_id, f"✅ সিলেক্ট হয়েছে: **{title}**\n\n🗣 অনুগ্রহ করে ভাষাটি সিলেক্ট করুন:")
            
    except Exception as e:
        print(f"Async TMDB Details Error: {e}")
        await client.send_message(chat_id, "❌ তথ্য লোড করতে ত্রুটি ঘটেছে!")


# ==================== প্রিমিয়াম HTML পোস্ট টেমপ্লেট জেনারেটরস ====================

# স্ক্রিনশট সেকশনের জন্য রেসপনসিভ ল্যান্ডস্কেপ গ্রিড এইচটিএমএল জেনারেটর
def build_screenshots_html_section(screenshots_list):
    if not screenshots_list:
        return ""
        
    imgs_html = ""
    for img in screenshots_list:
        imgs_html += f'<img class="screenshot-img" src="{img}" alt="Movie Screenshot" loading="lazy"/>\n'
        
    return f"""
    <div class="screenshots-section">
        <div class="screenshots-title">📸 Screenshots Gallery</div>
        <div class="screenshots-grid">
            {imgs_html}
        </div>
    </div>"""


# ১. মুভি কোড জেনারেটর (নিয়ন পালস এনিমেশন ও স্ক্রিনশট গ্যালারি সমৃদ্ধ)
async def generate_movie_html_output(client, chat_id):
    data = user_states[chat_id]['movie_data']
    key_480 = user_states[chat_id].get('dl_480_key', '')
    key_720 = user_states[chat_id].get('dl_720_key', '')
    key_1080 = user_states[chat_id].get('dl_1080_key', '')

    link_480 = f"https://t.me/{BOT_USERNAME}?start={key_480}" if key_480 else ""
    link_720 = f"https://t.me/{BOT_USERNAME}?start={key_720}" if key_720 else ""
    link_1080 = f"https://t.me/{BOT_USERNAME}?start={key_1080}" if key_1080 else ""

    ad_480 = get_button_ad_link(chat_id)
    ad_720 = get_button_ad_link(chat_id)
    ad_1080 = get_button_ad_link(chat_id)

    # প্রিমিয়াম বাটন স্টাইলিং ও মার্কআপ
    btn_480_html = ""
    if link_480:
        btn_480_html = f'''
        <a href="{link_480}" data-ad="{ad_480}" class="download-btn btn-sd pulse-neon">
            <span class="btn-ripple"></span>
            <svg class="btn-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
            <div class="btn-text-content">
                <span class="btn-label-text">Download 480p (SD)</span>
                <span class="btn-subtext">Direct Safe Server</span>
            </div>
        </a>'''

    btn_720_html = ""
    if link_720:
        btn_720_html = f'''
        <a href="{link_720}" data-ad="{ad_720}" class="download-btn btn-hd pulse-neon">
            <span class="btn-ripple"></span>
            <svg class="btn-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
            <div class="btn-text-content">
                <span class="btn-label-text">Download 720p (HD)</span>
                <span class="btn-subtext">Premium High-Speed</span>
            </div>
        </a>'''

    btn_1080_html = ""
    if link_1080:
        btn_1080_html = f'''
        <a href="{link_1080}" data-ad="{ad_1080}" class="download-btn btn-fhd pulse-neon">
            <span class="btn-ripple"></span>
            <svg class="btn-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4M7 10l5 5 5-5M12 15V3"/></svg>
            <div class="btn-text-content">
                <span class="btn-label-text">Download 1080p (FullHD)</span>
                <span class="btn-subtext">Ultra 4K Supported Server</span>
            </div>
        </a>'''

    # স্ক্রিনশট সেকশন প্রিপারেশন
    screenshots_html = build_screenshots_html_section(data.get('screenshots', []))

    html_code = f"""<!-- MOVIE POST START -->
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    
    .movie-container {{
        font-family: 'Plus Jakarta Sans', sans-serif;
        color: #e2e8f0;
        max-width: 800px;
        margin: 0 auto;
        padding: 10px;
    }}
    .poster-wrapper {{
        text-align: center;
        margin-bottom: 30px;
        position: relative;
    }}
    .poster-img {{
        max-width: 320px;
        width: 100%;
        height: auto;
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.6);
        transition: transform 0.4s ease;
    }}
    .poster-img:hover {{
        transform: scale(1.02);
    }}
    .info-card {{
        background: rgba(17, 18, 24, 0.95);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
        margin: 25px 0;
        box-shadow: 0 10px 30px rgba(0,0,0,0.4);
    }}
    .info-card h3 {{
        margin-top: 0;
        color: #38bdf8;
        font-size: 18px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        padding-bottom: 12px;
        margin-bottom: 16px;
    }}
    .info-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 12px;
    }}
    .info-item {{
        font-size: 14px;
        line-height: 1.5;
    }}
    .info-item strong {{
        color: #94a3b8;
    }}
    .rating-badge {{
        color: #fbbf24;
        font-weight: 700;
        display: inline-flex;
        align-items: center;
        gap: 5px;
    }}
    .synopsis-section {{
        margin: 25px 0;
    }}
    .synopsis-title {{
        color: #f43f5e;
        font-size: 18px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-left: 4px solid #f43f5e;
        padding-left: 12px;
        margin-bottom: 12px;
    }}
    .synopsis-text {{
        line-height: 1.7;
        color: #94a3b8;
        font-size: 15px;
    }}
    
    /* --- স্ক্রিনশট গ্যালারি ডিজাইন --- */
    .screenshots-section {{
        margin: 25px 0;
    }}
    .screenshots-title {{
        color: #38bdf8;
        font-size: 18px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-left: 4px solid #38bdf8;
        padding-left: 12px;
        margin-bottom: 16px;
    }}
    .screenshots-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 12px;
    }}
    .screenshot-img {{
        width: 100%;
        aspect-ratio: 16/9;
        object-fit: cover;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        transition: all 0.3s ease;
    }}
    .screenshot-img:hover {{
        transform: scale(1.03);
        border-color: #38bdf8;
        box-shadow: 0 8px 25px rgba(56, 189, 248, 0.25);
    }}

    .guide-box {{
        background: rgba(30, 41, 59, 0.4);
        border: 1px solid rgba(56, 189, 248, 0.2);
        border-left: 5px solid #38bdf8;
        border-radius: 12px;
        padding: 20px;
        margin: 25px 0;
    }}
    .guide-title {{
        color: #38bdf8;
        font-weight: 700;
        font-size: 15px;
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
    }}
    .guide-text {{
        margin: 0;
        font-size: 13px;
        line-height: 1.6;
        color: #cbd5e1;
    }}
    
    /* --- প্রিমিয়াম এনিমেটেড ডাউনলোড বাটন এরিয়া --- */
    .download-area {{
        background: #0b0c10;
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 20px;
        padding: 35px 20px;
        text-align: center;
        margin: 25px 0;
        box-shadow: 0 15px 35px rgba(0,0,0,0.8);
    }}
    .download-area h3 {{
        color: #ffffff;
        font-size: 20px;
        font-weight: 800;
        margin-top: 0;
        margin-bottom: 25px;
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    .button-container {{
        display: flex;
        flex-direction: column;
        gap: 15px;
        max-width: 450px;
        margin: 0 auto;
    }}
    .download-btn {{
        position: relative;
        display: inline-flex;
        align-items: center;
        justify-content: flex-start;
        gap: 15px;
        padding: 16px 28px;
        border-radius: 14px;
        font-weight: 700;
        text-decoration: none;
        transition: all 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        cursor: pointer;
        border: none;
        overflow: hidden;
        z-index: 1;
    }}
    .btn-text-content {{
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        text-align: left;
    }}
    .btn-label-text {{
        font-size: 15px;
        font-weight: 800;
    }}
    .btn-subtext {{
        font-size: 11px;
        opacity: 0.8;
        font-weight: 500;
    }}
    
    /* বাটন গ্রেডিয়েন্ট এবং থিমসমূহ */
    .btn-sd {{
        background: linear-gradient(135deg, #1e293b, #0f172a);
        color: #f1f5f9;
        border: 1px solid rgba(255, 255, 255, 0.1);
    }}
    .btn-hd {{
        background: linear-gradient(135deg, #f43f5e, #be123c);
        color: #ffffff;
        border: 1px solid rgba(244, 63, 94, 0.2);
    }}
    .btn-fhd {{
        background: linear-gradient(135deg, #06b6d4, #0369a1);
        color: #ffffff;
        border: 1px solid rgba(6, 182, 212, 0.2);
    }}
    
    /* নিয়ন গ্লোয়িং এবং ভাইব্রেন্ট পালস এনিমেশন */
    .pulse-neon {{
        animation: neon-shadow-pulse 2s infinite ease-in-out;
    }}
    @keyframes neon-shadow-pulse {{
        0% {{ box-shadow: 0 4px 15px rgba(56, 189, 248, 0.15); }}
        50% {{ box-shadow: 0 8px 25px rgba(56, 189, 248, 0.4); transform: scale(1.015); }}
        100% {{ box-shadow: 0 4px 15px rgba(56, 189, 248, 0.15); }}
    }}
    
    .download-btn:hover {{
        transform: translateY(-4px) scale(1.03);
        filter: brightness(1.15);
    }}
    
    /* ক্লিক হওয়ার পর লাইভ এনিমেশন ট্রানজিশন */
    .btn-clicked {{
        animation: progress-slide 1.5s infinite linear;
        pointer-events: auto;
    }}
</style>

<div class="movie-container">
    <div class="poster-wrapper">
        <img class="poster-img" src="{data['poster']}" alt="{data['title']} Poster"/>
        <img src="{data['backdrop']}" style="display: none;" alt="{data['title']} Backdrop"/>
    </div>

    <!-- মেটা ডেটা (সার্চ ক্রলার ও ফিল্টারের জন্য সংরক্ষিত) -->
    <div class="info-text" style="display: none;">
        <div>Rating: {data['rating']}</div>
        <div>Language: {data['lang']}</div>
        <div>Genres: {data['genres']}</div>
    </div>

    <div class="info-card">
        <h3>Movie Information</h3>
        <div class="info-grid">
            <div class="info-item"><strong>Title:</strong> {data['title']}</div>
            <div class="info-item"><strong>IMDb Rating:</strong> <span class="rating-badge"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style="vertical-align: middle;"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg>{data['rating']}</span></div>
            <div class="info-item"><strong>Language:</strong> {data['lang']}</div>
            <div class="info-item"><strong>Genres:</strong> {data['genres']}</div>
        </div>
    </div>

    {screenshots_html}

    <div class="synopsis-section">
        <div class="synopsis-title">Synopsis / Storyline</div>
        <div class="synopsis-text">{data['plot']}</div>
    </div>

    <div class="guide-box">
        <div class="guide-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
            ডাউনলোড করার সঠিক নিয়ম:
        </div>
        <p class="guide-text">
            ১. ডাউনলোড বাটনে প্রথমবার ক্লিক করলে একটি স্পনসর বিজ্ঞাপনের পেইজ চালু হবে।<br/>
            ২. সেটি ব্যাকগ্রাউন্ডে লোড হতে দিয়ে আপনি বর্তমান (Blogger) পেইজে ফিরে আসুন।<br/>
            ৩. এবার বাটনে <strong>"Click Again to Download"</strong> দেখতে পাবেন, সেখানে পুনরায় ক্লিক করলেই ফাইলটি সরাসরি টেলিগ্রামে পেয়ে যাবেন।
        </p>
    </div>

    <div class="download-area">
        <h3>⚡ Secure Download Links</h3>
        <div class="button-container">
            {btn_480_html}
            {btn_720_html}
            {btn_1080_html}
        </div>
    </div>
</div>

<script>
document.querySelectorAll('.download-btn').forEach(function(element) {{
    element.addEventListener('click', function(e) {{
        var adLink = this.getAttribute('data-ad');
        
        if (!adLink || adLink === 'None' || adLink === '') {{
            return; 
        }}
        
        if (this.getAttribute('data-clicked') !== 'true') {{
            e.preventDefault(); 
            window.open(adLink, '_blank');
            this.setAttribute('data-clicked', 'true');
            this.classList.remove('pulse-neon');
            this.classList.add('btn-clicked');
            
            // সফলভাবে প্রথম ক্লিকের জন্য আনলকড স্টেট ডিজাইন রূপান্তর
            this.style.background = 'linear-gradient(135deg, #10b981, #059669)';
            this.style.borderColor = '#10b981';
            this.style.color = '#ffffff';
            this.style.boxShadow = '0 0 25px rgba(16, 185, 129, 0.6)';
            
            var labelText = this.querySelector('.btn-label-text');
            var subText = this.querySelector('.btn-subtext');
            if (labelText) {{
                labelText.innerHTML = '⚡ Link Unlocked - Click to Download';
            }}
            if (subText) {{
                subText.innerHTML = 'Ready to download via Telegram';
            }}
        }}
    }});
}});
</script>
<!-- MOVIE POST END -->"""

    await client.send_message(chat_id, "🎉 **আপনার মুভি পোস্টের HTML কোড প্রস্তুত হয়েছে!**\nনিচের কোডটি কপি করে নিন:")
    safe_title = "".join(c for c in data['title'] if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
    await send_html_code(client, chat_id, html_code, filename=f"{safe_title}_post.html")
    user_states[chat_id] = {}


# ২. ওয়েব সিরিজ কোড জেনারেটর (গ্রিড-কার্ড এবং প্রিমিয়াম বাটন ট্রানজিশন সহ)
async def generate_series_html_output(client, chat_id):
    data = user_states[chat_id]['movie_data']
    season = user_states[chat_id]['season']
    episodes = user_states[chat_id]['episodes']

    episode_buttons_html = ""
    for ep in episodes:
        link = f"https://t.me/{BOT_USERNAME}?start={ep['key']}"
        ad_link = get_button_ad_link(chat_id)
        
        episode_buttons_html += f"""
        <a href="{link}" data-ad="{ad_link}" class="download-btn series-btn pulse-grid-neon">
            <span class="btn-sub-text">Download Episode</span>
            <span class="btn-label-text">{ep['name']}</span>
        </a>"""

    # স্ক্রিনশট সেকশন প্রিপারেশন
    screenshots_html = build_screenshots_html_section(data.get('screenshots', []))

    html_code = f"""<!-- TV SHOW POST START -->
<style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    
    .series-container {{
        font-family: 'Plus Jakarta Sans', sans-serif;
        color: #e2e8f0;
        max-width: 800px;
        margin: 0 auto;
        padding: 10px;
    }}
    .poster-wrapper {{
        text-align: center;
        margin-bottom: 30px;
    }}
    .poster-img {{
        max-width: 320px;
        width: 100%;
        height: auto;
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 15px 35px rgba(0, 0, 0, 0.6);
        transition: transform 0.4s ease;
    }}
    .poster-img:hover {{
        transform: scale(1.02);
    }}
    .info-card {{
        background: rgba(17, 18, 24, 0.95);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
        margin: 25px 0;
        box-shadow: 0 10px 30px rgba(0,0,0,0.4);
    }}
    .info-card h3 {{
        margin-top: 0;
        color: #38bdf8;
        font-size: 18px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        padding-bottom: 12px;
        margin-bottom: 16px;
    }}
    .info-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 12px;
    }}
    .info-item {{
        font-size: 14px;
        line-height: 1.5;
    }}
    .info-item strong {{
        color: #94a3b8;
    }}
    .rating-badge {{
        color: #fbbf24;
        font-weight: 700;
        display: inline-flex;
        align-items: center;
        gap: 5px;
    }}
    .synopsis-section {{
        margin: 25px 0;
    }}
    .synopsis-title {{
        color: #f43f5e;
        font-size: 18px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-left: 4px solid #f43f5e;
        padding-left: 12px;
        margin-bottom: 12px;
    }}
    .synopsis-text {{
        line-height: 1.7;
        color: #94a3b8;
        font-size: 15px;
    }}
    
    /* --- স্ক্রিনশট গ্যালারি ডিজাইন --- */
    .screenshots-section {{
        margin: 25px 0;
    }}
    .screenshots-title {{
        color: #38bdf8;
        font-size: 18px;
        font-weight: 800;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        border-left: 4px solid #38bdf8;
        padding-left: 12px;
        margin-bottom: 16px;
    }}
    .screenshots-grid {{
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
        gap: 12px;
    }}
    .screenshot-img {{
        width: 100%;
        aspect-ratio: 16/9;
        object-fit: cover;
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.3);
        transition: all 0.3s ease;
    }}
    .screenshot-img:hover {{
        transform: scale(1.03);
        border-color: #38bdf8;
        box-shadow: 0 8px 25px rgba(56, 189, 248, 0.25);
    }}

    .guide-box {{
        background: rgba(30, 41, 59, 0.4);
        border: 1px solid rgba(56, 189, 248, 0.2);
        border-left: 5px solid #38bdf8;
        border-radius: 12px;
        padding: 20px;
        margin: 25px 0;
    }}
    .guide-title {{
        color: #38bdf8;
        font-weight: 700;
        font-size: 15px;
        display: flex;
        align-items: center;
        gap: 8px;
        margin-bottom: 8px;
    }}
    .guide-text {{
        margin: 0;
        font-size: 13px;
        line-height: 1.6;
        color: #cbd5e1;
    }}
    
    /* --- ওয়েব সিরিজ প্রিমিয়াম কার্ড ডিজাইন --- */
    .download-area {{
        background: #0b0c10;
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 20px;
        padding: 35px 20px;
        margin: 25px 0;
        box-shadow: 0 15px 35px rgba(0,0,0,0.8);
    }}
    .download-area h3 {{
        color: #ffffff;
        font-size: 20px;
        font-weight: 800;
        margin-top: 0;
        margin-bottom: 25px;
        text-transform: uppercase;
        letter-spacing: 1px;
        text-align: center;
    }}
    .grid-container {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(170px, 1fr));
        gap: 16px;
    }}
    .series-btn {{
        background: rgba(17, 24, 39, 0.9);
        border: 1.5px solid rgba(56, 189, 248, 0.25);
        color: #ffffff;
        border-radius: 16px;
        padding: 18px 12px;
        text-decoration: none;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 8px;
        transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
        min-height: 90px;
        cursor: pointer;
    }}
    
    .pulse-grid-neon {{
        animation: grid-neon-pulse 2.5s infinite ease-in-out;
    }}
    @keyframes grid-neon-pulse {{
        0% {{ box-shadow: 0 4px 10px rgba(56, 189, 248, 0.1); }}
        50% {{ box-shadow: 0 8px 20px rgba(56, 189, 248, 0.3); border-color: rgba(56, 189, 248, 0.6); }}
        100% {{ box-shadow: 0 4px 10px rgba(56, 189, 248, 0.1); }}
    }}
    
    .series-btn:hover {{
        border-color: #38bdf8;
        transform: translateY(-5px);
        background: rgba(56, 189, 248, 0.08);
    }}
    .btn-sub-text {{
        font-size: 10px;
        text-transform: uppercase;
        color: #38bdf8;
        font-weight: 800;
        letter-spacing: 1px;
    }}
    .btn-label-text {{
        font-size: 14px;
        font-weight: 700;
        text-align: center;
    }}
</style>

<div class="series-container">
    <div class="poster-wrapper">
        <img class="poster-img" src="{data['poster']}" alt="{data['title']} Poster"/>
        <img src="{data['backdrop']}" style="display: none;" alt="{data['title']} Backdrop"/>
    </div>

    <div class="info-text" style="display: none;">
        <div>Rating: {data['rating']}</div>
        <div>Language: {data['lang']}</div>
        <div>Genres: {data['genres']}</div>
    </div>

    <div class="info-card">
        <h3>Series Information</h3>
        <div class="info-grid">
            <div class="info-item"><strong>Title:</strong> {data['title']}</div>
            <div class="info-item"><strong>IMDb Rating:</strong> <span class="rating-badge"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" style="vertical-align: middle;"><path d="M12 17.27L18.18 21l-1.64-7.03L22 9.24l-7.19-.61L12 2 9.19 8.63 2 9.24l5.46 4.73L5.82 21z"/></svg>{data['rating']}</span></div>
            <div class="info-item"><strong>Language:</strong> {data['lang']}</div>
            <div class="info-item"><strong>Genres:</strong> {data['genres']}</div>
            <div class="info-item"><strong>Season:</strong> {season}</div>
        </div>
    </div>

    {screenshots_html}

    <div class="synopsis-section">
        <div class="synopsis-title">Synopsis / Storyline</div>
        <div class="synopsis-text">{data['plot']}</div>
    </div>

    <div class="guide-box">
        <div class="guide-title">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="16" x2="12" y2="12"/><line x1="12" y1="8" x2="12.01" y2="8"/></svg>
            ডাউনলোড করার সঠিক নিয়ম:
        </div>
        <p class="guide-text">
            ১. ডাউনলোড বাটনে প্রথমবার ক্লিক করলে একটি স্পনসর বিজ্ঞাপনের পেইজ চালু হবে।<br/>
            ২. সেটি ব্যাকগ্রাউন্ডে লোড হতে দিয়ে আপনি বর্তমান (Blogger) পেইজে ফিরে আসুন।<br/>
            ৩. এবার বাটনে <strong>"Click Again to Download"</strong> দেখতে পাবেন, সেখানে পুনরায় ক্লিক করলেই ফাইলটি সরাসরি টেলিগ্রামে পেয়ে যাবেন।
        </p>
    </div>

    <div class="download-area">
        <h3>📥 Episode List (Season {season})</h3>
        <div class="grid-container">
            {episode_buttons_html}
        </div>
    </div>
</div>

<script>
document.querySelectorAll('.download-btn').forEach(function(element) {{
    element.addEventListener('click', function(e) {{
        var adLink = this.getAttribute('data-ad');
        
        if (!adLink || adLink === 'None' || adLink === '') {{
            return; 
        }}
        
        if (this.getAttribute('data-clicked') !== 'true') {{
            e.preventDefault(); 
            window.open(adLink, '_blank');
            this.setAttribute('data-clicked', 'true');
            this.classList.remove('pulse-grid-neon');
            
            this.style.background = 'linear-gradient(135deg, #10b981, #059669)';
            this.style.borderColor = '#10b981';
            this.style.color = '#ffffff';
            this.style.boxShadow = '0 0 20px rgba(16, 185, 129, 0.6)';
            
            var subText = this.querySelector('.btn-sub-text');
            var mainText = this.querySelector('.btn-label-text');
            if (subText) subText.innerHTML = '⚡ READY TO DOWNLOAD';
            if (mainText) mainText.innerHTML = 'Click Again';
        }}
    }});
}});
</script>
<!-- TV SHOW POST END -->"""

    await client.send_message(chat_id, f"🎉 **সিজন {season}-এর সব এপিসোডসহ ওয়েব সিরিজ পোস্টের HTML কোড প্রস্তুত হয়েছে!**\nনিচের কোডটি কপি করে নিন:")
    safe_title = "".join(c for c in data['title'] if c.isalnum() or c in (' ', '_', '-')).strip().replace(' ', '_')
    await send_html_code(client, chat_id, html_code, filename=f"{safe_title}_season_{season}.html")
    user_states[chat_id] = {}


# ==================== ব্যাকগ্রাউন্ড স্ক্র্যাপার ও অটো-পোস্ট লজিক ====================

def extract_info_from_blog(content):
    if not content:
        return {'rating': 'N/A', 'genres': 'Movie/Series', 'lang': 'N/A'}
    
    text = re.sub(r'<[^>]+>', ' ', content)
    
    rating_match = re.search(r'(?:Rating|IMDb Rating|IMDB):\s*([\d\./]+|N/A)', text, re.I)
    lang_match = re.search(r'Language:\s*([^📅🎭⏱\n|]+)', text, re.I)
    genres_match = re.search(r'Genres:\s*([^📅🎭⏱\n|]+)', text, re.I)
    
    return {
        'rating': rating_match.group(1).strip() if rating_match else "N/A",
        'lang': lang_match.group(1).strip() if lang_match else "N/A",
        'genres': genres_match.group(1).strip() if genres_match else "Movie/Series"
    }

def extract_poster_from_blog(content):
    if not content:
        return None
    img_match = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', content, re.I)
    if img_match:
        return img_match.group(1)
    return None

async def monitor_feeds():
    while True:
        try:
            configs = system_db.get('autopost_configs', {})
            if not configs:
                await asyncio.sleep(45)
                continue
                
            headers = {"User-Agent": "Mozilla/5.0"}
            async with aiohttp.ClientSession(headers=headers) as session:
                for user_id, config in list(configs.items()):
                    try:
                        f_url = config.get("feed")
                        l_id = config.get("last_post_id")
                        target_chat = config.get("channel")
                        tutorial = config.get("tutorial")
                        
                        if not f_url or not target_chat:
                            continue

                        async with session.get(f_url, timeout=15) as resp:
                            if resp.status != 200: 
                                continue
                            xml_data = await resp.text()
                            root = ET.fromstring(xml_data)
                            ns = {'atom': 'http://www.w3.org/2005/Atom'}
                            entries = root.findall('atom:entry', ns)
                            if not entries: 
                                continue
                            
                            latest = entries[0]
                            p_id = latest.find('atom:id', ns).text
                            if p_id != l_id:
                                # নতুন পোস্ট ডিটেক্ট করা হয়েছে
                                raw_title = latest.find('atom:title', ns).text
                                title = raw_title.split('|')[0].split('-')[0].strip()
                                link = latest.find('atom:link[@rel="alternate"]', ns).attrib['href']
                                
                                content_elem = latest.find('atom:content', ns)
                                content = content_elem.text or "" if content_elem is not None else ""
                                
                                info = extract_info_from_blog(content)
                                poster = extract_poster_from_blog(content)
                                
                                caption = (
                                    f"🎬 <b>NEW UPDATE: {title}</b>\n"
                                    f"━━━━━━━━━━━━━━━━━━━━━\n\n"
                                    f"⭐️ <b>Rating:</b> {info['rating']}\n"
                                    f"🗣 <b>Language:</b> {info['lang']}\n"
                                    f"🎭 <b>Genres:</b> {info['genres']}\n\n"
                                    f"━━━━━━━━━━━━━━━━━━━━━\n"
                                    f"📥 <b>ডাউনলোড করতে নিচের লিংকে ক্লিক করুন 👇</b>"
                                )
                                
                                btns = [[InlineKeyboardButton("🔗 Watch & Download Now", url=link)]]
                                if tutorial and tutorial != 'Not Set ❌' and tutorial.startswith("http"):
                                    btns.append([InlineKeyboardButton("📽️ How to Download", url=tutorial)])

                                try:
                                    if poster: 
                                        await app.send_photo(target_chat, poster, caption=caption, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btns))
                                    else: 
                                        await app.send_message(target_chat, caption, parse_mode=ParseMode.HTML, reply_markup=InlineKeyboardMarkup(btns))
                                    
                                    system_db['autopost_configs'][user_id]['last_post_id'] = p_id
                                    save_system_db()
                                except Exception as e:
                                    print(f"Auto-post error to channel {target_chat} for user {user_id}: {e}")
                    except Exception as e:
                        print(f"Error checking feed of user {user_id}: {e}")
                        continue
        except Exception as e:
            print(f"General monitor loop error: {e}")
        await asyncio.sleep(45)


# ==================== মূল এক্সেকিউশন ====================

if __name__ == '__main__':
    web_thread = threading.Thread(target=run_web_server)
    web_thread.daemon = True
    web_thread.start()
    
    async def main():
        global http_session
        print("Starting Pyrogram Bot Client...")
        await app.start()
        
        http_session = aiohttp.ClientSession()
        
        try:
            print("Resolving and caching Database Channel Peer...")
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            async with http_session.post(url, json={"chat_id": DATABASE_CHANNEL_ID, "text": "♻️ System Online & Connected!"}, timeout=10) as resp:
                res = await resp.json()
            if res.get('ok'):
                print(" Database Channel Peer resolved and cached successfully!")
                del_url = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"
                await http_session.post(del_url, json={"chat_id": DATABASE_CHANNEL_ID, "message_id": res['result']['message_id']}, timeout=10)
        except Exception as e:
            print(f"⚠️ Error resolving database channel peer: {e}")
            
        print("Starting Background Auto-Post Feed Monitor...")
        asyncio.create_task(monitor_feeds())
            
        print("Bot is successfully running and listening for requests...")
        await idle()
        
        if http_session:
            await http_session.close()
        await app.stop()

    asyncio.get_event_loop().run_until_complete(main())
