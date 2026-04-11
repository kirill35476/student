# database.py
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./school.db"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ========== ТАБЛИЦА УЧЕНИКОВ (ОСНОВНАЯ) ==========
class StudentDB(Base):
    """Модель ученика"""
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    grade = Column(Integer)
    hobby = Column(String)
    avatar = Column(String, nullable=True)

    # ✅ СВЯЗЬ: один ученик → много оценок
    # back_populates - обратная связь (из оценки можно получить ученика)
    grades = relationship("GradeDB", back_populates="student", cascade="all, delete-orphan")

    # ✅ СВЯЗЬ: много учеников → много кружков
    clubs = relationship("ClubDB", secondary="student_clubs", back_populates="students")


# ========== ТАБЛИЦА ОЦЕНОК ==========
class GradeDB(Base):
    """✅  Модель оценки (связь один ко многим с учеником)"""
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String)  # предмет
    score = Column(Integer)  # оценка (2, 3, 4, 5)
    date = Column(String)  # дата
    comment = Column(String, nullable=True)  # комментарий учителя

    # Внешний ключ: ссылка на ученика
    student_id = Column(Integer, ForeignKey("students.id"))

    # Обратная связь (чтобы из оценки получить ученика)
    student = relationship("StudentDB", back_populates="grades")


# ========== ТАБЛИЦА КРУЖКОВ ==========
class ClubDB(Base):
    """✅  Модель кружка"""
    __tablename__ = "clubs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)  # название кружка
    teacher = Column(String)  # руководитель
    room = Column(String)  # кабинет
    schedule = Column(String)  # расписание (например, "вторник 15:00")

    # Связь с учениками (многие ко многим)
    students = relationship("StudentDB", secondary="student_clubs", back_populates="clubs")


# ========== ТАБЛИЦА СВЯЗИ УЧЕНИКОВ И КРУЖКОВ ==========
class StudentClubDB(Base):
    """✅ Таблица связи (многие ко многим)"""
    __tablename__ = "student_clubs"

    student_id = Column(Integer, ForeignKey("students.id"), primary_key=True)
    club_id = Column(Integer, ForeignKey("clubs.id"), primary_key=True)
    join_date = Column(String, nullable=True)  # дата вступления (доп. поле)


# Создаём таблицы (если их ещё нет)
Base.metadata.create_all(bind=engine)


def get_db():
    """Возвращает сессию базы данных"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()