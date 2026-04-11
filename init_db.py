# init_db.py - скрипт для наполнения базы данных
from database import SessionLocal, ClubDB, StudentDB, GradeDB
from datetime import datetime


def init_clubs():
    """Добавляет начальные кружки в базу данных"""
    db = SessionLocal()

    try:
        # Проверяем, есть ли уже кружки
        existing_clubs = db.query(ClubDB).count()

        if existing_clubs == 0:
            print("📚 Добавляем начальные кружки...")

            clubs = [
                ClubDB(
                    name="Программирование",
                    teacher="Иванов А.А.",
                    room="№ 42",
                    schedule="ВТ 15:00, ЧТ 15:00"
                ),
                ClubDB(
                    name="Робототехника",
                    teacher="Петров Б.В.",
                    room="№ 15",
                    schedule="СР 14:00, ПТ 14:00"
                ),
                ClubDB(
                    name="Хор",
                    teacher="Сидорова М.И.",
                    room="Актовый зал",
                    schedule="ПН 16:00"
                ),
                ClubDB(
                    name="Спортивный",
                    teacher="Смирнов Д.К.",
                    room="Спортзал",
                    schedule="СР 16:00, ПТ 16:00"
                ),
                ClubDB(
                    name="Рисование",
                    teacher="Васильева Е.А.",
                    room="№ 8",
                    schedule="ВТ 15:00"
                ),
                ClubDB(
                    name="Шахматы",
                    teacher="Кузнецов И.П.",
                    room="№ 23",
                    schedule="ЧТ 15:00, СБ 11:00"
                ),
                ClubDB(
                    name="Театральная студия",
                    teacher="Волкова А.М.",
                    room="Актовый зал",
                    schedule="СР 16:00, ПТ 16:00"
                )
            ]

            for club in clubs:
                db.add(club)

            db.commit()
            print(f"✅ Добавлено {len(clubs)} кружков")
        else:
            print(f"ℹ️ Кружки уже есть в базе ({existing_clubs} шт.)")

        # Показываем список кружков
        clubs = db.query(ClubDB).all()
        print("\n📋 Список кружков:")
        for club in clubs:
            print(f"  - {club.name} ({club.teacher})")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        db.rollback()
    finally:
        db.close()


def show_stats():
    """Показывает статистику базы данных"""
    db = SessionLocal()
    try:
        students_count = db.query(StudentDB).count()
        grades_count = db.query(GradeDB).count()
        clubs_count = db.query(ClubDB).count()

        print("\n📊 Статистика базы данных:")
        print(f"  👨‍🎓 Учеников: {students_count}")
        print(f"  📝 Оценок: {grades_count}")
        print(f"  🎯 Кружков: {clubs_count}")

    finally:
        db.close()


def clear_clubs():
    """Очищает таблицу кружков (осторожно!)"""
    db = SessionLocal()
    try:
        confirm = input("⚠️ Вы уверены, что хотите удалить ВСЕ кружки? (yes/no): ")
        if confirm.lower() == "yes":
            count = db.query(ClubDB).delete()
            db.commit()
            print(f"🗑️ Удалено {count} кружков")
        else:
            print("❌ Операция отменена")
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 50)
    print("🛠️ Утилита управления базой данных школы")
    print("=" * 50)

    # Добавляем кружки
    init_clubs()

    # Показываем статистику
    show_stats()

    print("\n💡 Команды для запуска:")
    print("  python init_db.py          - добавить кружки")
    print("  python -c 'from init_db import show_stats; show_stats()' - статистика")
    print("  python -c 'from init_db import clear_clubs; clear_clubs()' - очистить кружки")