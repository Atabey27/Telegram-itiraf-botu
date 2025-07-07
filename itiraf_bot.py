import os
import random
import sqlite3
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery
from dotenv import load_dotenv

load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ONAY_KANALI = os.getenv("ONAY_KANALI_ID")
YAYIN_KANALI = os.getenv("YAYIN_KANALI_ID")
ADMINS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

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
ETIKETLER = ["Aşk", "Gizlilik", "Aldatma", "Macera", "İş Yeri"]

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
    buttons = []
    for grup in grupla(SEHIRLER, 3):
        row = [InlineKeyboardButton(f"🌏 {s}", callback_data=f"sehir_{s}") for s in grup]
        buttons.append(row)

    await msg.reply("📍 Hangi şehirden yazıyorsun?", reply_markup=InlineKeyboardMarkup(buttons))
    uid = msg.from_user.id if msg.from_user else msg.sender_chat.id
    user_state[uid] = {"state": "sehir"}

@app.on_message(filters.command("help"))
async def help(_, msg: Message):
    metin = """
🛠️ *Yönetici Komutu*

/limitayarla <sayi> – Kullanıcıların günlük itiraf gönderme limitini değiştirir.

Örnek:
`/limitayarla 5` → Günlük limit 5 olur.
"""
    await msg.reply(metin, quote=True)

@app.on_message(filters.text & ~filters.command(["start"]))
@app.on_message(filters.text & ~filters.command(["start"]))
async def itiraf_al(_, msg: Message):
    from datetime import time as dtime
    now = datetime.now().time()
    gece = dtime(0, 0) <= now <= dtime(7, 0)

    uid = msg.from_user.id if msg.from_user else msg.sender_chat.id
    if uid not in user_state or user_state[uid].get("state") != "yaz":
        return

    if uid not in ADMINS:
        if kullanici_itiraf_sayisi(uid) >= 3:
            return await msg.reply("❌ Günde en fazla 3 itiraf gönderebilirsin.")

    sehir = user_state[uid]["sehir"]
    etiket = user_state[uid]["etiket"]
    text = msg.text.strip()
    argo_var = icerik_uyarisi(text)
    itiraf_id = yeni_itiraf_ekle(uid, text, sehir, etiket)

    if msg.from_user:
        ad_soyad = msg.from_user.first_name or ""
        if msg.from_user.last_name:
            ad_soyad += " " + msg.from_user.last_name
        kullanici_adi = f"@{msg.from_user.username}" if msg.from_user.username else "(kullanıcı adı yok)"
        kullanici_id = msg.from_user.id
    else:
        ad_soyad = msg.sender_chat.title or "Anonim"
        kullanici_adi = "(anonim)"
        kullanici_id = msg.sender_chat.id

    bilgi = f"👤 {ad_soyad}\n🔗 {kullanici_adi}\n🆔 {kullanici_id}"

    if gece:
        if argo_var:
            mesaj = f"""🌙 *Gece Gelen İtiraf*
━━━━━━━━━━━━━━━
📝 {text}
━━━━━━━━━━━━━━━
📍 *{sehir}* | 🪪 *{etiket}*
🆔 *ID:* {itiraf_id}
⚠️ Argo içerik algılandı!
{bilgi}"""
            butonlar = InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Onayla", callback_data=f"onayla_{itiraf_id}"),
                 InlineKeyboardButton("❌ Reddet", callback_data=f"reddet_{itiraf_id}")]
            ])
            await app.send_message(ONAY_KANALI, mesaj, reply_markup=butonlar)
        else:
            yayin = f"""📢 *Yeni İtiraf*
━━━━━━━━━━━━━━━
📝 {text}
━━━━━━━━━━━━━━━
📍 *{sehir}* | 🪪 *{etiket}*"""
            await app.send_message(YAYIN_KANALI, yayin)

            mesaj = f"""🌙 *Gece Otomatik Yayın*
━━━━━━━━━━━━━━━
📝 {text}
━━━━━━━━━━━━━━━
📍 *{sehir}* | 🪪 *{etiket}*
🆔 *ID:* {itiraf_id}
{bilgi}"""
            await app.send_message(ONAY_KANALI, mesaj)

            await msg.reply("✅ *İtirafın başarıyla yayınlandı!* 📢", quote=True)
    else:
        mesaj = f"""📩 *Yeni İtiraf*
━━━━━━━━━━━━━━━
📝 {text}
━━━━━━━━━━━━━━━
📍 *{sehir}* | 🪪 *{etiket}*
🆔 *ID:* {itiraf_id}
{bilgi}"""

        butonlar = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Onayla", callback_data=f"onayla_{itiraf_id}"),
             InlineKeyboardButton("❌ Reddet", callback_data=f"reddet_{itiraf_id}")]
        ])

        await app.send_message(ONAY_KANALI, mesaj, reply_markup=butonlar)

        YAYIN_KANAL_LINKI = os.getenv("YAYIN_KANAL_LINKI")
        kanal_buton = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Yayın Kanalına Git", url=YAYIN_KANAL_LINKI)]
        ])
        await msg.reply("✅ İtirafın gönderildi. Onaylanınca paylaşılacak.", reply_markup=kanal_buton)
    
@app.on_message(filters.command("help"))
async def help(_, msg: Message):
    metin = """
🛠️ *Yönetici Komutu*

/limitayarla <sayi> – Kullanıcıların günlük itiraf gönderme limitini değiştirir.

Örnek:
`/limitayarla 5` → Günlük limit 5 olur.
"""
    await msg.reply(metin, quote=True)

@app.on_callback_query()
async def callback_handler(_, q: CallbackQuery):
    data = q.data
    uid = q.from_user.id

    if data.startswith("sehir_"):
        sehir = data.replace("sehir_", "")
        user_state[uid] = {"state": "etiket", "sehir": sehir}
        etiket_butonu = []
        for grup in grupla(ETIKETLER, 2):
            row = [InlineKeyboardButton(f"🪪 {e}", callback_data=f"etiket_{e}") for e in grup]
            etiket_butonu.append(row)

        await q.message.edit_text("🪪 Etiket seçin:", reply_markup=InlineKeyboardMarkup(etiket_butonu))

    elif data.startswith("etiket_"):
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
            yayin = f"""📢 *Yeni İtiraf*
━━━━━━━━━━━━━━━
📝 {text}
━━━━━━━━━━━━━━━
📍 *{sehir}* |🪪 *{etiket}*"""
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
