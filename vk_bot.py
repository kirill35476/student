import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
from database import SessionLocal, StudentDB, GradeDB, ClubDB, UserDB, StudentClubDB
from datetime import datetime

# ========== НАСТРОЙКИ ==========
VK_TOKEN = "vk1.a.PjMdwcmiylwObDa_vGbNU6C8mErnUPIUVtkp3M5cuiL4vPKkl_MeXwWQvP0_Z-oWeJ2jucdl5m7exaU11oFQSIXw3Mhf1LUr5fmv8ak1X0RuFS-0bkF2Rg3FsgdjuVgZl7L-feOhIzRBE_V0fFpdHIppLe7rARs8WtmQDnRbghIOYBi9wvpTSPONWAYXCd-PLrO4yGuVGDNLBp21t4D9aA"

# ========== ИНИЦИАЛИЗАЦИЯ ==========
vk_session = vk_api.VkApi(token=VK_TOKEN)
vk = vk_session.get_api()
longpoll = VkLongPoll(vk_session)

user_states = {}


# ========== КЛАВИАТУРЫ ==========

def get_main_keyboard():
    keyboard = VkKeyboard(one_time=False)
    keyboard.add_button('📚 Мои оценки', color=VkKeyboardColor.PRIMARY)
    keyboard.add_button('🎯 Кружки', color=VkKeyboardColor.POSITIVE)
    keyboard.add_line()
    keyboard.add_button('📊 Средний балл', color=VkKeyboardColor.SECONDARY)
    keyboard.add_button('📝 Хобби', color=VkKeyboardColor.SECONDARY)
    keyboard.add_line()
    keyboard.add_button('🏆 Лидеры класса', color=VkKeyboardColor.PRIMARY)
    keyboard.add_button('ℹ️ Помощь', color=VkKeyboardColor.SECONDARY)
    return keyboard


def get_login_keyboard():
    keyboard = VkKeyboard(one_time=True)
    keyboard.add_button('🔑 Войти', color=VkKeyboardColor.POSITIVE)
    keyboard.add_button('ℹ️ Помощь', color=VkKeyboardColor.SECONDARY)
    return keyboard


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С БД ==========

def get_student_by_vk_id(vk_id):
    """Находит ученика по VK ID"""
    db = SessionLocal()
    try:
        user = db.query(UserDB).filter(UserDB.vk_id == str(vk_id)).first()
        if user and user.student_id:
            student = db.query(StudentDB).filter(StudentDB.id == user.student_id).first()
            if student:
                # ✅ ЗАГРУЖАЕМ ВСЕ ДАННЫЕ ДО ЗАКРЫТИЯ СЕССИИ
                _ = student.grades  # Загружаем оценки
                _ = student.clubs  # Загружаем кружки
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
            # Загружаем связанные данные
            if user.student_id:
                student = db.query(StudentDB).filter(StudentDB.id == user.student_id).first()
                if student:
                    _ = student.grades
                    _ = student.clubs
            return user
        return None
    finally:
        db.close()


def get_student_grades(vk_id):
    """Получает оценки ученика"""
    db = SessionLocal()
    try:
        user = db.query(UserDB).filter(UserDB.vk_id == str(vk_id)).first()
        if not user or not user.student_id:
            return "❌ Аккаунт не привязан"

        student = db.query(StudentDB).filter(StudentDB.id == user.student_id).first()
        if not student:
            return "❌ Ученик не найден"

        grades = student.grades
        if not grades:
            return "📚 У вас пока нет оценок"

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
    finally:
        db.close()


def get_student_average(vk_id):
    """Вычисляет средний балл ученика"""
    db = SessionLocal()
    try:
        user = db.query(UserDB).filter(UserDB.vk_id == str(vk_id)).first()
        if not user or not user.student_id:
            return "❌ Аккаунт не привязан"

        student = db.query(StudentDB).filter(StudentDB.id == user.student_id).first()
        if not student:
            return "❌ Ученик не найден"

        grades = student.grades
        if not grades:
            return "📊 У вас пока нет оценок"

        avg = sum(g.score for g in grades) / len(grades)

        if avg >= 4.5:
            level = "🌟 Отлично! Так держать!"
        elif avg >= 4.0:
            level = "👍 Хорошо! Можешь лучше!"
        elif avg >= 3.0:
            level = "📚 Удовлетворительно. Нужно подтянуть!"
        else:
            level = "💪 Нужно больше заниматься!"

        return f"📊 Ваш средний балл: {avg:.2f}\n{level}\nВсего оценок: {len(grades)}"
    finally:
        db.close()


def get_student_clubs(vk_id):
    """Получает кружки ученика"""
    db = SessionLocal()
    try:
        user = db.query(UserDB).filter(UserDB.vk_id == str(vk_id)).first()
        if not user or not user.student_id:
            return "❌ Аккаунт не привязан"

        student = db.query(StudentDB).filter(StudentDB.id == user.student_id).first()
        if not student:
            return "❌ Ученик не найден"

        clubs = student.clubs
        if not clubs:
            return "🎯 Вы не записаны ни в один кружок"

        text = "🎯 Ваши кружки:\n\n"
        for club in clubs:
            text += f"📌 {club.name}\n"
            text += f"   👨‍🏫 {club.teacher}\n"
            text += f"   🏫 {club.room}\n"
            text += f"   ⏰ {club.schedule}\n\n"

        return text
    finally:
        db.close()


def get_student_hobby(vk_id):
    """Получает хобби ученика"""
    db = SessionLocal()
    try:
        user = db.query(UserDB).filter(UserDB.vk_id == str(vk_id)).first()
        if not user or not user.student_id:
            return "❌ Аккаунт не привязан"

        student = db.query(StudentDB).filter(StudentDB.id == user.student_id).first()
        if not student:
            return "❌ Ученик не найден"

        return f"📝 Ваше хобби: {student.hobby}\n📚 Класс: {student.grade}"
    finally:
        db.close()


def get_class_leaders(vk_id):
    """Получает лидеров класса"""
    db = SessionLocal()
    try:
        user = db.query(UserDB).filter(UserDB.vk_id == str(vk_id)).first()
        if not user or not user.student_id:
            return "❌ Аккаунт не привязан"

        student = db.query(StudentDB).filter(StudentDB.id == user.student_id).first()
        if not student:
            return "❌ Ученик не найден"

        grade = student.grade
        students = db.query(StudentDB).filter(StudentDB.grade == grade).all()

        leaders = []
        for s in students:
            grades = s.grades
            if grades:
                avg = sum(g.score for g in grades) / len(grades)
                leaders.append({
                    'name': s.name,
                    'avg': avg,
                    'count': len(grades)
                })

        leaders.sort(key=lambda x: x['avg'], reverse=True)

        if not leaders:
            return "🏆 В вашем классе пока нет оценок"

        text = f"🏆 Лидеры {grade} класса:\n\n"
        for i, leader in enumerate(leaders[:10], 1):
            if i == 1:
                medal = "🥇"
            elif i == 2:
                medal = "🥈"
            elif i == 3:
                medal = "🥉"
            else:
                medal = f"{i}."
            text += f"{medal} {leader['name']}: {leader['avg']:.2f} ({leader['count']} оценок)\n"

        return text
    finally:
        db.close()


def get_help():
    return """ℹ️ Помощь по боту:

Доступные команды:
📚 Мои оценки - показывает все оценки
📊 Средний балл - показывает средний балл
🎯 Кружки - список ваших кружков
📝 Хобби - информация о вас
🏆 Лидеры класса - рейтинг учеников

Для привязки аккаунта напишите:
Логин и пароль через пробел
Например: masha masha123"""


# ========== ОТПРАВКА СООБЩЕНИЙ ==========

def send_message(user_id, message, keyboard=None):
    try:
        params = {
            'user_id': user_id,
            'message': message,
            'random_id': get_random_id(),
        }
        if keyboard:
            params['keyboard'] = keyboard.get_keyboard()

        vk.messages.send(**params)
    except Exception as e:
        print(f"Ошибка отправки: {e}")


# ========== ОБРАБОТКА СООБЩЕНИЙ ==========

def process_message(event):
    user_id = event.user_id
    text = event.text.strip()

    # Проверяем, привязан ли пользователь
    student, user = get_student_by_vk_id(user_id)

    # Если пользователь уже привязан
    if student:
        if text in ['📚 Мои оценки', 'Оценки', 'оценки']:
            send_message(user_id, get_student_grades(user_id), get_main_keyboard())

        elif text in ['📊 Средний балл', 'Средний балл', 'Балл', 'балл']:
            send_message(user_id, get_student_average(user_id), get_main_keyboard())

        elif text in ['🎯 Кружки', 'Кружки', 'кружки', 'Мои кружки']:
            send_message(user_id, get_student_clubs(user_id), get_main_keyboard())

        elif text in ['📝 Хобби', 'Хобби', 'хобби']:
            send_message(user_id, get_student_hobby(user_id), get_main_keyboard())

        elif text in ['🏆 Лидеры класса', 'Лидеры', 'Рейтинг', 'лидеры']:
            send_message(user_id, get_class_leaders(user_id), get_main_keyboard())

        elif text in ['ℹ️ Помощь', 'Помощь', 'help', 'помощь']:
            send_message(user_id, get_help(), get_main_keyboard())

        elif text.lower() in ['привет', 'здравствуй', 'hello', 'hi', 'начать', 'start', 'меню']:
            send_message(user_id, f"👋 Привет, {student.name}!\nВыберите действие:", get_main_keyboard())

        else:
            send_message(user_id, "Используйте кнопки меню или напишите 'Помощь'", get_main_keyboard())

        return

    # Если не привязан
    if user_id in user_states and user_states[user_id] == 'waiting_login':
        parts = text.split()
        if len(parts) >= 2:
            username = parts[0]
            password = parts[1]
            user = link_vk_to_student(user_id, username, password)
            if user:
                student, _ = get_student_by_vk_id(user_id)
                send_message(user_id, f"✅ Добро пожаловать, {student.name}!", get_main_keyboard())
            else:
                send_message(user_id, "❌ Неверный логин или пароль. Попробуйте ещё раз:")
        else:
            send_message(user_id, "Введите логин и пароль через пробел:\nНапример: masha masha123")
        del user_states[user_id]
        return

    if text in ['🔑 Войти', 'Войти', 'войти']:
        send_message(user_id, "Введите логин и пароль через пробел:\nНапример: masha masha123")
        user_states[user_id] = 'waiting_login'

    elif text in ['ℹ️ Помощь', 'Помощь', 'help']:
        send_message(user_id, get_help(), get_login_keyboard())

    elif text.lower() in ['привет', 'здравствуй', 'hello', 'hi', 'начать', 'start']:
        send_message(user_id,
                     "👋 Привет! Я бот школы №7.\n\n"
                     "Для работы нужно привязать аккаунт.\n"
                     "Нажмите '🔑 Войти' и введите логин и пароль.\n"
                     "Например: masha masha123",
                     get_login_keyboard())

    else:
        parts = text.split()
        if len(parts) == 2:
            username = parts[0]
            password = parts[1]
            user = link_vk_to_student(user_id, username, password)
            if user:
                student, _ = get_student_by_vk_id(user_id)
                send_message(user_id, f"✅ Добро пожаловать, {student.name}!", get_main_keyboard())
            else:
                send_message(user_id, "❌ Неверный логин или пароль", get_login_keyboard())
        else:
            send_message(user_id,
                         "Нажмите '🔑 Войти' и введите логин и пароль.\n"
                         "Например: masha masha123",
                         get_login_keyboard())


def main():
    print("=" * 50)
    print("🤖 Школьный бот ВКонтакте")
    print("=" * 50)
    print("Бот запущен!")
    print("Ожидание сообщений...")

    try:
        for event in longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW and event.to_me:
                print(f"📩 Сообщение от {event.user_id}: {event.text}")
                try:
                    process_message(event)
                except Exception as e:
                    print(f"❌ Ошибка: {e}")
                    try:
                        send_message(event.user_id, "❌ Произошла ошибка. Попробуйте позже.")
                    except:
                        pass
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен!")


if __name__ == "__main__":
    main()