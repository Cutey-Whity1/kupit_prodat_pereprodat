import sqlite3
from datetime import datetime
from config import DATABASE 
import os
import cv2

class DatabaseManager:
    def __init__(self, database):
        self.database = database

    def create_tables(self):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                user_name TEXT
            )
            ''')

            conn.execute('''
            CREATE TABLE IF NOT EXISTS prizes (
                prize_id INTEGER PRIMARY KEY AUTOINCREMENT,
                image TEXT,
                used INTEGER DEFAULT 0
            )
            ''')

            conn.execute('''
            CREATE TABLE IF NOT EXISTS winners (
                user_id INTEGER,
                prize_id INTEGER,
                win_time TEXT,
                FOREIGN KEY(user_id) REFERENCES users(user_id),
                FOREIGN KEY(prize_id) REFERENCES prizes(prize_id),
                PRIMARY KEY (user_id, prize_id)
            )
            ''')
            # conn.commit() не нужен здесь, так как with conn автоматически коммитит

    def add_user(self, user_id, user_name):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('INSERT OR IGNORE INTO users VALUES (?, ?)', (user_id, user_name))
            # conn.commit() не нужен

    def add_prize(self, data):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.executemany('INSERT INTO prizes (image) VALUES (?)', data)
            # conn.commit() не нужен

    def add_winner(self, user_id, prize_id):
        win_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = sqlite3.connect(self.database)
        with conn:
            # Используем INSERT OR IGNORE для избежания дубликатов
            conn.execute('''
                INSERT OR IGNORE INTO winners (user_id, prize_id, win_time) 
                VALUES (?, ?, ?)
            ''', (user_id, prize_id, win_time))
            return conn.changes > 0  # Возвращаем True, если была добавлена запись

    def mark_prize_used(self, prize_id):
        conn = sqlite3.connect(self.database)
        with conn:
            conn.execute('UPDATE prizes SET used = 1 WHERE prize_id = ?', (prize_id,))
            # conn.commit() не нужен

    def get_users(self):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('SELECT * FROM users')
            return [x[0] for x in cur.fetchall()] 
        
    def get_prize_img(self, prize_id):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('SELECT image FROM prizes WHERE prize_id = ?', (prize_id,))
            result = cur.fetchone()
            return result[0] if result else None

    def get_winners_count(self, prize_id):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('''
                SELECT COUNT(*) 
                FROM winners 
                WHERE prize_id = ?
            ''', (prize_id,))
            return cur.fetchall()[0][0]
    
    
        
    def get_rating(self):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            cur.execute('''
                SELECT u.user_id, u.user_name, COUNT(w.prize_id) as wins_count
                FROM users u
                LEFT JOIN winners w ON u.user_id = w.user_id
                GROUP BY u.user_id, u.user_name
                ORDER BY wins_count DESC, u.user_name
            ''')
            return cur.fetchall()

    def get_random_prize(self):
        conn = sqlite3.connect(self.database)
        with conn:
            cur = conn.cursor()
            # Выбираем случайный неиспользованный приз
            cur.execute('''
                SELECT * FROM prizes 
                WHERE used = 0 
                ORDER BY RANDOM() 
                LIMIT 1
            ''')
            return cur.fetchone()
    
  
def hide_img(img_name):
    if not os.path.exists('hidden_img'):
        os.makedirs('hidden_img')
        
    image = cv2.imread(f'img/{img_name}')
    if image is None:
        raise FileNotFoundError(f"Image img/{img_name} not found")
        
    blurred_image = cv2.GaussianBlur(image, (15, 15), 0)
    pixelated_image = cv2.resize(blurred_image, (30, 30), interpolation=cv2.INTER_NEAREST)
    pixelated_image = cv2.resize(pixelated_image, (image.shape[1], image.shape[0]), interpolation=cv2.INTER_NEAREST)
    cv2.imwrite(f'hidden_img/{img_name}', pixelated_image)

if __name__ == '__main__':
    if not os.path.exists('img'):
        os.makedirs('img')
        print("Папка 'img' создана. Добавьте изображения призов и запустите скрипт снова.")
    else:
        manager = DatabaseManager(DATABASE)
        manager.create_tables()
        prizes_img = os.listdir('img')
        if prizes_img:
            data = [(x,) for x in prizes_img]
            manager.add_prize(data)
            print(f"Добавлено {len(prizes_img)} призов в базу данных.")
        else:
            print("В папке 'img' нет изображений. Добавьте изображения призов и запустите скрипт снова.")
