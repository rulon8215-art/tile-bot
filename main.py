import os
import math
import tempfile

import telebot
from PIL import Image, ImageDraw


# ==========================================
# НАСТРОЙКИ
# ==========================================

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    raise RuntimeError(
        "Не найдена переменная окружения TELEGRAM_BOT_TOKEN"
    )

bot = telebot.TeleBot(TOKEN)

# Максимальная длина стороны изображения
MAX_IMAGE_SIZE = 1800

# Отступ комнаты от краев изображения
MARGIN = 50

# Данные пользователей
user_data = {}


# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================

def parse_number(value):
    """
    Преобразует введенное значение в число.
    Поддерживает точку и запятую.
    """

    number = float(value.strip().replace(",", "."))

    if not math.isfinite(number):
        raise ValueError("Некорректное число")

    return number


def get_valid_number(message, callback, allow_zero=False):
    """
    Проверяет введенное число и передает его
    следующему обработчику.
    """

    chat_id = message.chat.id

    try:
        value = parse_number(message.text)

        if allow_zero:
            if value < 0:
                raise ValueError
        else:
            if value <= 0:
                raise ValueError

        callback(message, value)

    except (ValueError, AttributeError):
        msg = bot.send_message(
            chat_id,
            "❌ Некорректное значение.\n"
            "Введи положительное число."
        )

        bot.register_next_step_handler(
            msg,
            lambda m: get_valid_number(
                m,
                callback,
                allow_zero
            )
        )


# ==========================================
# START
# ==========================================

@bot.message_handler(commands=["start"])
def start(message):

    bot.send_message(
        message.chat.id,
        "Привет! 👋\n\n"
        "Я бот для визуализации раскладки плитки.\n\n"
        "Для начала расчета отправь команду /calc"
    )


# ==========================================
# НАЧАЛО РАСЧЕТА
# ==========================================

@bot.message_handler(commands=["calc"])
def calculate(message):

    chat_id = message.chat.id

    user_data[chat_id] = {}

    msg = bot.send_message(
        chat_id,
        "📏 Введи длину комнаты в метрах "
        "(например, 3.5):"
    )

    bot.register_next_step_handler(
        msg,
        room_length
    )


# ==========================================
# ДЛИНА КОМНАТЫ
# ==========================================

def room_length(message):

    def save(message, value):

        user_data[message.chat.id]["room_length"] = value

        msg = bot.send_message(
            message.chat.id,
            "📏 Введи ширину комнаты в метрах:"
        )

        bot.register_next_step_handler(
            msg,
            room_width
        )

    get_valid_number(message, save)


# ==========================================
# ШИРИНА КОМНАТЫ
# ==========================================

def room_width(message):

    def save(message, value):

        user_data[message.chat.id]["room_width"] = value

        msg = bot.send_message(
            message.chat.id,
            "🧱 Введи длину плитки в метрах:"
        )

        bot.register_next_step_handler(
            msg,
            tile_length
        )

    get_valid_number(message, save)


# ==========================================
# ДЛИНА ПЛИТКИ
# ==========================================

def tile_length(message):

    def save(message, value):

        user_data[message.chat.id]["tile_length"] = value

        msg = bot.send_message(
            message.chat.id,
            "🧱 Введи ширину плитки в метрах:"
        )

        bot.register_next_step_handler(
            msg,
            tile_width
        )

    get_valid_number(message, save)


# ==========================================
# ШИРИНА ПЛИТКИ
# ==========================================

def tile_width(message):

    def save(message, value):

        user_data[message.chat.id]["tile_width"] = value

        msg = bot.send_message(
            message.chat.id,
            "↔️ Введи ширину шва между плитками "
            "в миллиметрах (например, 2):"
        )

        bot.register_next_step_handler(
            msg,
            seam_width
        )

    get_valid_number(message, save)


# ==========================================
# ШИРИНА ШВА
# ==========================================

def seam_width(message):

    def save(message, value):

        chat_id = message.chat.id

        user_data[chat_id]["seam_width"] = value

        bot.send_message(
            chat_id,
            "⏳ Рассчитываю количество плиток "
            "и создаю изображение..."
        )

        try:
            generate_image(chat_id)

        except Exception as error:
            bot.send_message(
                chat_id,
                f"❌ Ошибка: {error}"
            )

        finally:
            user_data.pop(chat_id, None)

    get_valid_number(
        message,
        save,
        allow_zero=True
    )


# ==========================================
# РАСЧЕТ КОЛИЧЕСТВА ПЛИТОК
# ==========================================

def calculate_tiles(room_size, tile_size, seam):
    """
    Рассчитывает количество плиток вдоль одной стороны.

    Шаг сетки = размер плитки + ширина шва.

    Плитки, частично попадающие в комнату,
    тоже учитываются.
    """

    step = tile_size + seam

    return math.ceil(room_size / step)


# ==========================================
# СОЗДАНИЕ ИЗОБРАЖЕНИЯ
# ==========================================

def generate_image(chat_id):

    data = user_data[chat_id]

    room_length = data["room_length"]
    room_width = data["room_width"]

    tile_length = data["tile_length"]
    tile_width = data["tile_width"]

    # Перевод шва из миллиметров в метры
    seam = data["seam_width"] / 1000

    # Шаг между одинаковыми точками соседних плиток
    step_x = tile_length + seam
    step_y = tile_width + seam

    # Количество плиток по каждой стороне
    count_x = calculate_tiles(
        room_length,
        tile_length,
        seam
    )

    count_y = calculate_tiles(
        room_width,
        tile_width,
        seam
    )

    # Общее количество плиток
    total_tiles = count_x * count_y

    # ======================================
    # МАСШТАБ ИЗОБРАЖЕНИЯ
    # ======================================

    available_size = MAX_IMAGE_SIZE - 2 * MARGIN

    scale = min(
        available_size / room_length,
        available_size / room_width
    )

    room_px_length = max(
        1,
        round(room_length * scale)
    )

    room_px_width = max(
        1,
        round(room_width * scale)
    )

    image_width = room_px_length + 2 * MARGIN
    image_height = room_px_width + 2 * MARGIN

    # Белый фон
    image = Image.new(
        "RGB",
        (image_width, image_height),
        "white"
    )

    draw = ImageDraw.Draw(image)

    # Координаты комнаты
    left = MARGIN
    top = MARGIN

    right = left + room_px_length
    bottom = top + room_px_width

    # ======================================
    # РИСОВАНИЕ СЕТКИ ПЛИТОК
    # ======================================

    gray = (150, 150, 150)

    line_width = max(
        1,
        round(scale * 0.0015)
    )

    # Вертикальные линии
    for i in range(count_x + 1):

        x = i * step_x

        if x > room_length:
            break

        pixel_x = left + round(x * scale)

        draw.line(
            [
                (pixel_x, top),
                (pixel_x, bottom)
            ],
            fill=gray,
            width=line_width
        )

    # Горизонтальные линии
    for i in range(count_y + 1):

        y = i * step_y

        if y > room_width:
            break

        pixel_y = top + round(y * scale)

        draw.line(
            [
                (left, pixel_y),
                (right, pixel_y)
            ],
            fill=gray,
            width=line_width
        )

    # ======================================
    # ЧЕРНАЯ РАМКА КОМНАТЫ
    # ======================================

    draw.rectangle(
        [
            (left, top),
            (right - 1, bottom - 1)
        ],
        outline="black",
        width=3
    )

    # ======================================
    # СОХРАНЕНИЕ ВРЕМЕННОГО ФАЙЛА
    # ======================================

    temp_path = None

    try:

        with tempfile.NamedTemporaryFile(
            suffix=".png",
            delete=False
        ) as temp:

            temp_path = temp.name

        image.save(temp_path, format="PNG")

        # ==================================
        # ТЕКСТ РЕЗУЛЬТАТА
        # ==================================

        caption = (
            "✅ РАСКЛАДКА ПЛИТКИ ГОТОВА!\n\n"

            f"📐 Размер комнаты:\n"
            f"{room_length} × {room_width} м\n\n"

            f"🧱 Размер плитки:\n"
            f"{tile_length} × {tile_width} м\n\n"

            f"↔️ Ширина шва: {data['seam_width']} мм\n\n"

            f"📊 КОЛИЧЕСТВО ПЛИТОК:\n\n"

            f"По длине: {count_x} шт.\n"
            f"По ширине: {count_y} шт.\n\n"

            f"🔢 ОБЩЕЕ КОЛИЧЕСТВО: "
            f"{total_tiles} шт.\n\n"

            "Учитываются также частично обрезанные плитки."
        )

        # Отправка изображения
        with open(temp_path, "rb") as photo:

            bot.send_photo(
                chat_id,
                photo,
                caption=caption
            )

    finally:

        # Удаление временного файла
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


# ==========================================
# ЗАПУСК БОТА
# ==========================================
import os
import math
import tempfile
import telebot
from PIL import Image, ImageDraw
from flask import Flask
from threading import Thread

# ==========================================
# НАСТРОЙКИ
# ==========================================
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("Не найдена переменная окружения TELEGRAM_BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)
MAX_IMAGE_SIZE = 1800
MARGIN = 50
user_data = {}

# ==========================================
# FLASK (Чтобы Render не усыплял бота)
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive"

def run_flask():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ==========================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==========================================
def parse_number(value):
    number = float(value.strip().replace(",", "."))
    if not math.isfinite(number):
        raise ValueError("Некорректное число")
    return number

def get_valid_number(message, callback, allow_zero=False):
    chat_id = message.chat.id
    try:
        value = parse_number(message.text)
        if allow_zero:
            if value < 0: raise ValueError
        else:
            if value <= 0: raise ValueError
        callback(message, value)
    except (ValueError, AttributeError):
        msg = bot.send_message(chat_id, "❌ Некорректное значение.\nВведи положительное число.")
        bot.register_next_step_handler(msg, lambda m: get_valid_number(m, callback, allow_zero))

# ==========================================
# ХЕНДЛЕРЫ
# ==========================================
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(message.chat.id, "Привет! 👋\n\nЯ бот для визуализации раскладки плитки.\n\nДля начала расчета отправь команду /calc")

@bot.message_handler(commands=["calc"])
def calculate(message):
    chat_id = message.chat.id
    user_data[chat_id] = {}
    msg = bot.send_message(chat_id, "📏 Введи длину комнаты в метрах (например, 3.5):")
    bot.register_next_step_handler(msg, room_length)

def room_length(message):
    def save(message, value):
        user_data[message.chat.id]["room_length"] = value
        msg = bot.send_message(message.chat.id, "📏 Введи ширину комнаты в метрах:")
        bot.register_next_step_handler(msg, room_width)
    get_valid_number(message, save)

def room_width(message):
    def save(message, value):
        user_data[message.chat.id]["room_width"] = value
        msg = bot.send_message(message.chat.id, "🧱 Введи длину плитки в метрах:")
        bot.register_next_step_handler(msg, tile_length)
    get_valid_number(message, save)

def tile_length(message):
    def save(message, value):
        user_data[message.chat.id]["tile_length"] = value
        msg = bot.send_message(message.chat.id, "🧱 Введи ширину плитки в метрах:")
        bot.register_next_step_handler(msg, tile_width)
    get_valid_number(message, save)

def tile_width(message):
    def save(message, value):
        user_data[message.chat.id]["tile_width"] = value
        msg = bot.send_message(message.chat.id, "↔️ Введи ширину шва между плитками в миллиметрах (например, 2):")
        bot.register_next_step_handler(msg, seam_width)
    get_valid_number(message, save)

def seam_width(message):
    def save(message, value):
        chat_id = message.chat.id
        user_data[chat_id]["seam_width"] = value
        bot.send_message(chat_id, "⏳ Рассчитываю количество плиток и создаю изображение...")
        try:
            generate_image(chat_id)
        except Exception as error:
            bot.send_message(chat_id, f"❌ Ошибка: {error}")
        finally:
            user_data.pop(chat_id, None)
    get_valid_number(message, save, allow_zero=True)

# ==========================================
# ЛОГИКА РАСЧЕТА И РИСОВАНИЯ
# ==========================================
def calculate_tiles(room_size, tile_size, seam):
    step = tile_size + seam
    return math.ceil(room_size / step)

def generate_image(chat_id):
    data = user_data[chat_id]
    room_length = data["room_length"]
    room_width = data["room_width"]
    tile_length = data["tile_length"]
    tile_width = data["tile_width"]
    seam = data["seam_width"] / 1000

    step_x = tile_length + seam
    step_y = tile_width + seam

    count_x = calculate_tiles(room_length, tile_length, seam)
    count_y = calculate_tiles(room_width, tile_width, seam)
    total_tiles = count_x * count_y

    available_size = MAX_IMAGE_SIZE - 2 * MARGIN
    scale = min(available_size / room_length, available_size / room_width)

    room_px_length = max(1, round(room_length * scale))
    room_px_width = max(1, round(room_width * scale))

    image_width = room_px_length + 2 * MARGIN
    image_height = room_px_width + 2 * MARGIN

    image = Image.new("RGB", (image_width, image_height), "white")
    draw = ImageDraw.Draw(image)

    left = MARGIN
    top = MARGIN
    right = left + room_px_length
    bottom = top + room_px_width

    gray = (150, 150, 150)
    line_width = max(1, round(scale * 0.0015))

    for i in range(count_x + 1):
        x = i * step_x
        if x > room_length: break
        pixel_x = left + round(x * scale)
        draw.line([(pixel_x, top), (pixel_x, bottom)], fill=gray, width=line_width)

    for i in range(count_y + 1):
        y = i * step_y
        if y > room_width: break
        pixel_y = top + round(y * scale)
        draw.line([(left, pixel_y), (right, pixel_y)], fill=gray, width=line_width)

    draw.rectangle([(left, top), (right - 1, bottom - 1)], outline="black", width=3)

    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temp:
            temp_path = temp.name
        image.save(temp_path, format="PNG")

        caption = (
            "✅ РАСКЛАДКА ПЛИТКИ ГОТОВА!\n\n"
            f"📐 Размер комнаты:\n{room_length} × {room_width} м\n\n"
            f"🧱 Размер плитки:\n{tile_length} × {tile_width} м\n\n"
            f"↔️ Ширина шва: {data['seam_width']} мм\n\n"
            f"📊 КОЛИЧЕСТВО ПЛИТОК:\n\n"
            f"По длине: {count_x} шт.\n"
            f"По ширине: {count_y} шт.\n\n"
            f"🔢 ОБЩЕЕ КОЛИЧЕСТВО: {total_tiles} шт.\n\n"
            "Учитываются также частично обрезанные плитки."
        )

        with open(temp_path, "rb") as photo:
            bot.send_photo(chat_id, photo, caption=caption)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

# ==========================================
# ЗАПУСК
# ==========================================
if __name__ == "__main__":
    print("Бот запущен!")
    keep_alive()
    bot.infinity_polling(skip_pending=True, timeout=30)
if __name__ == "__main__":

    print("Бот запущен!")

    bot.infinity_polling(
        skip_pending=True,
        timeout=30
    )
