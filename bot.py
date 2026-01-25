import os
import telebot
from telebot import types
from flask import Flask
import threading
from dotenv import load_dotenv
from vk_worker import send_to_vk_groups

load_dotenv()

# Настройки
TOKEN = os.getenv("TG_TOKEN")
VK_TOKEN = os.getenv("VK_TOKEN")
GROUPS_RAW = os.getenv("GROUP_IDS", "")
GROUP_IDS = [int(i.strip()) for i in GROUPS_RAW.split(",") if i.strip()]

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Хранилище: {chat_id: {'photos': [], 'text': ''}}
user_data = {}

# --- СЕРВЕР ДЛЯ RENDER ---
@app.route('/')
def health():
    return "Bot is alive", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# --- КЛАВИАТУРЫ ---

def get_start_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("Отправить объявление"))
    return kb

def get_finish_photos_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("Закончить отправку фото ✅"))
    return kb

def get_confirm_kb():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(types.KeyboardButton("Готово ☑️"), types.KeyboardButton("Изменить"))
    return kb

# --- КОМАНДЫ ---

@bot.message_handler(commands=['start', 'auto'])
def send_welcome(message):
    chat_id = message.chat.id
    user_data[chat_id] = {'photos': [], 'text': None}
    bot.send_message(
        chat_id, 
        "Привет! Чтобы отправить объявление в ВК, нажмите на кнопку ниже 👇", 
        reply_markup=get_start_kb()
    )

@bot.message_handler(func=lambda m: m.text == "Отправить объявление")
def ask_photo(message):
    chat_id = message.chat.id
    user_data[chat_id] = {'photos': [], 'text': None}
    bot.send_message(
        chat_id, 
        "Отправьте фотографию(ии) вашего объявления (до 10 шт.)", 
        reply_markup=types.ReplyKeyboardRemove()
    )

# Обработка фото
@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        user_data[chat_id] = {'photos': [], 'text': None}

    if len(user_data[chat_id]['photos']) < 10:
        file_id = message.photo[-1].file_id
        user_data[chat_id]['photos'].append(file_id)
        
        bot.send_message(
            chat_id, 
            f"Фото получено ({len(user_data[chat_id]['photos'])}/10). Можете отправить еще или нажмите кнопку 👇", 
            reply_markup=get_finish_photos_kb()
        )
    else:

        bot.send_message(chat_id, "Достигнут лимит 10 фото. Нажмите кнопку 👇", reply_markup=get_finish_photos_kb())

# Нажатие на "Закончить отправку фото ✅"
@bot.message_handler(func=lambda m: m.text == "Закончить отправку фото ✅")
def finish_photos_step(message):
    chat_id = message.chat.id
    if chat_id not in user_data or not user_data[chat_id]['photos']:
        bot.send_message(chat_id, "Вы не отправили ни одного фото!")
        return
    
    bot.send_message(chat_id, "Теперь отправьте текст к вашему объявлению", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, get_text)

def get_text(message):
    chat_id = message.chat.id
    if not message.text:
        bot.send_message(chat_id, "Нужен текст объявления!")
        bot.register_next_step_handler(message, get_text)
        return
    
    user_data[chat_id]['text'] = message.text
    bot.send_message(
        chat_id, 
        "Объявление готово! Вы уверены? Если нужно что-то изменить, нажмите кнопку ниже", 
        reply_markup=get_confirm_kb()
    )

# Кнопки Готово / Изменить
@bot.message_handler(func=lambda m: m.text in ["Готово ☑️", "Изменить"])
def confirm_step(message):
    chat_id = message.chat.id
    if chat_id not in user_data: return

    if message.text == "Изменить":
        ask_photo(message)
        return

    # Процесс публикации
    if not VK_TOKEN:
        bot.send_message(chat_id, "Ключ вк не подключен!! Обратись к администратору @Ivanka58", reply_markup=get_start_kb())
        return

    bot.send_message(chat_id, "Начинаю процесс отправки в ВК... подождите.")

    paths = []
    try:
        data = user_data[chat_id]
        
        # Скачиваем все фото из Телеграма
        for i, photo_id in enumerate(data['photos']):
            file_info = bot.get_file(photo_id)
            downloaded_file = bot.download_file(file_info.file_path)
            path = f"temp_{chat_id}_{i}.jpg"
            with open(path, 'wb') as f:
                f.write(downloaded_file)
            paths.append(path)

        # Вызываем ВК-воркера (передаем список путей)
        report = send_to_vk_groups(VK_TOKEN, GROUP_IDS, data['text'], paths)

        # Удаляем временные файлы
        for p in paths:
            if os.path.exists(p):
                os.remove(p)

        bot.send_message(chat_id, report, reply_markup=get_start_kb())
        user_data[chat_id] = {'photos': [], 'text': None}

    except Exception as e:
        # Чистим файлы в случае ошибки
        for p in paths:
            if os.path.exists(p): os.remove(p)
        bot.send_message(chat_id, f"Ошибка: {e}\nОбратитесь к @Ivanka58", reply_markup=get_start_kb())

if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling()
