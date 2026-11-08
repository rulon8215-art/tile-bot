import telebot
from flask import Flask
from threading import Thread
import os
import math

app = Flask('')

@app.route('/')
def home():
    return "Bot is alive"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

bot = telebot.TeleBot(os.environ.get("TELEGRAM_BOT_TOKEN"))

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Привет, мастер! Я бот для расчета плитки. Напиши /calc чтобы начать.")

@bot.message_handler(commands=['calc'])
def calc(message):
    msg = bot.send_message(message.chat.id, "Введи площадь комнаты в кв.м (например: 20):")
    bot.register_next_step_handler(msg, get_room_area)

def get_room_area(message):
    try:
        area = float(message.text.replace(',', '.'))
        msg = bot.send_message(message.chat.id, "Введи длину плитки в метрах (например: 0,3):")
        bot.register_next_step_handler(msg, get_tile_length, area)
    except:
        bot.send_message(message.chat.id, "Ошибка! Введи число, например 20.")

def get_tile_length(message, area):
    try:
        length = float(message.text.replace(',', '.'))
        msg = bot.send_message(message.chat.id, "Введи ширину плитки в метрах (например: 0,3):")
        bot.register_next_step_handler(msg, get_tile_width, area, length)
    except:
        bot.send_message(message.chat.id, "Ошибка! Введи число, например 0.3")

def get_tile_width(message, area, length):
    try:
        width = float(message.text.replace(',', '.'))
        msg = bot.send_message(message.chat.id, "Введи процент запаса (например: 10). Введи 0, если запас не нужен.")
        bot.register_next_step_handler(msg, calculate_total, area, length, width)
    except:
        bot.send_message(message.chat.id, "Ошибка! Введи число, например 0.3")

def calculate_total(message, area, length, width):
    try:
        reserve = float(message.text.replace(',', '.'))
    except:
        bot.send_message(message.chat.id, "Ошибка! Введи число, например 10.")
        return

    tile_area = length * width
    total_tiles = (area / tile_area)
    total_with_reserve = total_tiles * (1 + reserve / 100)
    final_amount = math.ceil(total_with_reserve)

    text = f"Площадь: {area} м²\nРазмер плитки: {length} × {width} м\nЗапас: {reserve}%\n\nТебе нужно купить: {final_amount} плиток."
    bot.send_message(message.chat.id, text)

keep_alive()
bot.polling(none_stop=True)
