import os
import sqlite3
from datetime import datetime, timedelta, time as dtime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ONAY_KANALI = os.getenv("ONAY_KANALI_ID")
YAYIN_KANALI = os.getenv("YAYIN_KANALI_ID")
YAYIN_KANAL_LINKI = os.getenv("YAYIN_KANAL_LINKI")
ADMINS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]
LIMIT = 3  # varsayılan limit

app = Client("itiraf_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

conn = sqlite3.connect("itiraflar.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS itiraflar (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    text TEXT,
    sehir TEXT,
    etiket TEXT,
    tarih TEXT,
    onayli INTEGER DEFAULT 0
)
""")
conn.commit()

def txt_dosyadan_liste(dosya_adi):
    with open(dosya_adi, "r", encoding="utf-8") as f:
        return [satir.strip() for satir in f if satir.strip()]

CINSIYEL_KELIMELER = txt_dosyadan_liste("argolar.txt")
SEHIRLER = txt_dosyadan_liste("sehirler.txt")

ETIKETLER = [
    ("Aşk", "❤️"),
    ("Gizlilik", "🕵️"),
    ("Genel", "💬"),
    ("Macera", "🌪️"),
    ("İş Yeri", "🏢")
]

user_state = {}

def icerik_uyarisi(text):
    return any(k in text.lower() for k in CINSIYEL_KELIMELER)

def kullanici_itiraf_sayisi(user_id):
    bugun = datetime.now().strftime("%Y-%m-%d")
    cur.execute("SELECT COUNT(*) FROM itiraflar WHERE user_id = ? AND tarih = ?", (user_id, bugun))
    return cur.fetchone()[0]

def yeni_itiraf_ekle(user_id, text, sehir, etiket):
    tarih = datetime.now().strftime("%Y-%m-%d")
    cur.execute("INSERT INTO itiraflar (user_id, text, sehir, etiket, tarih) VALUES (?, ?, ?, ?, ?)",
                (user_id, text, sehir, etiket, tarih))
    conn.commit()
    return cur.lastrowid

def grupla(liste, n):
    return [liste[i:i + n] for i in range(0, len(liste), n)]

@app.on_message(filters.command("start"))
async def start(_, msg: Message):
    await msg.reply("📍 Hangi şehirden yazıyorsun? (örnek: İstanbul)")
    uid = msg.from_user.id
    user_state[uid] = {"state": "sehir"}

@app.on_message(filters.command("limitayarla") & filters.user(ADMINS))
async def limit_ayarla(_, msg: Message):
    global LIMIT
    try:
        yeni_limit = int(msg.text.split()[1])
        LIMIT = yeni_limit
        await msg.reply(f"✅ Günlük itiraf limiti {LIMIT} olarak ayarlandı.")
    except:
        await msg.reply("❌ Kullanım: /limitayarla <sayi>")

@app.on_message(filters.command("hakkisifirla") & filters.user(ADMINS))
async def hak_sifirla(_, msg: Message):
    try:
        uid = int(msg.text.split()[1])
        bugun = datetime.now().strftime("%Y-%m-%d")
        cur.execute("DELETE FROM itiraflar WHERE user_id = ? AND tarih = ?", (uid, bugun))
        conn.commit()
        await msg.reply(f"✅ {uid} kullanıcısının bugünkü hakları sıfırlandı.")
    except:
        await msg.reply("❌ Kullanım: /hakkisifirla <kullanici_id>")

@app.on_message(filters.command("tumhaklarisifirla") & filters.user(ADMINS))
async def toplu_hak_sifirla(_, msg: Message):
    bugun = datetime.now().strftime("%Y-%m-%d")
    cur.execute("DELETE FROM itiraflar WHERE tarih = ?", (bugun,))
    conn.commit()
    await msg.reply("✅ Bugünkü tüm kullanıcı hakları sıfırlandı.")

@app.on_message(filters.text & ~filters.command(["start"]))
async def itiraf_al(_, msg: Message):
    now_tr = datetime.utcnow() + timedelta(hours=3)
    gece = dtime(0, 0) <= now_tr.time() <= dtime(7, 0)

    uid = msg.from_user.id
    state = user_state.get(uid, {}).get("state")

    if state == "sehir":
        sehir = msg.text.strip().title()
        if sehir not in SEHIRLER:
            return await msg.reply("❌ Böyle bir şehir yok. Lütfen tekrar yaz (örnek: İstanbul)")
        user_state[uid] = {"state": "etiket", "sehir": sehir}
        etiket_butonu = []
        for grup in grupla(ETIKETLER, 2):
            row = [InlineKeyboardButton(f"{emoji} {etiket}", callback_data=f"etiket_{etiket}") for etiket, emoji in grup]
            etiket_butonu.append(row)
        return await msg.reply("🪪 Etiket seçin:", reply_markup=InlineKeyboardMarkup(etiket_butonu))

    if state != "yaz":
        return

    if uid not in ADMINS and kullanici_itiraf_sayisi(uid) >= LIMIT:
        return await msg.reply("❌ Günde en fazla {} itiraf gönderebilirsin.".format(LIMIT))

    sehir = user_state[uid]["sehir"]
    etiket = user_state[uid]["etiket"]
    text = msg.text.strip()
    argo_var = icerik_uyarisi(text)
    itiraf_id = yeni_itiraf_ekle(uid, text, sehir, etiket)

    ad_soyad = (msg.from_user.first_name or "") + (" " + msg.from_user.last_name if msg.from_user.last_name else "")
    kullanici_adi = f"@{msg.from_user.username}" if msg.from_user.username else "(kullanıcı adı yok)"
    bilgi = f"👤 {ad_soyad}\n🔗 {kullanici_adi}\n🆔 {uid}"

    if gece and not argo_var:
        yayin = f"""📢 *Yeni İtiraf*\n━━━━━━━━━━━━━━━\n📝 {text}\n━━━━━━━━━━━━━━━\n📍 *{sehir}* | 🪪 *{etiket}*"""
        await app.send_message(YAYIN_KANALI, yayin)

        mesaj = f"""🌙 *Gece Otomatik Yayın*\n━━━━━━━━━━━━━━━\n📝 {text}\n━━━━━━━━━━━━━━━\n📍 *{sehir}* | 🪪 *{etiket}*\n🆔 *ID:* {itiraf_id}\n{bilgi}"""
        await app.send_message(ONAY_KANALI, mesaj)

        kanal_buton = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Yayın Kanalına Git", url=YAYIN_KANAL_LINKI)]
        ])
        await msg.reply("✅ *İtirafın başarıyla yayınlandı! Devam edebilirsin.* 📢", reply_markup=kanal_buton)
        return

    mesaj = f"""📩 *Yeni İtiraf*\n━━━━━━━━━━━━━━━\n📝 {text}\n━━━━━━━━━━━━━━━\n📍 *{sehir}* | 🪪 *{etiket}*\n🆔 *ID:* {itiraf_id}\n{bilgi}"""

    if gece and argo_var:
    mesaj = f"""⚠️ *Gece Argo İçerik Tespit Edildi!*\n━━━━━━━━━━━━━━━\n📝 {text}\n━━━━━━━━━━━━━━━\n📍 *{sehir}* | 🪪 *{etiket}*\n🆔 *ID:* {itiraf_id}\n{bilgi}"""
else:
    mesaj = f"""📩 *Yeni İtiraf*\n━━━━━━━━━━━━━━━\n📝 {text}\n━━━━━━━━━━━━━━━\n📍 *{sehir}* | 🪪 *{etiket}*\n🆔 *ID:* {itiraf_id}\n{bilgi}"""

butonlar = InlineKeyboardMarkup([
    [InlineKeyboardButton("✅ Onayla", callback_data=f"onayla_{itiraf_id}"),
     InlineKeyboardButton("❌ Reddet", callback_data=f"reddet_{itiraf_id}")]
])
await app.send_message(ONAY_KANALI, mesaj, reply_markup=butonlar)

kanal_buton = InlineKeyboardMarkup([
    [InlineKeyboardButton("📢 Yayın Kanalına Git", url=YAYIN_KANAL_LINKI)]
])
await msg.reply("✅ İtirafın gönderildi. Onaylanınca paylaşılacak.", reply_markup=kanal_buton)
@app.on_callback_query()
async def callback_handler(_, q: CallbackQuery):
    data = q.data
    uid = q.from_user.id

    if data.startswith("etiket_"):
        etiket = data.replace("etiket_", "")
        if uid in user_state:
            user_state[uid]["etiket"] = etiket
            user_state[uid]["state"] = "yaz"
            await q.message.edit_text("🖍️ Şimdi itirafını yaz.")

    elif data.startswith("onayla_"):
        id = int(data.split("_")[1])
        cur.execute("SELECT text, sehir, etiket FROM itiraflar WHERE id = ?", (id,))
        row = cur.fetchone()
        if row:
            text, sehir, etiket = row
            cur.execute("UPDATE itiraflar SET onayli = 1 WHERE id = ?", (id,))
            conn.commit()
            yayin = f"""📢 *Yeni İtiraf*\n━━━━━━━━━━━━━━━\n📝 {text}\n━━━━━━━━━━━━━━━\n📍 *{sehir}* | 🪪 *{etiket}*"""
            await app.send_message(YAYIN_KANALI, yayin)
            await q.message.delete()
            await q.answer("Yayınlandı ✅")

    elif data.startswith("reddet_"):
        id = int(data.split("_")[1])
        cur.execute("DELETE FROM itiraflar WHERE id = ?", (id,))
        conn.commit()
        await q.message.delete()
        await q.answer("İtiraf reddedildi ❌")

app.run()
