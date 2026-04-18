# main.py (добавляем в начало файла)

from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi import Form, UploadFile, File
from typing import Annotated, Optional  # для опциональных аргументов
import shutil
import os
from sqlalchemy.orm import Session
from datetime import datetime
# Для работы с сессиями (чтобы запоминать, кто вошёл)
from fastapi import Cookie
# Импортируем наши БД-штуки (обновлённые)
from database import get_db, create_test_users,StudentDB, GradeDB, ClubDB, StudentClubDB, UserDB, UserRole, check_permission, get_current_user,SessionLocal


# Настройки для загрузки картинок
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


# main.py - добавить в начало файла

def transliterate(name: str) -> str:
    """Преобразует русское имя в латиницу (для логина)"""
    ru = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '',
        'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    result = []
    for char in name.lower():
        if char in ru:
            result.append(ru[char])
        elif char.isalpha():
            result.append(char)
        elif char.isdigit():
            result.append(char)
        else:
            result.append('_')
    return ''.join(result)


def generate_password() -> str:
    """Генерирует случайный пароль"""
    import random
    import string
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(8))




def validate_image(file: UploadFile):
    """Проверяет, что файл - допустимое изображение"""
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Неверный формат. Разрешены: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)

    if size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Файл слишком большой. Максимум: {MAX_FILE_SIZE // (1024 * 1024)} MB"
        )
    return True

# Простая система сессий (в реальном проекте используйте JWT или OAuth2)
# Храним пользователей в словаре: session_token -> username
active_sessions = {}
def generate_session_token():
    """Генерирует простой токен для сессии"""
    import hashlib
    import time
    return hashlib.md5(f"{time.time()}{os.urandom(16)}".encode()).hexdigest()


# main.py (добавляем в lifespan)

from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Запускается при старте приложения"""
    print("🚀 Запускаем приложение...")

    # Создаём тестовых пользователей
    db = SessionLocal()
    try:
        create_test_users(db)  # функция из database.py
    finally:
        db.close()

    print("✅ Приложение готово к работе!")
    yield
    print("👋 Останавливаем приложение...")


# Обновляем создание app
app = FastAPI(title="Школа с БД", lifespan=lifespan)

# app = FastAPI(title="Школа с БД")

# Подключаем статику и шаблоны
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Папка для аватарок
AVATAR_DIR = "static/avatars"
os.makedirs(AVATAR_DIR, exist_ok=True)


def get_current_user_from_session(
        session_token: Optional[str] = Cookie(None),
        db: Session = Depends(get_db)
):
    """
    Получает текущего пользователя из cookie
    """
    if not session_token or session_token not in active_sessions:
        return None

    username = active_sessions[session_token]
    user = db.query(UserDB).filter(UserDB.username == username).first()
    return user




# ========== СТРАНИЦА ВХОДА ==========

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """
    Показывает страницу входа в систему
    """
    return templates.TemplateResponse(
        "login.html",
        {"request": request, "title": "Вход в систему"}
    )

@app.post("/login")
async def login(
        request: Request,
        username: Annotated[str, Form()],
        password: Annotated[str, Form()],
        db: Session = Depends(get_db)
):
    """
    Обрабатывает форму входа
    """
    # Ищем пользователя в базе данных
    user = db.query(UserDB).filter(
        UserDB.username == username,
        UserDB.password == password  # В реальном проекте пароли хешируют!
    ).first()

    if not user:
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "title": "Вход в систему",
                "error": "Неверное имя пользователя или пароль"
            }
        )

    # Создаём сессию
    session_token = generate_session_token()
    active_sessions[session_token] = user.username

    # Создаём ответ и устанавливаем cookie
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="session_token", value=session_token, httponly=True)

    return response

@app.get("/logout")
async def logout():
    """
    Выход из системы
    """
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_token")
    return response


# ========== ГЛАВНАЯ СТРАНИЦА (с проверкой прав) ==========
@app.get("/", response_class=HTMLResponse)
async def home(
        request: Request,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """
    Главная страница со списком учеников
    - Ученик видит только свой профиль
    - Учитель и Админ видят всех учеников
    """
    # Если пользователь не авторизован - отправляем на страницу входа
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    # Определяем, какие данные показывать
    if current_user.role == UserRole.STUDENT:
        # Ученик видит только себя
        student = db.query(StudentDB).filter(StudentDB.id == current_user.student_id).first()
        students = [student] if student else []
        show_add_button = False  # ученик не может добавлять
        show_delete_buttons = False  # ученик не может удалять
        show_edit_buttons = False  # ученик не может редактировать
    else:
        # Учитель и Админ видят всех
        students = db.query(StudentDB).all()
        show_add_button = True  # учитель и админ могут добавлять
        show_edit_buttons = True  # учитель и админ могут редактировать
        show_delete_buttons = (current_user.role == UserRole.ADMIN)  # ТОЛЬКО админ удаляет
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "students": students,
            "school_name": "Школа №7",
            "title": "Моя школа",
            "current_user": current_user,
            "show_add_button": show_add_button,
            "show_edit_buttons": show_edit_buttons,
            "show_delete_buttons": show_delete_buttons
        }
    )

# ========== СТРАНИЦА ПРОФИЛЯ (с оценками и кружками) по ID и ролям ==========
@app.get("/student/{student_id}", response_class=HTMLResponse)
async def student_profile(
        request: Request,
        student_id: int,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """
    Страница ученика с оценками и кружками
    - Ученик может видеть только свой профиль
    - Учитель и Админ могут видеть любого ученика
    """
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    # Проверяем права доступа к профилю
    if current_user.role == UserRole.STUDENT:
        # Ученик может смотреть только свой профиль
        if current_user.student_id != student_id:
            raise HTTPException(status_code=403, detail="У вас нет доступа к этому профилю")

    student = db.query(StudentDB).filter(StudentDB.id == student_id).first()

    if not student:
        raise HTTPException(status_code=404, detail="Ученик не найден")

    all_clubs = db.query(ClubDB).all()

    # Определяем, какие кнопки показывать
    can_add_grade = current_user.role != UserRole.STUDENT  # учитель и админ
    can_edit = current_user.role != UserRole.STUDENT  # учитель и админ
    can_join_club = current_user.role == UserRole.STUDENT  # ученик может записываться
    can_leave_club = (current_user.role == UserRole.STUDENT)  # только ученик
    can_manage_clubs = current_user.role == UserRole.ADMIN  # только админ управляет кружками

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "student": student,
            "all_clubs": all_clubs,
            "title": f"Профиль: {student.name}",
            "current_user": current_user,
            "can_add_grade": can_add_grade,
            "can_edit": can_edit,
            "can_join_club": can_join_club,
            "can_leave_club": can_leave_club,
            "can_manage_clubs": can_manage_clubs
        }
    )


# ========== ФОРМА ДОБАВЛЕНИЯ УЧЕНИКА (только для админа) ==========
@app.get("/add-student-with-avatar", response_class=HTMLResponse)
async def show_add_form(
        request: Request,
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Показывает форму добавления ученика (только для админа)"""
    if not current_user or current_user.role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    return templates.TemplateResponse(
        "add_student_avatar.html",
        {"request": request, "title": "Добавить ученика с фото"}
    )



# ========== ДОБАВЛЕНИЕ УЧЕНИКА (с созданием пользователя) ==========
@app.post("/add-student-with-avatar")
async def add_student_with_avatar(
        request: Request,
        name: Annotated[str, Form()],
        grade: Annotated[int, Form()],
        hobby: Annotated[str, Form()],
        avatar: UploadFile = File(...),
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """
    ✅ Добавляет нового ученика в базу данных и создаёт пользователя
    """
    # Проверка прав (учитель или админ)
    if not current_user or current_user.role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    # 1. ПРОВЕРЯЕМ КАРТИНКУ
    try:
        validate_image(avatar)
    except HTTPException as e:
        return templates.TemplateResponse(
            "add_student_avatar.html",
            {
                "request": request,
                "title": "Добавить ученика с фото",
                "error": e.detail
            }
        )

    # 2. СОХРАНЯЕМ КАРТИНКУ
    filename = f"{name}_{avatar.filename}"
    filepath = os.path.join(AVATAR_DIR, filename)

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(avatar.file, buffer)

    # 3. СОЗДАЁМ НОВОГО УЧЕНИКА В БД
    new_student = StudentDB(
        name=name,
        grade=grade,
        hobby=hobby,
        avatar=f"/static/avatars/{filename}"
    )
    db.add(new_student)
    db.commit()
    db.refresh(new_student)  # Получаем ID нового ученика

    # 4. ✅ СОЗДАЁМ ПОЛЬЗОВАТЕЛЯ ДЛЯ УЧЕНИКА
    username = transliterate(name)

    # Проверяем, не занят ли логин
    existing_user = db.query(UserDB).filter(UserDB.username == username).first()
    if existing_user:
        # Если логин занят, добавляем ID в конец
        username = f"{username}_{new_student.id}"

    password = generate_password()

    new_user = UserDB(
        username=username,
        password=password,
        role=UserRole.STUDENT,
        student_id=new_student.id
    )
    db.add(new_user)
    db.commit()

    # 5. ПОЛУЧАЕМ ОБНОВЛЁННЫЙ СПИСОК
    students = db.query(StudentDB).all()

    # Определяем права доступа для отображения кнопок
    show_add_button = True
    show_edit_buttons = True
    show_delete_buttons = (current_user.role == UserRole.ADMIN)

    # 6. ВОЗВРАЩАЕМ ГЛАВНУЮ СТРАНИЦУ С ДАННЫМИ ДЛЯ ВХОДА
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "students": students,
            "school_name": "Школа №7",
            "title": "Моя школа",
            "current_user": current_user,
            "show_add_button": show_add_button,
            "show_edit_buttons": show_edit_buttons,
            "show_delete_buttons": show_delete_buttons,
            "success": f"✅ Ученик {name} добавлен!",
            "new_user_info": {
                "username": username,
                "password": password
            }
        }
    )

# ========== УДАЛЕНИЕ УЧЕНИКА (удаляем из БД) по ID ==========

@app.post("/delete-student/{student_id}")
async def delete_student(
    request: Request,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Удаляет ученика (ТОЛЬКО АДМИН)"""
    # Проверка прав
    if not current_user or current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Доступ запрещён. Только для администратора.")

    # Находим ученика
    student = db.query(StudentDB).filter(StudentDB.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Ученик не найден")

    student_name = student.name

    # Удаляем ученика
    db.delete(student)
    db.commit()

    # Получаем обновлённый список
    students = db.query(StudentDB).all()

    # Определяем права доступа для отображения кнопок
    show_add_button = True  # админ может добавлять
    show_edit_buttons = True  # админ может редактировать
    show_delete_buttons = (current_user.role == UserRole.ADMIN)

    # ✅ ВОЗВРАЩАЕМ ШАБЛОН С current_user
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "students": students,
            "school_name": "Школа №7",
            "title": "Моя школа",
            "current_user": current_user,  # ✅ ОБЯЗАТЕЛЬНО!
            "show_add_button": show_add_button,
            "show_edit_buttons": show_edit_buttons,
            "show_delete_buttons": show_delete_buttons,
            "success": f"✅ Ученик {student_name} удалён!"
        }
    )

# ========== РЕДАКТИРОВАНИЕ УЧЕНИКА (учитель и админ) ==========
@app.get("/edit/{student_id}", response_class=HTMLResponse)
async def show_edit_form(
        request: Request,
        student_id: int,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Обновляет данные ученика (только для учителя и админа)"""
    # ✅ ПРОВЕРКА ПРАВ
    if not current_user or current_user.role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    student = db.query(StudentDB).filter(StudentDB.id == student_id).first()

    if not student:
        raise HTTPException(status_code=404, detail="Ученик не найден")

    return templates.TemplateResponse(
        "edit_student.html",
        {
            "request": request,
            "student": student,
            "title": f"Редактировать: {student.name}",
            "current_user": current_user
        }
    )


@app.post("/edit/{student_id}")
async def update_student(
        student_id: int,
        name: Annotated[str, Form()],
        grade: Annotated[int, Form()],
        hobby: Annotated[str, Form()],
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Обновляет данные ученика"""
    student = db.query(StudentDB).filter(StudentDB.id == student_id).first()

    if not student:
        raise HTTPException(status_code=404, detail="Ученик не найден")

    # Обновляем поля
    student.name = name
    student.grade = grade
    student.hobby = hobby

    db.commit()

    # # Перенаправляем на страницу профиля
    # return RedirectResponse(url=f"/student/{name}", status_code=303)

    # Возвращаемся на страницу профиля по ID
    return RedirectResponse(url=f"/student/{student_id}", status_code=303)



# Если нужно обновлять и аватарку
@app.post("/edit/{student_id}/avatar")
async def update_avatar(
    student_id: int,
    avatar: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Optional[UserDB] = Depends(get_current_user_from_session)  # ✅ ДОБАВЛЕНО
):
    """Обновляет аватарку ученика (только для учителя и админа)"""
    # ✅ ПРОВЕРКА ПРАВ
    if not current_user or current_user.role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    """Обновляет аватарку ученика"""
    student = db.query(StudentDB).filter(StudentDB.id == student_id).first()

    if not student:
        raise HTTPException(status_code=404, detail="Ученик не найден")

    try:
        validate_image(avatar)
    except HTTPException as e:
        raise e

    # Сохраняем новую картинку
    filename = f"{student.name}_{avatar.filename}"
    filepath = os.path.join(AVATAR_DIR, filename)

    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(avatar.file, buffer)

    # Обновляем путь к аватарке
    student.avatar = f"/static/avatars/{filename}"
    db.commit()

    # return RedirectResponse(url=f"/student/{student.name}", status_code=303)
    # ✅ ИСПРАВЛЕНО: перенаправляем на ID, а не на имя!
    return RedirectResponse(url=f"/student/{student.id}", status_code=303)

# ========== ДОБАВЛЕНИЕ ОЦЕНКИ (только для учителя и админа) ==========
@app.get("/student/{student_id}/add-grade", response_class=HTMLResponse)
async def show_add_grade_form(
        request: Request,
        student_id: int,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Показывает форму добавления оценки"""
    if not current_user or current_user.role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    student = db.query(StudentDB).filter(StudentDB.id == student_id).first()

    if not student:
        raise HTTPException(status_code=404, detail="Ученик не найден")

    return templates.TemplateResponse(
        "add_grade.html",
        {
            "request": request,
            "student": student,
            "title": f"Добавить оценку: {student.name}"
        }
    )


# ========== ДОБАВЛЕНИЕ ОЦЕНКИ (POST) ==========
@app.post("/student/{student_id}/add-grade")
async def add_grade(
        request: Request,
        student_id: int,
        subject: Annotated[str, Form()],
        score: Annotated[int, Form()],
        date: Annotated[str, Form()],
        comment: Annotated[str, Form()] = "",
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Добавляет новую оценку ученику (только для учителя и админа)"""
    if not current_user or current_user.role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    student = db.query(StudentDB).filter(StudentDB.id == student_id).first()

    if not student:
        raise HTTPException(status_code=404, detail="Ученик не найден")

    new_grade = GradeDB(
        subject=subject,
        score=score,
        date=date,
        comment=comment,
        teacher_name=current_user.username,  # запоминаем, кто поставил оценку
        student_id=student_id
    )

    db.add(new_grade)
    db.commit()

    return RedirectResponse(url=f"/student/{student_id}", status_code=303)



# ========== УДАЛЕНИЕ ОЦЕНКИ (только для учителя и админа) ==========
@app.post("/grade/{grade_id}/delete")
async def delete_grade(
        grade_id: int,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Удаляет оценку"""
    if not current_user or current_user.role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    grade = db.query(GradeDB).filter(GradeDB.id == grade_id).first()

    if not grade:
        raise HTTPException(status_code=404, detail="Оценка не найдена")

    student_id = grade.student_id
    db.delete(grade)
    db.commit()

    return RedirectResponse(url=f"/student/{student_id}", status_code=303)



# ========== КРУЖКИ ==========



# Добавление кружка (админ-функция)
@app.post("/clubs/add")
async def add_club(
    request: Request,
    name: Annotated[str, Form()],
    teacher: Annotated[str, Form()],
    room: Annotated[str, Form()],
    schedule: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
    current_user: Optional[UserDB] = Depends(get_current_user_from_session)  # ✅ ДОБАВЛЕНО
):
    """Добавляет новый кружок (только для админа)"""
    # ✅ ПРОВЕРКА ПРАВ
    if not current_user or current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Доступ запрещён. Только для администратора.")

    """Добавляет новый кружок"""
    new_club = ClubDB(
        name=name,
        teacher=teacher,
        room=room,
        schedule=schedule
    )

    db.add(new_club)
    db.commit() # Сохраняем изменения в БД

    return RedirectResponse(url="/clubs", status_code=303)




# Запись ученика в кружок (через данные формы)
@app.post("/student/{student_id}/join-club")
async def join_club_form(
        student_id: int,
        club_id: Annotated[int, Form()],
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)  # ✅ ДОБАВЛЕНО
):
    """Записывает ученика в кружок (только ученик может записать себя)"""
    # ✅ ПРОВЕРКА ПРАВ: только ученик может записать СЕБЯ
    if not current_user:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    # Только ученик может записать СЕБЯ
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Только ученики могут записываться в кружки")

    # Ученик может записать только себя
    if current_user.student_id != student_id:
        raise HTTPException(status_code=403, detail="Вы можете записать только себя")

    """Записывает ученика в кружок (данные из формы)"""
    # Проверяем, что ученик и кружок существуют
    student = db.query(StudentDB).filter(StudentDB.id == student_id).first()
    club = db.query(ClubDB).filter(ClubDB.id == club_id).first()

    if not student or not club:
        raise HTTPException(status_code=404, detail="Ученик или кружок не найдены")

    # Проверяем, не записан ли уже
    existing = db.query(StudentClubDB).filter(
        StudentClubDB.student_id == student_id,
        StudentClubDB.club_id == club_id
    ).first()

    if not existing:
        # Записываем
        student_club = StudentClubDB(
            student_id=student_id,
            club_id=club_id,
            join_date=datetime.now().strftime("%d.%m.%Y")
        )
        db.add(student_club)
        db.commit() # Сохраняем изменения в БД

    # return RedirectResponse(url=f"/student/{student.name}", status_code=303)
    # ✅ ИСПРАВЛЕНО: перенаправляем на ID, а не на имя!
    return RedirectResponse(url=f"/student/{student_id}", status_code=303)

# Отписать ученика от кружка
@app.post("/student/{student_id}/leave-club/{club_id}")
async def leave_club(
        student_id: int,
        club_id: int,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)  # ✅ ДОБАВЛЕНО
):
    """Отписывает ученика от кружка"""
    # ✅ ПРОВЕРКА ПРАВ
    if not current_user:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    # Только ученик может отписать СЕБЯ
    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Только ученики могут отписываться от кружков")

    if current_user.student_id != student_id:
        raise HTTPException(status_code=403, detail="Вы можете отписать только себя")

    """Отписывает ученика от кружка"""
    student_club = db.query(StudentClubDB).filter(
        StudentClubDB.student_id == student_id,
        StudentClubDB.club_id == club_id
    ).first()

    if student_club:
        db.delete(student_club)
        db.commit()
    return RedirectResponse(url=f"/student/{student_id}", status_code=303)





# ========== АДМИНИСТРАТИВНЫЙ ИНТЕРФЕЙС (ТОЛЬКО ДЛЯ ADMIN) ==========
# Все эндпоинты ниже доступны ТОЛЬКО пользователям с ролью ADMIN

def check_admin(current_user: Optional[UserDB]):
    """Проверяет, является ли пользователь администратором"""
    if not current_user or current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Доступ запрещён. Только для администратора.")



# Страница администрирования кружков
@app.get("/admin/clubs", response_class=HTMLResponse)
async def admin_clubs(
        request: Request,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Административная страница управления кружками (только ADMIN)"""
    check_admin(current_user)

    clubs = db.query(ClubDB).all()
    return templates.TemplateResponse(
        "admin_clubs.html",
        {
            "request": request,
            "clubs": clubs,
            "title": "Управление кружками (админка)",
            "current_user": current_user
        }
    )


# Редактирование кружка
@app.get("/admin/clubs/{club_id}/edit", response_class=HTMLResponse)
async def edit_club_form(
        request: Request,
        club_id: int,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Форма редактирования кружка (только ADMIN)"""
    check_admin(current_user)

    club = db.query(ClubDB).filter(ClubDB.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Кружок не найден")

    return templates.TemplateResponse(
        "edit_club.html",
        {
            "request": request,
            "club": club,
            "title": f"Редактировать: {club.name}",
            "current_user": current_user
        }
    )


@app.post("/admin/clubs/{club_id}/edit")
async def update_club(
        club_id: int,
        name: Annotated[str, Form()],
        teacher: Annotated[str, Form()],
        room: Annotated[str, Form()],
        schedule: Annotated[str, Form()] = "",
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Обновляет данные кружка (только ADMIN)"""
    check_admin(current_user)

    club = db.query(ClubDB).filter(ClubDB.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Кружок не найден")

    club.name = name
    club.teacher = teacher
    club.room = room
    club.schedule = schedule
    db.commit()

    return RedirectResponse(url="/admin/clubs", status_code=303)


# Удаление кружка
@app.post("/admin/clubs/{club_id}/delete")
async def delete_club(
        club_id: int,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Удаляет кружок (только ADMIN)"""
    check_admin(current_user)

    club = db.query(ClubDB).filter(ClubDB.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Кружок не найден")

    db.delete(club)
    db.commit()

    return RedirectResponse(url="/admin/clubs", status_code=303)


# Быстрое добавление нескольких кружков
@app.post("/admin/clubs/bulk-add")
async def bulk_add_clubs(
        request: Request,
        clubs_data: Annotated[str, Form()],
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Массовое добавление кружков (только ADMIN)"""
    check_admin(current_user)
    lines = clubs_data.strip().split('\n')
    added = 0
    errors = []

    for line in lines:
        if line.strip():
            parts = line.split('|')
            if len(parts) >= 3:
                try:
                    new_club = ClubDB(
                        name=parts[0].strip(),
                        teacher=parts[1].strip(),
                        room=parts[2].strip(),
                        schedule=parts[3].strip() if len(parts) > 3 else ""
                    )
                    db.add(new_club)
                    added += 1
                except Exception as e:
                    errors.append(f"Ошибка в строке '{line}': {e}")

    if added > 0:
        db.commit()

    clubs = db.query(ClubDB).all()

    return templates.TemplateResponse(
        "admin_clubs.html",
        {
            "request": request,
            "clubs": clubs,
            "title": "Управление кружками (админка)",
            "success": f"✅ Добавлено {added} кружков",
            "errors": errors if errors else None
        }
    )


# ========== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ (ТОЛЬКО ДЛЯ ADMIN) ==========

@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(
        request: Request,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Страница управления пользователями (только ADMIN)"""
    check_admin(current_user)

    # Получаем всех пользователей с информацией об учениках
    users = db.query(UserDB).all()

    return templates.TemplateResponse(
        "admin_users.html",
        {
            "request": request,
            "users": users,
            "title": "Управление пользователями",
            "current_user": current_user
        }
    )


@app.post("/admin/users/{user_id}/reset-password")
async def reset_user_password(
        request: Request,  # ✅ ДОБАВЛЯЕМ request!
        user_id: int,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Сброс пароля пользователя (только ADMIN)"""
    check_admin(current_user)

    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Генерируем новый пароль
    new_password = generate_password()
    user.password = new_password
    db.commit()

    # Возвращаемся на страницу управления с новым паролем
    users = db.query(UserDB).all()

    return templates.TemplateResponse(
        "admin_users.html",
        {
            "request": request,  # ✅ ТЕПЕРЬ request определён
            "users": users,
            "title": "Управление пользователями",
            "current_user": current_user,
            "success": f"Пароль для {user.username} сброшен!",
            "new_password": new_password,
            "reset_user_id": user_id
        }
    )


@app.post("/admin/users/{user_id}/delete")
async def delete_user(
        user_id: int,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Удаляет пользователя (только ADMIN)"""
    check_admin(current_user)

    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    # Нельзя удалить самого себя
    if user.id == current_user.id:
        raise HTTPException(status_code=403, detail="Нельзя удалить самого себя")

    db.delete(user)
    db.commit()

    return RedirectResponse(url="/admin/users", status_code=303)

# ========== СПИСОК КРУЖКОВ (все могут смотреть) ==========
@app.get("/clubs", response_class=HTMLResponse)
async def list_clubs(
        request: Request,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Показывает список всех кружков (доступно всем)"""
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    clubs = db.query(ClubDB).all()
    return templates.TemplateResponse(
        "clubs_list.html",
        {
            "request": request,
            "clubs": clubs,
            "title": "Кружки и секции",
            "current_user": current_user
        }
    )