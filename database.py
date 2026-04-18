# database.py
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Float, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import enum
from sqlalchemy.orm import Session

SQLALCHEMY_DATABASE_URL = "sqlite:///./school.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()



# ========== НОВОЕ: РОЛИ ПОЛЬЗОВАТЕЛЕЙ ==========

class UserRole(str, enum.Enum):
    """
    Роли пользователей в системе

    Роли определяют, какие действия может выполнять пользователь:
    - STUDENT (ученик): может только смотреть свой профиль и свои оценки
    - TEACHER (учитель): может добавлять/удалять оценки всем ученикам
    - ADMIN (администратор): может всё + управлять кружками и пользователями
    """
    STUDENT = "student"  # ученик
    TEACHER = "teacher"  # учитель
    ADMIN = "admin"  # администратор


class UserDB(Base):
    """
    НОВАЯ ТАБЛИЦА: Пользователи системы

    Теперь у нас есть отдельная таблица для хранения пользователей.
    Каждый пользователь имеет:
    - username: уникальное имя для входа
    - password: пароль (в реальном проекте нужно хешировать!)
    - role: роль (ученик, учитель, администратор)
    - student_id: связь с учеником (если пользователь - ученик)
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)  # уникальное имя
    password = Column(String, nullable=False)  # пароль (временно храним как текст)
    role = Column(Enum(UserRole), default=UserRole.STUDENT, nullable=False)  # роль

    # Связь с учеником (один к одному)
    # Если пользователь - ученик, то здесь будет ID ученика
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True, unique=True)

    # Связь для получения объекта ученика
    student = relationship("StudentDB", back_populates="user")

    # Дата регистрации
    created_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))


# ========== ТАБЛИЦА УЧЕНИКОВ (ОСНОВНАЯ) ==========
class StudentDB(Base):
    """
    Модель ученика (НЕ ИЗМЕНИЛАСЬ, но добавилась связь с пользователем)
    """
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    grade = Column(Integer)
    hobby = Column(String)
    avatar = Column(String, nullable=True)

    # СВЯЗЬ: один ученик → много оценок
    grades = relationship("GradeDB", back_populates="student", cascade="all, delete-orphan")

    # СВЯЗЬ: много учеников → много кружков
    clubs = relationship("ClubDB", secondary="student_clubs", back_populates="students")

    # НОВОЕ: связь с пользователем (один к одному)
    user = relationship("UserDB", back_populates="student", uselist=False)


# ========== ТАБЛИЦА ОЦЕНОК (НЕ ИЗМЕНИЛАСЬ) ==========
class GradeDB(Base):
    """Модель оценки (связь один ко многим с учеником)"""
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String)  # предмет
    score = Column(Integer)  # оценка (2, 3, 4, 5)
    date = Column(String)  # дата
    comment = Column(String, nullable=True)  # комментарий учителя
    teacher_name = Column(String, nullable=True)  # НОВОЕ: кто поставил оценку

    # Внешний ключ: ссылка на ученика
    student_id = Column(Integer, ForeignKey("students.id"))

    # Обратная связь (чтобы из оценки получить ученика)
    student = relationship("StudentDB", back_populates="grades")


# ========== ТАБЛИЦА КРУЖКОВ (НЕ ИЗМЕНИЛАСЬ) ==========
class ClubDB(Base):
    """Модель кружка"""
    __tablename__ = "clubs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)  # название кружка
    teacher = Column(String)  # руководитель
    room = Column(String)  # кабинет
    schedule = Column(String)  # расписание (например, "вторник 15:00")

    # Связь с учениками (многие ко многим)
    students = relationship("StudentDB", secondary="student_clubs", back_populates="clubs")


# ========== ТАБЛИЦА СВЯЗИ УЧЕНИКОВ И КРУЖКОВ (НЕ ИЗМЕНИЛАСЬ) ==========
class StudentClubDB(Base):
    """Таблица связи (многие ко многим)"""
    __tablename__ = "student_clubs"

    student_id = Column(Integer, ForeignKey("students.id"), primary_key=True)
    club_id = Column(Integer, ForeignKey("clubs.id"), primary_key=True)
    join_date = Column(String, nullable=True)  # дата вступления


# Создаём таблицы (если их ещё нет)
Base.metadata.create_all(bind=engine)


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ ==========

def get_db():
    """Возвращает сессию базы данных"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# НОВОЕ: Функция для создания тестовых пользователей
def create_test_users(db):
    """
    Создаёт тестовых пользователей для демонстрации

    ВНИМАНИЕ! В реальном проекте пароли нужно хешировать!
    Сейчас они хранятся в открытом виде ТОЛЬКО ДЛЯ ОБУЧЕНИЯ!
    """

    # Проверяем, есть ли уже пользователи
    if db.query(UserDB).count() > 0:
        print("ℹ️ Пользователи уже существуют")
        return


    test_users = [
        # Ученики
        {"username": "masha", "password": "masha123", "role": UserRole.STUDENT, "student_id": 1},
        {"username": "petya", "password": "petya123", "role": UserRole.STUDENT, "student_id": 2},
        {"username": "anya", "password": "anya123", "role": UserRole.STUDENT, "student_id": 3},

        # Учитель
        {"username": "teacher", "password": "teacher123", "role": UserRole.TEACHER, "student_id": None},

        # Администратор
        {"username": "admin", "password": "admin123", "role": UserRole.ADMIN, "student_id": None},
    ]

    for user_data in test_users:
        # Проверяем, не занято ли имя
        existing = db.query(UserDB).filter(UserDB.username == user_data["username"]).first()
        if not existing:
            user = UserDB(**user_data)
            db.add(user)

    db.commit()
    print("✅ Созданы тестовые пользователи:")
    print("   Ученики: masha/masha123, petya/petya123, anya/anya123")
    print("   Учитель: teacher/teacher123")
    print("   Админ: admin/admin123")


# НОВОЕ: Функция для проверки прав пользователя
def check_permission(user_role: UserRole, action: str) -> bool:
    """
    Проверяет, имеет ли пользователь право на действие

    Правила доступа:
    - Ученик (STUDENT): может только смотреть (read)
    - Учитель (TEACHER): может читать и писать оценки (read, write_grades)
    - Админ (ADMIN): может всё (все действия)
    """
    # Определяем, какие действия разрешены каждой роли
    permissions = {
        UserRole.STUDENT: ["read_own_profile", "read_own_grades", "read_clubs"],
        UserRole.TEACHER: ["read_own_profile", "read_own_grades", "read_clubs",
                           "write_grades", "delete_grades", "read_all_students"],
        UserRole.ADMIN: ["*"]  # звёздочка означает "все действия"
    }

    if user_role == UserRole.ADMIN:
        return True

    return action in permissions.get(user_role, [])


# НОВОЕ: Функция для получения текущего пользователя (будет использоваться в main.py)
def get_current_user(db: Session, username: str, password: str):
    """Проверяет логин и пароль, возвращает пользователя или None"""
    user = db.query(UserDB).filter(
        UserDB.username == username,
        UserDB.password == password
    ).first()
    return user


# ========================================================
# НОВОЕ: Функция для получения текущего пользователя по ID (будет использоваться в main.py)

def get_student_by_id(db: Session, student_id: int):
    """Получить ученика по ID (безопаснее, чем по имени)"""
    return db.query(StudentDB).filter(StudentDB.id == student_id).first()


def get_student_by_username(db: Session, username: str):
    """Получить ученика по имени пользователя (для входа)"""
    user = db.query(UserDB).filter(UserDB.username == username).first()
    if user and user.student_id:
        return db.query(StudentDB).filter(StudentDB.id == user.student_id).first()
    return None