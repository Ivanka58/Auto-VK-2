import os
import telebot
from telebot import types
from flask import Flask
import threading
from dotenv import load_dotenv
import time

# Selenium для имитации браузера
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import undetected_chromedriver as uc

load_dotenv()

# --- ЗАГРУЗКА ПЕРЕМЕННЫХ ОКРУЖЕНИЯ ---
TOKEN = os.getenv("TG_TOKEN")
VK_LOGIN = os.getenv("VK_LOGIN")          # Номер телефона или email от VK
VK_PASSWORD = os.getenv("VK_PASSWORD")    # Пароль от VK
GROUPS_RAW = os.getenv("GROUP_IDS", "")
GROUP_IDS = [int(i.strip()) for i in GROUPS_RAW.split(",") if i.strip()]

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Хранилище данных пользователя
user_data = {}

# ------------------- ФУНКЦИЯ ПОСТИНГА В VK -------------------
def post_to_vk_group(photo_paths, message_text, group_id):
    """
    Публикует пост в VK через браузер, имитируя действия человека.
    group_id — целое число (ID группы, может быть с минусом).
    """
    chrome_options = Options()
    chrome_options.add_argument("--headless")                # Без окна
    chrome_options.add_argument("--no-sandbox")             # Для Linux
    chrome_options.add_argument("--disable-dev-shm-usage")  # Для Render
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")

    driver = None
    try:
        driver = uc.Chrome(options=chrome_options)
        driver.get("https://vk.com")
        time.sleep(3)

        # Авторизация
        driver.find_element(By.NAME, "login").send_keys(VK_LOGIN)
        driver.find_element(By.NAME, "password").send_keys(VK_PASSWORD)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(5)

        # Переход в группу (ID без минуса)
        group_id_clean = str(group_id).replace("-", "")
        driver.get(f"https://vk.com/club{group_id_clean}")
        time.sleep(5)

        # Открыть форму предложки
        try:
            driver.find_element(By.XPATH, "//button[contains(@class, 'suggest')]").click()
        except:
            driver.find_element(By.XPATH, "//div[contains(@class, 'post_field')]").click()
        time.sleep(2)

        # Загрузка фото
        for path in photo_paths:
            driver.find_element(By.XPATH, "//input[@type='file']").send_keys(os.path.abspath(path))
            time.sleep(2)

        # Ввод текста
        textarea = driver.find_element(By.XPATH, "//div[@role='textbox']")
        textarea.click()
        textarea.send_keys(message_text)

        # Отправка
        driver.find_element(By.XPATH, "//button[contains(@class, 'submit')]").click()
        time.sleep(5)

        return f"✅ Пост в группу {group_id} отправлен на модерацию/опубликован."

    except Exception as e:
        return f"❌ Ошибка в группе {group_id}: {str(e)[:200]}"
    finally:
        if driver:
            driver.quit()

def send_to_vk_groups(message_text, photo_paths):
    results = []
    for gid in GROUP_IDS:
        results.append(post_to_vk_group(photo_paths, message_text, gid))
        time.sleep(30)  # Защита от флуда
    return "\n".join(results)

# ------------------- ОБЫЧНАЯ ТЕЛЕГРАМ-ЛОГИКА -------------------
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

@bot.message_handler(commands=['start', 'auto'])
def send_welcome(message):
    chat_id = message.chat.id
    user_data[chat_id] = {'photos': [], 'text': None}
    bot.send_message(chat_id, "Привет! Чтобы отправить объявление в ВК, нажми на кнопку 👇",
                     reply_markup=get_start_kb())

@bot.message_handler(func=lambda m: m.text == "Отправить объявление")
def ask_photo(message):
    chat_id = message.chat.id
    user_data[chat_id] = {'photos': [], 'text': None}
    bot.send_message(chat_id, "Отправь фото (до 10 шт.)", reply_markup=types.ReplyKeyboardRemove())

@bot.message_handler(content_types=['photo'])
def handle_photos(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        user_data[chat_id] = {'photos': [], 'text': None}
    if len(user_data[chat_id]['photos']) < 10:
        file_id = message.photo[-1].file_id
        user_data[chat_id]['photos'].append(file_id)
        bot.send_message(chat_id, f"Фото {len(user_data[chat_id]['photos'])}/10. Можете отправить ещё или нажмите кнопку.",
                         reply_markup=get_finish_photos_kb())
    else:
        bot.send_message(chat_id, "Лимит 10 фото. Нажмите кнопку.", reply_markup=get_finish_photos_kb())

@bot.message_handler(func=lambda m: m.text == "Закончить отправку фото ✅")
def finish_photos_step(message):
    chat_id = message.chat.id
    if chat_id not in user_data or not user_data[chat_id]['photos']:
        bot.send_message(chat_id, "Нет ни одного фото!")
        return
    bot.send_message(chat_id, "Теперь отправьте текст объявления.", reply_markup=types.ReplyKeyboardRemove())
    bot.register_next_step_handler(message, get_text)

def get_text(message):
    chat_id = message.chat.id
    if not message.text:
        bot.send_message(chat_id, "Нужен текст!")
        bot.register_next_step_handler(message, get_text)
        return
    user_data[chat_id]['text'] = message.text
    bot.send_message(chat_id, "Объявление готово. Подтверждаете?", reply_markup=get_confirm_kb())

@bot.message_handler(func=lambda m: m.text in ["Готово ☑️", "Изменить"])
def confirm_step(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        return
    if message.text == "Изменить":
        ask_photo(message)
        return

    bot.send_message(chat_id, "Публикую во все группы...")
    data = user_data[chat_id]
    paths = []

    try:
        # Скачиваем фото из Telegram
        for i, photo_id in enumerate(data['photos']):
            file_info = bot.get_file(photo_id)
            downloaded_file = bot.download_file(file_info.file_path)
            path = f"temp_{chat_id}_{i}.jpg"
            with open(path, 'wb') as f:
                f.write(downloaded_file)
            paths.append(path)

        # Отправляем в VK через Selenium
        report = send_to_vk_groups(data['text'], paths)

        # Чистим временщики
        for p in paths:
            if os.path.exists(p):
                os.remove(p)

        bot.send_message(chat_id, report, reply_markup=get_start_kb())
        user_data[chat_id] = {'photos': [], 'text': None}

    except Exception as e:
        for p in paths:
            if os.path.exists(p):
                os.remove(p)
        bot.send_message(chat_id, f"Критическая ошибка: {e}\nОбратитесь к администратору.", reply_markup=get_start_kb())

# ------------------- ФЛАСК ДЛЯ RENDER -------------------
@app.route('/')
def health():
    return "Bot is alive", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# ------------------- ЗАПУСК -------------------
if __name__ == '__main__':
    threading.Thread(target=run_flask, daemon=True).start()
    bot.infinity_polling()
