import asyncio
import re
import requests
from telethon import TelegramClient
from flask import Flask
from threading import Thread

# === 🔧 Настройки ===
API_ID = 21610900
API_HASH = "ad608e8630bdba3a4e4b5ff3d929c476"
BOT_TOKEN = "7539175415:AAECIfHrar6SEygyx9hBhQd087kNgTm1TeA"
TARGET_CHAT_ID = -1002383425682  # твой канал

# Каналы для мониторинга
CHANNELS = {
    "plasma": "https://t.me/PLASMA_ALERTS",
    "solana": "https://t.me/PumpFunNewPools",
    "trx": "https://t.me/SunPumpNewDeploys",
    "bsc": "https://t.me/FourMemeNewTokens"
}

# === Flask для работы 24/7 на Replit ===
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run_server():
    app.run(host='0.0.0.0', port=8080)

Thread(target=run_server).start()

# === Состояние отправленных сообщений ===
sent_messages = {}  # key = "<tag>:<ticker>", value = {"message_id": int, "count": int}

client = TelegramClient("userbot_session", API_ID, API_HASH)

# === 📩 Отправка или обновление сообщений ===
def send_or_update_message(tag: str, display_name: str, count: int, twitter_url=None, telegram_url=None):
    key = f"{tag}:{display_name.lower()}"
    text = f"⚡ [{tag.upper()}] Найден повтор!\n🪙 {display_name} — встречается {count} раза(ов)\n"

    if tag != "plasma":
        text += f"🐦 Twitter: {twitter_url or 'Not available'}\n📱 Telegram: {telegram_url or 'Not available'}"
    else:
        text += f"🐦 Twitter: {twitter_url or 'Not available'}"

    if key in sent_messages:
        old_msg = sent_messages[key]
        if count != old_msg["count"]:
            resp = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/editMessageText",
                json={"chat_id": TARGET_CHAT_ID, "message_id": old_msg["message_id"], "text": text}
            )
            print(f"✏️ Обновлено сообщение для {display_name} ({tag}): {resp.status_code}")
            if resp.status_code == 200:
                sent_messages[key]["count"] = count
    else:
        resp = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": TARGET_CHAT_ID, "text": text}
        )
        print(f"📤 Новое сообщение отправлено для {display_name} ({tag}): {resp.status_code}")
        if resp.status_code == 200:
            data = resp.json()
            sent_messages[key] = {
                "message_id": data["result"]["message_id"],
                "count": count
            }

# === 📊 Парсеры ===
def parse_plasma_message(msg):
    text = (msg.message or msg.raw_text or "")
    symbol_match = re.search(r"Symbol\s*:\s*(.+)", text, re.IGNORECASE)
    symbol = symbol_match.group(1).strip() if symbol_match else None

    twitter_url = None
    if hasattr(msg, "buttons") and msg.buttons:
        for row in msg.buttons:
            for button in row:
                if hasattr(button, "url") and button.url and ("x.com" in button.url or "twitter.com" in button.url):
                    twitter_url = button.url
                    break
            if twitter_url:
                break

    return symbol, twitter_url, None

def parse_solana_message(msg):
    lines = (msg.message or "").splitlines()
    if len(lines) >= 10:
        token = lines[9].split("|")[0].strip()
        twitter = next((l.split(":", 1)[1].strip() for l in lines if "Twitter" in l), None)
        telegram = next((l.split(":", 1)[1].strip() for l in lines if "Telegram" in l), None)
        return token, twitter, telegram
    return None, None, None

def parse_trx_message(msg):
    lines = (msg.message or "").splitlines()
    if lines:
        token = lines[0].split()[1]
        twitter = next((l.split(":", 1)[1].strip() for l in lines if "Twitter" in l), None)
        telegram = next((l.split(":", 1)[1].strip() for l in lines if "Telegram" in l), None)
        return token, twitter, telegram
    return None, None, None

def parse_bsc_message(msg):
    return parse_trx_message(msg)

PARSERS = {
    "plasma": parse_plasma_message,
    "solana": parse_solana_message,
    "trx": parse_trx_message,
    "bsc": parse_bsc_message
}

# === 🔁 Основной цикл ===
async def monitor_channel(tag, url):
    channel = await client.get_entity(url)
    messages = await client.get_messages(channel, limit=40)

    counts = {}
    details = {}

    for msg in messages:
        token, twitter, telegram = PARSERS[tag](msg)
        if token:
            token_norm = token.lower().strip()
            counts[token_norm] = counts.get(token_norm, 0) + 1
            if token_norm not in details:
                details[token_norm] = (token, twitter, telegram)

    print(f"📊 [{tag}] Найденные токены:", counts)

    for token_norm, count in counts.items():
        if count >= 2:
            token, twitter, telegram = details[token_norm]
            send_or_update_message(tag, token, count, twitter, telegram)

async def main():
    await client.start()
    print("✅ Userbot авторизован и каждые 10 секунд проверяет каналы...")

    while True:
        for tag, url in CHANNELS.items():
            try:
                await monitor_channel(tag, url)
            except Exception as e:
                print(f"[❌] Ошибка при проверке {tag}: {e}")
        await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(main())
