# vk_bot.py
"""
Бот ВКонтакте для школьной системы
Позволяет ученикам и учителям получать информацию через ВК

Для работы нужно:
1. Установить библиотеку: pip install vk-api
2. Создать группу ВК и получить токен
3. Включить Long Poll API в настройках группы
"""

import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
from database import SessionLocal, StudentDB, GradeDB, ClubDB, UserDB, StudentClubDB
from datetime import datetime
import random

# ========== НАСТРОЙКИ ==========
# Токен группы ВК (получить в настройках группы -> Работа с API)
VK_TOKEN = "vk1.a.k1UnXPcPLoTR2nWX8sgYizNZRJA8bscXYB2iTzAGf18rv4O5SARwibzVtA2zGJq4M3Xm_NiakCt0JAVK2dR2Oh8XOg8GrQFDrzMwJhfUx6HCF0sO-pRw5qpwgYJzR-gNgfIRM0R40wIa_gZw9dzy0YRip5kMSU71O-UkOCsJEV9L2h1Mh25yx9Id1ORFoBYDTb0Vccac-v8Dzb9ZkiG35w"

# ========== ИНИЦИАЛИЗАЦИЯ ==========
vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

# Словарь для хранения состояний пользователей
user_states = {}


# ========== КЛАВИАТУРЫ ==========

def get_main_keyboard():
    """Главное меню"""
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('📚 Мои оценки', color=VkKeyboardColor.PRIMARY)
    keyboard.add_button('🎯 Кружки', color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button('📊 Мой средний балл', color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button('🏆 Лидеры класса', color=VkKeyboardColor.PRIMARY)
    keyboard.add_button('ℹ️ Помощь', color=VkKeyboardColor.SECONDARY)
    return keyboard


def get_clubs_keyboard(clubs):
    """Клавиатура с кружками"""
    keyboard = VkKeyboard(one_time=True)
    for i, club in enumerate(clubs):
        if i % 2 == 0 and i != 0:
            keyboard.add_line()
        keyboard.add_button(f"📌 {club.name}", color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button('🔙 Назад', color=VkKeyboardColor.SECONDARY)
    return keyboard


def get_back_keyboard():
    """Клавиатура с кнопкой назад"""
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('🔙 Назад', color=VkKeyboardColor.SECONDARY)
    return keyboard


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С БД ==========

def get_student_by_vk_id(vk_id):
    """Находит ученика по привязанному VK ID"""
    db = SessionLocal()
    try:
        # Ищем пользователя с таким VK ID
        user = db.query(UserDB).filter(UserDB.vk_id == str(vk_id)).first()
        if user and user.student_id:
            student = db.query(StudentDB).filter(StudentDB.id == user.student_id).first()
            return student, user
        return None, None
    finally:
        db.close()


def link_vk_to_student(vk_id, username, password):
    """Привязывает VK ID к ученику"""
    db = SessionLocal()
    try:
        user = db.query(UserDB).filter(
            UserDB.username == username,
            UserDB.password == password
        ).first()

        if user:
            user.vk_id = str(vk_id)
            db.commit()
            return user
        return None
    finally:
        db.close()


def get_student_grades(student):
    """Получает оценки ученика"""
    grades = student.grades
    if not grades:
        return "У вас пока нет оценок"

    # Группируем по предметам
    subjects = {}
    for grade in grades:
        if grade.subject not in subjects:
            subjects[grade.subject] = []
        subjects[grade.subject].append(grade.score)

    text = "📚 Ваши оценки:\n\n"
    for subject, scores in subjects.items():
        avg = sum(scores) / len(scores)
        scores_str = ", ".join(str(s) for s in scores)
        text += f"📖 {subject}: {scores_str}\n"
        text += f"   Средний: {avg:.1f}\n\n"

    return text


def get_student_average(student):
    """Вычисляет средний балл ученика"""
    grades = student.grades
    if not grades:
        return "У вас пока нет оценок"

    avg = sum(g.score for g in grades) / len(grades)

    # Определяем уровень
    if avg >= 4.5:
        level = "🌟 Отлично!"
    elif avg >= 4.0:
        level = "👍 Хорошо"
    elif avg >= 3.0:
        level = "📚 Удовлетворительно"
    else:
        level = "💪 Нужно подтянуть"

    return f"📊 Ваш средний балл: {avg:.2f}\n{level}\nВсего оценок: {len(grades)}"


def get_student_clubs(student):
    """Получает кружки ученика"""
    clubs = student.clubs
    if not clubs:
        return "Вы не записаны ни в один кружок"

    text = "🎯 Ваши кружки:\n\n"
    for club in clubs:
        text += f"📌 {club.name}\n"
        text += f"   👨‍🏫 {club.teacher}\n"
        text += f"   🏫 {club.room}\n"
        text += f"   ⏰ {club.schedule}\n\n"

    return text


def get_all_clubs():
    """Получает все кружки"""
    db = SessionLocal()
    try:
        clubs = db.query(ClubDB).all()
        return clubs
    finally:
        db.close()


def get_class_leaders(grade):
    """Получает лидеров класса"""
    db = SessionLocal()
    try:
        students = db.query(StudentDB).filter(StudentDB.grade == grade).all()

        leaders = []
        for student in students:
            grades = student.grades
            if grades:
                avg = sum(g.score for g in grades) / len(grades)
                leaders.append({
                    'name': student.name,
                    'avg': avg,
                    'count': len(grades)
                })

        # Сортируем по убыванию
        leaders.sort(key=lambda x: x['avg'], reverse=True)

        text = f"🏆 Лидеры {grade} класса:\n\n"
        for i, leader in enumerate(leaders[:10], 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{medal} {leader['name']}: {leader['avg']:.2f} ({leader['count']} оценок)\n"

        return text
    finally:
        db.close()


def get_help():
    """Помощь по командам"""
    return """ℹ️ Помощь по боту:

Доступные команды:
📚 Мои оценки - показывает все оценки
📊 Средний балл - показывает средний балл
🎯 Кружки - список ваших кружков
🏆 Лидеры класса - рейтинг учеников
📌 Название кружка - информация о кружке

Для привязки аккаунта:
🔑 Привязать: логин пароль

По вопросам: @admin"""


# ========== ОБРАБОТКА СООБЩЕНИЙ ==========

def send_message(user_id, message, keyboard=None, attachment=None):
    """Отправляет сообщение пользователю"""
    try:
        params = {
            'user_id': user_id,
            'message': message,
            'random_id': get_random_id(),
        }
        if keyboard:
            params['keyboard'] = keyboard.get_keyboard()
        if attachment:
            params['attachment'] = attachment

        vk.messages.send(**params)
    except Exception as e:
        print(f"Ошибка отправки: {e}")


def process_message(event):
    """Обрабатывает входящее сообщение"""
    user_id = event.user_id
    text = event.text.strip()

    # Проверяем состояние пользователя
    if user_id in user_states:
        state = user_states[user_id]

        if state == 'waiting_login':
            # Пользователь вводит логин и пароль
            parts = text.split()
            if len(parts) >= 2:
                username = parts[0]
                password = parts[1]
                user = link_vk_to_student(user_id, username, password)
                if user:
                    send_message(user_id, "✅ Аккаунт успешно привязан!", get_main_keyboard())
                else:
                    send_message(user_id, "❌ Неверный логин или пароль. Попробуйте ещё раз:\nВведите: логин пароль",
                                 get_back_keyboard())
            else:
                send_message(user_id, "Введите логин и пароль через пробел:\nНапример: masha masha123",
                             get_back_keyboard())
            del user_states[user_id]
            return

        elif state == 'waiting_club_info':
            # Пользователь хочет посмотреть информацию о кружке
            clubs = get_all_clubs()
            club = next((c for c in clubs if c.name.lower() in text.lower()), None)
            if club:
                info = f"📌 {club.name}\n👨‍🏫 Преподаватель: {club.teacher}\n🏫 Кабинет: {club.room}\n⏰ Расписание: {club.schedule}"
                send_message(user_id, info, get_main_keyboard())
            else:
                send_message(user_id, "Кружок не найден", get_main_keyboard())
            del user_states[user_id]
            return

    # Обработка команд
    student, user = get_student_by_vk_id(user_id)

    # Если пользователь не привязан
    if not student and text not in ['🔑 Привязать', 'Начать', 'start', 'ℹ️ Помощь']:
        keyboard = VkKeyboard(one_time=True)
        keyboard.add_button('🔑 Привязать аккаунт', color=VkKeyboardColor.PRIMARY)
        keyboard.add_button('ℹ️ Помощь', color=VkKeyboardColor.SECONDARY)

        send_message(user_id,
                     "👋 Привет! Я бот школьной системы.\n"
                     "Для работы нужно привязать аккаунт.\n"
                     "Нажмите кнопку ниже или введите логин и пароль:\n"
                     "Например: masha masha123",
                     keyboard)
        return

    # Главные команды
    if text in ['📚 Мои оценки', 'Оценки']:
        if student:
            send_message(user_id, get_student_grades(student), get_main_keyboard())
        else:
            send_message(user_id, "Сначала привяжите аккаунт", get_main_keyboard())

    elif text in ['📊 Мой средний балл', 'Средний балл', 'Балл']:
        if student:
            send_message(user_id, get_student_average(student), get_main_keyboard())
        else:
            send_message(user_id, "Сначала привяжите аккаунт", get_main_keyboard())

    elif text in ['🎯 Кружки', 'Мои кружки']:
        if student:
            clubs = get_all_clubs()
            text = get_student_clubs(student)
            text += "\n📌 Напишите название кружка для подробной информации"
            send_message(user_id, text, get_clubs_keyboard(clubs))
        else:
            send_message(user_id, "Сначала привяжите аккаунт", get_main_keyboard())

    elif text in ['🏆 Лидеры класса', 'Лидеры', 'Рейтинг']:
        if student:
            send_message(user_id, get_class_leaders(student.grade), get_main_keyboard())
        else:
            send_message(user_id, "Сначала привяжите аккаунт", get_main_keyboard())

    elif text in ['ℹ️ Помощь', 'Помощь', 'help']:
        send_message(user_id, get_help(), get_main_keyboard())

    elif text in ['🔙 Назад', 'Назад']:
        send_message(user_id, "Главное меню", get_main_keyboard())

    elif text in ['🔑 Привязать аккаунт', '🔑 Привязать']:
        send_message(user_id, "Введите логин и пароль через пробел:\nНапример: masha masha123", get_back_keyboard())
        user_states[user_id] = 'waiting_login'

    elif text.startswith('📌'):
        club_name = text.replace('📌', '').strip()
        clubs = get_all_clubs()
        club = next((c for c in clubs if c.name.lower() == club_name.lower()), None)
        if club:
            info = f"📌 {club.name}\n👨‍🏫 {club.teacher}\n🏫 {club.room}\n⏰ {club.schedule}"
            send_message(user_id, info, get_main_keyboard())
        else:
            send_message(user_id, "Кружок не найден", get_main_keyboard())

    elif text.lower() in ['привет', 'здравствуй', 'hello', 'hi', 'начать', 'start']:
        if student:
            send_message(user_id, f"👋 Привет, {student.name}!\nВыберите действие:", get_main_keyboard())
        else:
            send_message(user_id, "👋 Привет! Введите логин и пароль для привязки:\nНапример: masha masha123")

    else:
        # Проверяем, может это логин и пароль
        parts = text.split()
        if len(parts) == 2:
            username = parts[0]
            password = parts[1]
            user = link_vk_to_student(user_id, username, password)
            if user:
                student, _ = get_student_by_vk_id(user_id)
                send_message(user_id, f"✅ Добро пожаловать, {student.name}!", get_main_keyboard())
            else:
                send_message(user_id, "❌ Неверный логин или пароль", get_main_keyboard())
        else:
            send_message(user_id, "Неизвестная команда. Напишите 'Помощь' для списка команд", get_main_keyboard())


# ========== ЗАПУСК БОТА ==========

def main():
    """Основной цикл бота"""
    print("🤖 Бот запущен!")
    print("Ожидание сообщений...")

    try:
        for event in longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                print(f"📩 Новое сообщение от {event.user_id}: {event.text}")
                try:
                    process_message(event)
                except Exception as e:
                    print(f"❌ Ошибка обработки сообщения: {e}")
                    send_message(event.user_id, "Произошла ошибка. Попробуйте позже.")
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен!")


if __name__ == "__main__":
    print("=" * 50)
    print("🤖 Школьный бот ВКонтакте")
    print("=" * 50)
    main()