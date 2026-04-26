import json
import re
import os
from pathlib import Path

from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters


# 🔐 загружаем переменные из .env
load_dotenv()

# берём токен из .env
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("❌ BOT_TOKEN не найден. Проверь файл .env")


# путь к базе кодов
CODES_FILE = Path("codes.json")


CYR_TO_LAT = str.maketrans({
    "А": "A", "В": "B", "Е": "E", "К": "K",
    "М": "M", "Н": "H", "О": "O", "Р": "P",
    "С": "C", "Т": "T", "У": "Y", "Х": "X",
    "а": "A", "в": "B", "е": "E", "к": "K",
    "м": "M", "н": "H", "о": "O", "р": "P",
    "с": "C", "т": "T", "у": "Y", "х": "X",
})


def load_codes():
    with open(CODES_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


CODES = load_codes()


def normalize_plate(text: str) -> str:
    text = text.strip().upper()
    text = text.translate(CYR_TO_LAT)
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text)
    return text


def detect_russia(plate: str):
    clean = re.sub(r"[\s-]", "", plate)
    match = re.search(r"(\d{2,3})$", clean)

    if not match:
        return []

    code = match.group(1)
    ru_codes = CODES.get("RU", {}).get("codes", {})
    location = ru_codes.get(code, f"Region {code}")

    return [{
        "country": "Russia",
        "location": location,
        "code": code,
        "source": "цифровой код региона"
    }]


def detect_by_prefix(plate: str):
    match = re.match(r"^([A-Z]{1,3})", plate)

    if not match:
        return []

    prefix = match.group(1)
    matches = []
    seen = set()

    max_length = min(3, len(prefix))

    for length in range(max_length, 0, -1):
        code = prefix[:length]

        for country_key, country_data in CODES.items():
            if country_key == "RU":
                continue

            codes = country_data.get("codes", {})

            if code in codes:
                unique_key = (country_key, code)

                if unique_key in seen:
                    continue

                seen.add(unique_key)

                matches.append({
                    "country": country_data.get("country", country_key),
                    "location": codes[code],
                    "code": code,
                    "source": "буквенный префикс"
                })

    return matches

def detect_plate(text: str):
    plate = normalize_plate(text)

    results = []
    results.extend(detect_russia(plate))
    results.extend(detect_by_prefix(plate))

    return results


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚗 Пришли номер машины.\n\n"
        "Примеры:\n"
        "LJ AB-123\n"
        "B AB 1234\n"
        "ZG 1234 AB\n"
        "BG 123-AB\n"
        "A123BC77\n"
        "О344КР34"
    )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    plate = normalize_plate(text)
    results = detect_plate(text)

    if results:
        lines = [f"Номер: {plate}", "Возможные варианты:"]

        for item in results:
            lines.append(
                f"- {item['country']}: {item['location']} / "
                f"код {item['code']} ({item['source']})"
            )

        await update.message.reply_text("\n".join(lines))
    else:
        await update.message.reply_text("Не смог определить номер 😕")


def main():
    print("Bot started...")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling()


if __name__ == "__main__":
    main()