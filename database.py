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


# ========== РОЛИ ПОЛЬЗОВАТЕЛЕЙ ==========
class UserRole(str, enum.Enum):
    STUDENT = "student"
    TEACHER = "teacher"
    ADMIN = "admin"


# ========== ТАБЛИЦА ПОЛЬЗОВАТЕЛЕЙ (ТОЛЬКО ОДНО ОПРЕДЕЛЕНИЕ!) ==========
class UserDB(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.STUDENT, nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)  # УБРАТЬ unique=True
    vk_id = Column(String, nullable=True)
    student = relationship("StudentDB", back_populates="user")
    created_at = Column(String, default=lambda: datetime.now().strftime("%d.%m.%Y %H:%M"))

# ========== ТАБЛИЦА УЧЕНИКОВ ==========
class StudentDB(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    grade = Column(Integer)
    hobby = Column(String)
    avatar = Column(String, nullable=True)
    grades = relationship("GradeDB", back_populates="student", cascade="all, delete-orphan")
    clubs = relationship("ClubDB", secondary="student_clubs", back_populates="students")
    user = relationship("UserDB", back_populates="student", uselist=False)


# ========== ТАБЛИЦА ОЦЕНОК ==========
class GradeDB(Base):
    __tablename__ = "grades"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String)
    score = Column(Integer)
    date = Column(String)
    comment = Column(String, nullable=True)
    teacher_name = Column(String, nullable=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    student = relationship("StudentDB", back_populates="grades")


# ========== ТАБЛИЦА КРУЖКОВ ==========
class ClubDB(Base):
    __tablename__ = "clubs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    teacher = Column(String)
    room = Column(String)
    schedule = Column(String)
    students = relationship("StudentDB", secondary="student_clubs", back_populates="clubs")


# ========== ТАБЛИЦА СВЯЗИ ==========
class StudentClubDB(Base):
    __tablename__ = "student_clubs"

    student_id = Column(Integer, ForeignKey("students.id"), primary_key=True)
    club_id = Column(Integer, ForeignKey("clubs.id"), primary_key=True)
    join_date = Column(String, nullable=True)


# ========== СОЗДАНИЕ ТАБЛИЦ ==========
Base.metadata.create_all(bind=engine)


# ========== ФУНКЦИИ ==========
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_test_users(db):
    if db.query(UserDB).count() > 0:
        print("ℹ️ Пользователи уже существуют")
        return

    test_users = [
        {"username": "masha", "password": "masha123", "role": UserRole.STUDENT, "student_id": 1},
        {"username": "petya", "password": "petya123", "role": UserRole.STUDENT, "student_id": 2},
        {"username": "anya", "password": "anya123", "role": UserRole.STUDENT, "student_id": 3},
        {"username": "teacher", "password": "teacher123", "role": UserRole.TEACHER, "student_id": None},
        {"username": "admin", "password": "admin123", "role": UserRole.ADMIN, "student_id": None},
    ]

    for user_data in test_users:
        existing = db.query(UserDB).filter(UserDB.username == user_data["username"]).first()
        if not existing:
            user = UserDB(**user_data)
            db.add(user)

    db.commit()
    print("✅ Созданы тестовые пользователи:")
    print("   Ученики: masha/masha123, petya/petya123, anya/anya123")
    print("   Учитель: teacher/teacher123")
    print("   Админ: admin/admin123")


def check_permission(user_role: UserRole, action: str) -> bool:
    permissions = {
        UserRole.STUDENT: ["read_own_profile", "read_own_grades", "read_clubs"],
        UserRole.TEACHER: ["read_own_profile", "read_own_grades", "read_clubs",
                           "write_grades", "delete_grades", "read_all_students"],
        UserRole.ADMIN: ["*"]
    }
    if user_role == UserRole.ADMIN:
        return True
    return action in permissions.get(user_role, [])


def get_current_user(db: Session, username: str, password: str):
    user = db.query(UserDB).filter(
        UserDB.username == username,
        UserDB.password == password
    ).first()
    return user


def get_student_by_id(db: Session, student_id: int):
    return db.query(StudentDB).filter(StudentDB.id == student_id).first()


def get_student_by_username(db: Session, username: str):
    user = db.query(UserDB).filter(UserDB.username == username).first()
    if user and user.student_id:
        return db.query(StudentDB).filter(StudentDB.id == user.student_id).first()
    return None