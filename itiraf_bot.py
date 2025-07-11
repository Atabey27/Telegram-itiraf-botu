import os
import sqlite3
from datetime import datetime
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuer
from pyrogram.errors import ChatAdminRequired, UserNotParticipant

# .env yükle
load_dotenv()

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ONAY_KANALI_ID = int(os.getenv("ONAY_KANALI_ID"))
ADMINS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()]

app = Client("itiraf_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Veritabanı
conn = sqlite3.connect("itiraf.db", check_same_thread=False)
cur = conn.cursor()
cur.execute("""
CREATE TABLE IF NOT EXISTS kanallar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    kanal_username TEXT,
    kayit_tarihi TEXT
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS itiraflar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    kanal_username TEXT,
    itiraf TEXT,
    tarih TEXT,
    mesaj_id INTEGER
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS ban_list (
    user_id INTEGER PRIMARY KEY,
    ban_tarihi TEXT
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS yanitlar (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    itiraf_id INTEGER,
    user_id INTEGER,
    yanit TEXT,
    tarih TEXT
)
""")

try:
    cur.execute("ALTER TABLE itiraflar ADD COLUMN mesaj_id INTEGER")
    conn.commit()
except sqlite3.OperationalError:
    # Sütun zaten varsa hata verir, burada gözardı ediyoruz
    pass

conn.commit()

gecici_itiraflar = {}

def temizle(text):
    return text.replace("*", "\\*").replace("_", "\\_")

def format_user(user):
    name = f"{user.first_name or ''} {user.last_name or ''}".strip()
    uname = f"@{user.username}" if user.username else "Yok"
    return f"👤 {name}\n🆔 {user.id}\n📛 {uname}"
async def get_kanal_ve_grup_listesi():
    """
    Botun üye olduğu kanal / grupları döndürür.
    Admin olmadığı yerlere ❌ etiketi ekler.
    """
    kanal_listesi, grup_listesi = [], []

    async for dialog in app.get_dialogs():
        chat = dialog.chat
        if chat.type not in ("channel", "group", "supergroup"):
            continue

        # bot admin mi?
        try:
            member = await app.get_chat_member(chat.id, "me")
            bot_admin = member.status in ("administrator", "creator")
        except (ChatAdminRequired, UserNotParticipant):
            bot_admin = False
        except Exception:
            bot_admin = False

        ad = f"{chat.title} ({chat.username or 'private'})"
        if not bot_admin:
            ad += " ❌ Bot admin değil"

        if chat.type == "channel":
            kanal_listesi.append(f"📢 {ad}")
        else:
            grup_listesi.append(f"👥 {ad}")

    return kanal_listesi, grup_listesi
@app.on_message(filters.command("start") & filters.private)
async def start(_, msg):
    await msg.reply(
        "👋 İtiraf Botu'na Hoş Geldiniz!\n\n"
        "📌 İşte kullanabileceğiniz komutlar:\n"
        "/kanal - Kanal ekle veya silme işlemlerini yönet.\n"
        "/yardim - Tüm komutları ve yardım bilgilerini göster.\n\n"
        "📢 İtiraf göndermeye başlamak için öncelikle bir kanal eklemelisiniz.\n"
        "Örnek: /kanal komutunu kullanıp 'Yeni Kanal Ekle' seçeneğine tıklayın."
    )

@app.on_message(filters.command("yardim") & filters.private)
async def yardim(_, msg):
    await msg.reply(
        "🆘 Yardım Menüsü\n\n"
        "Kullanılabilir Komutlar:\n"
        "/start - Botu başlatır\n"
        "/kanal - Kanal ekleme/silme menüsü\n"
        "/yardim - Yardım bilgisi\n"
        "/yanitla ID mesaj - Bir itirafa gizli yanıt gönder\n"
        "/istatistik - Toplam itiraf ve kullanıcı sayısı (sadece admin)\n"
        "/ban @kullanici veya ID - Kullanıcıyı engelle (sadece admin)\n"
        "/unban @kullanici veya ID - Engeli kaldır (kendin için ve adminler için)\n"
        "/temizle gün - Eski itirafları sil (sadece admin)"
    )

@app.on_message(filters.command("kanal") & filters.private)
async def kanal_menu(_, msg):
    user_id = msg.from_user.id
    cur.execute("SELECT kanal_username FROM kanallar WHERE user_id = ?", (user_id,))
    kanallar = [row[0] for row in cur.fetchall()]
    
    buttons = []
    for k in kanallar:
        buttons.append([InlineKeyboardButton(f"❌ Sil {k}", callback_data=f"sil_{k}")])
    buttons.append([InlineKeyboardButton("➕ Yeni Kanal Ekle", callback_data="ekle")])
    
    text = "🔻 Kanal Yönetimi:\n" + "\n".join(f"- {k}" for k in kanallar) if kanallar else "Henüz kanal eklemedin."
    await msg.reply(text, reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query(filters.regex("^ekle$"))
async def yeni_kanal(_, query: CallbackQuery):
    await query.message.edit_text("📝 Eklemek istediğin kanal adını yaz. Örn: @kanalim")
    gecici_itiraflar[query.from_user.id] = "kanal_ekle"

@app.on_callback_query(filters.regex("^sil_"))
async def sil(_, query: CallbackQuery):
    user_id = query.from_user.id
    silinecek = query.data.split("_", 1)[1]
    cur.execute("DELETE FROM kanallar WHERE user_id = ? AND kanal_username = ?", (user_id, silinecek))
    conn.commit()
    await query.message.edit_text(f"❌ {silinecek} silindi. /kanal komutuyla tekrar kontrol edebilirsin.")

@app.on_message(filters.command("yanitla") & filters.private)
async def yanitla(_, msg):
    try:
        args = msg.text.split(None, 2)
        if len(args) < 3:
            return await msg.reply("⚠️ Kullanım: /yanitla 12 cevabım...")
        
        itiraf_id = int(args[1])
        yanit_text = args[2]

        cur.execute("SELECT kanal_username, mesaj_id FROM itiraflar WHERE id = ?", (itiraf_id,))
        row = cur.fetchone()
        if not row:
            return await msg.reply("⚠️ Bu ID'ye ait bir itiraf bulunamadı.")

        hedef_kanal, mesaj_id = row
        mesaj = f"📨 Yeni yanıt:\n{temizle(yanit_text)}"

        await app.send_message(hedef_kanal, mesaj, reply_to_message_id=mesaj_id)
        cur.execute("INSERT INTO yanitlar (itiraf_id, user_id, yanit, tarih) VALUES (?, ?, ?, ?)",
            (itiraf_id, msg.from_user.id, yanit_text, datetime.now().isoformat()))
        conn.commit()

        await msg.reply("✅ Cevabın gönderildi.")
    except Exception as e:
        await msg.reply(f"❌ Hata: {e}")

# --- YENİ /istatistik (sayfalandırmalı) ---
istat_sayfa = {}   # {user_id: {"k": 0, "g": 0}}

def bol(liste, n=5):
    return [liste[i:i+n] for i in range(0, len(liste), n)] or [["(Yok)"]]

@app.on_message(filters.command("istatistik") & filters.private)
async def istatistik(_, msg):
    if msg.from_user.id not in ADMINS:
        return await msg.reply("❌ Bu komut sadece adminler içindir.")

    # veritabanı sayıları
    cur.execute("SELECT COUNT(*) FROM itiraflar")
    toplam = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT user_id) FROM itiraflar")
    kullanici = cur.fetchone()[0]

    # sohbetler
    kanallar, gruplar = await get_kanal_ve_grup_listesi()
    k_pages, g_pages = bol(kanallar), bol(gruplar)
    istat_sayfa[msg.from_user.id] = {"k": 0, "g": 0}

    await msg.reply(
        _istat_metni(toplam, kullanici, k_pages, g_pages, msg.from_user.id),
        reply_markup=_istat_kp(msg.from_user.id, k_pages, g_pages),
        disable_web_page_preview=True
    )

def _istat_metni(toplam, kullanici, k_pages, g_pages, uid):
    k_i = istat_sayfa[uid]["k"]
    g_i = istat_sayfa[uid]["g"]
    return (
        f"📊 **İstatistikler**\n"
        f"📝 İtiraf: **{toplam}**\n"
        f"🙋 Kullanıcı: **{kullanici}**\n\n"
        f"📢 **Kanallar** (Sayfa {k_i+1}/{len(k_pages)}):\n" +
        "\n".join(k_pages[k_i]) + "\n\n" +
        f"👥 **Gruplar** (Sayfa {g_i+1}/{len(g_pages)}):\n" +
        "\n".join(g_pages[g_i])
    )

def _istat_kp(uid, k_pages, g_pages):
    k_i, g_i = istat_sayfa[uid]["k"], istat_sayfa[uid]["g"]
    rows = []

    # kanal sayfaları
    k_btn = []
    if k_i > 0:
        k_btn.append(InlineKeyboardButton("⬅️", callback_data=f"istat_k_{k_i-1}"))
    if k_i+1 < len(k_pages):
        k_btn.append(InlineKeyboardButton("➡️", callback_data=f"istat_k_{k_i+1}"))
    if k_btn: rows.append(k_btn)

    # grup sayfaları
    g_btn = []
    if g_i > 0:
        g_btn.append(InlineKeyboardButton("⬅️", callback_data=f"istat_g_{g_i-1}"))
    if g_i+1 < len(g_pages):
        g_btn.append(InlineKeyboardButton("➡️", callback_data=f"istat_g_{g_i+1}"))
    if g_btn: rows.append(g_btn)

    return InlineKeyboardMarkup(rows) if rows else None

@app.on_callback_query(filters.regex(r"^istat_(k|g)_(\d+)$"))
async def istat_sayfa_degistir(_, q: CallbackQuery):
    uid = q.from_user.id
    if uid not in ADMINS:
        return await q.answer("Yetkin yok", show_alert=True)

    alan, yeni = q.matches[0].group(1), int(q.matches[0].group(2))
    istat_sayfa[uid][alan] = yeni

    # verileri tazele
    cur.execute("SELECT COUNT(*) FROM itiraflar")
    toplam = cur.fetchone()[0]
    cur.execute("SELECT COUNT(DISTINCT user_id) FROM itiraflar")
    kullanici = cur.fetchone()[0]
    kanallar, gruplar = await get_kanal_ve_grup_listesi()
    k_pages, g_pages = bol(kanallar), bol(gruplar)

    await q.message.edit_text(
        _istat_metni(toplam, kullanici, k_pages, g_pages, uid),
        reply_markup=_istat_kp(uid, k_pages, g_pages)
    )

@app.on_message(filters.command("ban") & filters.private)
async def banla(_, msg):
    if msg.from_user.id not in ADMINS:
        return await msg.reply("❌ Bu komut sadece adminler içindir.")
    
    try:
        hedef_id = msg.text.split()[1]
        if hedef_id.startswith("@"):
            user = await app.get_users(hedef_id)
            uid = user.id
        else:
            uid = int(hedef_id)

        cur.execute("INSERT OR IGNORE INTO ban_list (user_id, ban_tarihi) VALUES (?, ?)", (uid, datetime.now().isoformat()))
        conn.commit()
        await msg.reply(f"🚫 {uid} engellendi.")
    except Exception as e:
        await msg.reply(f"❌ Hata: {e}")

@app.on_message(filters.command("unban") & filters.private)
async def unbanla(_, msg):
    try:
        hedef_id = msg.text.split()[1]
        if hedef_id.startswith("@"):
            user = await app.get_users(hedef_id)
            uid = user.id
        else:
            uid = int(hedef_id)
        
        # Kendi banını kaldırabilmen için izin ver
        if msg.from_user.id == uid or msg.from_user.id in ADMINS:
            cur.execute("DELETE FROM ban_list WHERE user_id = ?", (uid,))
            conn.commit()
            await msg.reply(f"✅ {uid} engeli kaldırıldı.")
        else:
            await msg.reply("❌ Bu komutu sadece adminler kullanabilir.")
    except Exception as e:
        await msg.reply(f"❌ Hata: {e}")
@app.on_message(filters.command("duyuru") & filters.private)
async def duyuru_yayinla(_, msg):
    if msg.from_user.id not in ADMINS:
        return await msg.reply("❌ Bu komut sadece adminler içindir.")

    if len(msg.text.split(None, 1)) < 2:
        return await msg.reply("⚠️ Kullanım: /duyuru mesajınız")

    duyuru = msg.text.split(None, 1)[1]
    basarili, hatali = 0, 0

    async for dialog in app.get_dialogs():
        chat = dialog.chat
        if chat.type not in ("channel", "group", "supergroup"):
            continue
        try:
            me = await app.get_chat_member(chat.id, "me")
            if me.status in ("administrator", "creator"):
                await app.send_message(chat.id, f"📣 **DUYURU**\n\n{duyuru}")
                basarili += 1
        except Exception:
            hatali += 1

    await msg.reply(f"✅ Gönderildi: {basarili}\n❌ Hata: {hatali}")
@app.on_message(filters.command("temizle") & filters.private)
async def temizle_cmd(_, msg):
    if msg.from_user.id not in ADMINS:
        return await msg.reply("❌ Bu komut sadece adminler içindir.")

    try:
        gun = int(msg.text.split()[1])
        limit_tarih = datetime.now().timestamp() - (gun * 86400)

        cur.execute("DELETE FROM itiraflar WHERE tarih < datetime(?, 'unixepoch')", (int(limit_tarih),))
        conn.commit()
        await msg.reply(f"🗑️ {gun} günden eski itiraflar silindi.")
    except:
        await msg.reply("⚠️ Kullanım: /temizle 3 gibi bir sayı gir.")

@app.on_message(filters.private & filters.text & ~filters.command([
    "start", "kanal", "yardim", "istatistik", "temizle", "yanitla", "ban", "unban"
]))
async def kanal_veya_itiraf(_, msg: Message):
    uid = msg.from_user.id

    cur.execute("SELECT 1 FROM ban_list WHERE user_id = ?", (uid,))
    if cur.fetchone() and uid not in ADMINS:
        return await msg.reply("🚫 Engellendiniz. Bu botu kullanamazsınız.")

    text = msg.text.strip()

    if gecici_itiraflar.get(uid) == "kanal_ekle":
        if not text.startswith("@"):
            return await msg.reply("⚠️ Geçersiz! '@' ile başlayan kullanıcı adı gir.")
        try:
            await app.get_chat(text)
            cur.execute("INSERT INTO kanallar (user_id, kanal_username, kayit_tarihi) VALUES (?, ?, ?)", (uid, text, datetime.now().isoformat()))
            conn.commit()
            await msg.reply(f"✅ {text} eklendi. Artık itiraf gönderebilirsin.")
        except Exception as e:
            await msg.reply(f"❌ Hata: {str(e)}")
        del gecici_itiraflar[uid]
        return

    cur.execute("SELECT kanal_username FROM kanallar WHERE user_id = ?", (uid,))
    kanallar = [row[0] for row in cur.fetchall()]
    if not kanallar:
        return await msg.reply("⚠️ Önce kanal eklemelisin. /kanal")

    try:
        metin = text[:300]
        await app.send_message(ONAY_KANALI_ID, f"🔔 Yeni itiraf geldi:\n\n{format_user(msg.from_user)}\n\n📝 İçerik:\n{metin}")
    except Exception as e:
        print(f"Onay kanalına gönderilemedi: {e}")

    gecici_itiraflar[uid] = temizle(text)
    butonlar = [[InlineKeyboardButton(k, callback_data=f"gonder_{k}")] for k in kanallar]
    butonlar.append([InlineKeyboardButton("❌ Vazgeç", callback_data="iptal")])
    await msg.reply("📤 Hangi kanala göndereyim?", reply_markup=InlineKeyboardMarkup(butonlar))

@app.on_callback_query(filters.regex("^gonder_"))
async def gonder(_, query: CallbackQuery):
    uid = query.from_user.id
    kanal = query.data.split("_", 1)[1]
    itiraf = gecici_itiraflar.get(uid)
    if not itiraf:
        return await query.answer("⏰ İtiraf süresi doldu.", show_alert=True)
    try:
        # 1. Önce veritabanına itirafı ekle (mesaj_id şimdilik None)
        tarih = datetime.now().isoformat()
        cur.execute("INSERT INTO itiraflar (user_id, kanal_username, itiraf, tarih, mesaj_id) VALUES (?, ?, ?, ?, ?)", (uid, kanal, itiraf, tarih, None))
        conn.commit()
        itiraf_id = cur.lastrowid  # Kaydın ID'si
        
        # 2. Mesajı ID'li gönder
        mesaj_metni = f"📢 İtiraf #{itiraf_id}\n\n{itiraf}"
        mesaj = await app.send_message(kanal, mesaj_metni)
        
        # 3. Mesaj ID'yi güncelle
        cur.execute("UPDATE itiraflar SET mesaj_id = ? WHERE id = ?", (mesaj.id, itiraf_id))
        conn.commit()
        
        await query.message.edit_text("✅ Gönderildi!")
        del gecici_itiraflar[uid]
    except Exception as e:
        await query.message.edit_text(f"❌ Hata: {str(e)}")
@app.on_callback_query(filters.regex("iptal"))
async def iptal(_, query: CallbackQuery):
    uid = query.from_user.id
    gecici_itiraflar.pop(uid, None)
    await query.message.edit_text("❌ Gönderim iptal edildi.")

if __name__ == "__main__":
    print("🚀 Bot başlatılıyor...")
    app.run()
