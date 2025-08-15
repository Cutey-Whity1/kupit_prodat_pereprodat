from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from logic import DatabaseManager
import schedule
import threading
import time
import os
import sqlite3
from config import API_TOKEN, DATABASE

bot = TeleBot(API_TOKEN)
manager = DatabaseManager(DATABASE)

def check_prizes_available():
    """Проверяет, есть ли доступные призы"""
    conn = sqlite3.connect(DATABASE)
    with conn:
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM prizes WHERE used = 0')
        return cur.fetchone()[0] > 0

def gen_markup(prize_id):
    """Создает кнопку 'Получить!' для приза"""
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("Получить!", callback_data=str(prize_id)))
    return markup

def send_message():
    try:
        # Проверяем доступные призы
        prize = manager.get_random_prize()
        if not prize:
            print("Нет доступных призов!")
            return
            
        prize_id, img_name = prize[:2]
        print(f"Пытаемся отправить приз {prize_id}: {img_name}")  # Логирование
        
        # Проверяем существование файла
        hidden_img_path = os.path.join('hidden_img', img_name)
        if not os.path.exists(hidden_img_path):
            print(f"Файл {hidden_img_path} не найден!")
            return
            
        # Получаем список пользователей
        users = manager.get_users()
        if not users:
            print("Нет пользователей для отправки!")
            return
            
        print(f"Отправляем {img_name} {len(users)} пользователям...")
        
        # Отправка всем пользователям
        success_count = 0
        for user_id in users:
            try:
                with open(hidden_img_path, 'rb') as photo:
                    bot.send_photo(
                        chat_id=user_id,
                        photo=photo,
                        caption="Угадай, что это?",
                        reply_markup=gen_markup(prize_id)
                    )
                success_count += 1
            except Exception as e:
                print(f"Ошибка отправки пользователю {user_id}: {str(e)}")
                
        print(f"Успешно отправлено: {success_count}/{len(users)}")
        manager.mark_prize_used(prize_id)
        
    except Exception as e:
        print(f"Критическая ошибка в send_message: {str(e)}")

def schedule_thread():
    schedule.every(5).seconds.do(send_message)  # Здесь можно изменить периодичность
    while True:
        schedule.run_pending()
        time.sleep(1)

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.chat.id
    if user_id in manager.get_users():
        bot.reply_to(message, "Ты уже зарегистрирован!")
    else:
        manager.add_user(user_id, message.from_user.username)
        bot.reply_to(message, """Привет! Добро пожаловать! 
Тебя успешно зарегистрировали!
Каждый час тебе будут приходить новые картинки и у тебя будет шанс их получить!
Для этого нужно быстрее всех нажать на кнопку 'Получить!'

Только три первых пользователя получат картинку!)""")

@bot.message_handler(commands=['rating'])
def handle_rating(message):
    res = manager.get_rating() 
    res = [f'| @{x[1]:<11} | {x[2]:<11}|' for x in res]
    res = '\n'.join(res)
    res = f'|USER_NAME    |COUNT_PRIZE|\n{"_"*26}\n' + res
    bot.send_message(message.chat.id, res)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        prize_id = call.data
        user_id = call.from_user.id
        
        print(f"Пользователь {user_id} нажал на приз {prize_id}")  # Логирование
        
        # Проверяем количество победителей
        winners_count = manager.get_winners_count(prize_id)
        if winners_count >= 3:
            bot.answer_callback_query(
                call.id,
                text="К сожалению, все копии этого приза уже разобраны!",
                show_alert=True
            )
            return
            
        # Пытаемся добавить победителя
        if manager.add_winner(user_id, prize_id):
            img = manager.get_prize_img(prize_id)
            if img and os.path.exists(f'img/{img}'):
                with open(f'img/{img}', 'rb') as photo:
                    bot.send_photo(
                        user_id,
                        photo,
                        caption="Поздравляем! Ты получил этот приз! 🎉"
                    )
                bot.answer_callback_query(call.id, text="Поздравляем с получением приза!")
            else:
                bot.answer_callback_query(
                    call.id,
                    text="Ошибка: приз не найден",
                    show_alert=True
                )
        else:
            bot.answer_callback_query(
                call.id,
                text="Ты уже получал этот приз!",
                show_alert=True
            )
            
    except Exception as e:
        print(f"Ошибка в callback_handler: {str(e)}")
        bot.answer_callback_query(
            call.id,
            text="Произошла ошибка при обработке запроса",
            show_alert=True
        )

def polling_thread():
    bot.infinity_polling()

if __name__ == '__main__':
    manager.create_tables()
    
    # Принудительная инициализация призов
    prizes_img = [f for f in os.listdir('img') if f.endswith(('.jpg', '.png', '.jpeg'))]
    if prizes_img:
        print(f"Найдены изображения: {prizes_img}")
        # Очищаем старые призы и добавляем новые
        conn = sqlite3.connect(DATABASE)
        with conn:
            conn.execute('DELETE FROM prizes')
            conn.executemany('INSERT INTO prizes (image, used) VALUES (?, 0)', [(img,) for img in prizes_img])
        print(f"Добавлено {len(prizes_img)} призов в базу")
        
        # Создаем размытые версии
        for img in prizes_img:
            manager.hide_img(img)
    else:
        print("Ошибка: В папке 'img' нет подходящих изображений!")

    polling_thread = threading.Thread(target=polling_thread)
    schedule_thread = threading.Thread(target=schedule_thread)

    polling_thread.start()
    schedule_thread.start()
