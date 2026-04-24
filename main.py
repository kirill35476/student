# main.py

from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi import Form, UploadFile, File
from typing import Annotated, Optional
import shutil
import os
from sqlalchemy.orm import Session
from datetime import datetime
from fastapi import Cookie
from database import get_db, create_test_users, StudentDB, GradeDB, ClubDB, StudentClubDB, UserDB, UserRole, check_permission, get_current_user, SessionLocal
from contextlib import asynccontextmanager

# Настройки для загрузки картинок
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


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


# Простая система сессий
active_sessions = {}

def generate_session_token():
    """Генерирует простой токен для сессии"""
    import hashlib
    import time
    return hashlib.md5(f"{time.time()}{os.urandom(16)}".encode()).hexdigest()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Запускается при старте приложения"""
    print("🚀 Запускаем приложение...")
    db = SessionLocal()
    try:
        create_test_users(db)
    finally:
        db.close()
    print("✅ Приложение готово к работе!")
    yield
    print("👋 Останавливаем приложение...")


app = FastAPI(title="Школа с БД", lifespan=lifespan)

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
    """Получает текущего пользователя из cookie"""
    if not session_token or session_token not in active_sessions:
        return None
    username = active_sessions[session_token]
    user = db.query(UserDB).filter(UserDB.username == username).first()
    return user


# ========== СТРАНИЦА ВХОДА ==========
@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Показывает страницу входа в систему"""
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
    """Обрабатывает форму входа"""
    user = db.query(UserDB).filter(
        UserDB.username == username,
        UserDB.password == password
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

    session_token = generate_session_token()
    active_sessions[session_token] = user.username

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="session_token", value=session_token, httponly=True)
    return response


@app.get("/logout")
async def logout():
    """Выход из системы"""
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_token")
    return response


# ========== ГЛАВНАЯ СТРАНИЦА ==========
@app.get("/", response_class=HTMLResponse)
async def home(
        request: Request,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    if current_user.role == UserRole.STUDENT:
        student = db.query(StudentDB).filter(StudentDB.id == current_user.student_id).first()
        students = [student] if student else []
        show_add_button = False
        show_delete_buttons = False
        show_edit_buttons = False
    else:
        students = db.query(StudentDB).all()
        show_add_button = True
        show_edit_buttons = True
        show_delete_buttons = (current_user.role == UserRole.ADMIN)

    clubs = db.query(ClubDB).all()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "students": students,
            "clubs": clubs,
            "school_name": "Школа №7",
            "title": "Моя школа",
            "current_user": current_user,
            "show_add_button": show_add_button,
            "show_edit_buttons": show_edit_buttons,
            "show_delete_buttons": show_delete_buttons
        }
    )


# ========== УДАЛЕНИЕ УЧЕНИКА (POST) ==========
@app.post("/delete-student/{student_id}")
async def delete_student(
    request: Request,
    student_id: int,
    db: Session = Depends(get_db),
    current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Удаляет ученика (ТОЛЬКО АДМИН)"""
    if not current_user or current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    student = db.query(StudentDB).filter(StudentDB.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Ученик не найден")

    student_name = student.name
    db.delete(student)
    db.commit()

    students = db.query(StudentDB).all()
    clubs = db.query(ClubDB).all()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "students": students,
            "clubs": clubs,
            "school_name": "Школа №7",
            "title": "Моя школа",
            "current_user": current_user,
            "show_add_button": True,
            "show_edit_buttons": True,
            "show_delete_buttons": True,
            "success": f"✅ Ученик {student_name} удалён!"
        }
    )


# ========== СТРАНИЦА ПРОФИЛЯ ==========
@app.get("/student/{student_id}", response_class=HTMLResponse)
async def student_profile(
        request: Request,
        student_id: int,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    if current_user.role == UserRole.STUDENT:
        if current_user.student_id != student_id:
            raise HTTPException(status_code=403, detail="У вас нет доступа к этому профилю")

    student = db.query(StudentDB).filter(StudentDB.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Ученик не найден")

    all_clubs = db.query(ClubDB).all()

    can_add_grade = current_user.role != UserRole.STUDENT
    can_edit = current_user.role != UserRole.STUDENT
    can_join_club = current_user.role == UserRole.STUDENT
    can_leave_club = current_user.role == UserRole.STUDENT
    can_manage_clubs = current_user.role == UserRole.ADMIN

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


# ========== ФОРМА ДОБАВЛЕНИЯ УЧЕНИКА ==========
@app.get("/add-student-with-avatar", response_class=HTMLResponse)
async def show_add_form(
        request: Request,
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Показывает форму добавления ученика (только для учителя и админа)"""
    if not current_user or current_user.role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    return templates.TemplateResponse(
        "add_student_avatar.html",
        {"request": request, "title": "Добавить ученика с фото"}
    )


# ========== ДОБАВЛЕНИЕ УЧЕНИКА (POST) ==========
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
    """Добавляет нового ученика и создаёт пользователя"""
    if not current_user or current_user.role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    # Проверяем картинку
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

    # Сохраняем картинку
    filename = f"{name}_{avatar.filename}"
    filepath = os.path.join(AVATAR_DIR, filename)
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(avatar.file, buffer)

    # Создаём ученика
    new_student = StudentDB(
        name=name,
        grade=grade,
        hobby=hobby,
        avatar=f"/static/avatars/{filename}"
    )
    db.add(new_student)
    db.commit()
    db.refresh(new_student)

    # 4. СОЗДАЁМ ПОЛЬЗОВАТЕЛЯ ДЛЯ УЧЕНИКА
    username = transliterate(name)

    # Проверяем, не занят ли логин
    existing_username = db.query(UserDB).filter(UserDB.username == username).first()
    if existing_username:
        # Если логин занят, добавляем ID в конец
        username = f"{username}_{new_student.id}"

    password = generate_password()

    # Проверяем, есть ли уже пользователь с таким student_id
    existing_student_user = db.query(UserDB).filter(UserDB.student_id == new_student.id).first()
    if existing_student_user:
        # Обновляем существующего пользователя
        # НЕ меняем username, если он уже существует у другого пользователя
        if not db.query(UserDB).filter(UserDB.username == username, UserDB.id != existing_student_user.id).first():
            existing_student_user.username = username
        existing_student_user.password = password
    else:
        # Создаём нового пользователя
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
    clubs = db.query(ClubDB).all()

    # Определяем права доступа для отображения кнопок
    show_add_button = True
    show_edit_buttons = True
    show_delete_buttons = (current_user.role == UserRole.ADMIN)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "students": students,
            "clubs": clubs,
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


# ========== РЕДАКТИРОВАНИЕ УЧЕНИКА ==========
@app.get("/edit/{student_id}", response_class=HTMLResponse)
async def show_edit_form(
        request: Request,
        student_id: int,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Показывает форму редактирования ученика"""
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

    student.name = name
    student.grade = grade
    student.hobby = hobby
    db.commit()

    return RedirectResponse(url=f"/student/{student_id}", status_code=303)


@app.post("/edit/{student_id}/avatar")
async def update_avatar(
    student_id: int,
    avatar: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Обновляет аватарку ученика"""
    if not current_user or current_user.role == UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    student = db.query(StudentDB).filter(StudentDB.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Ученик не найден")

    try:
        validate_image(avatar)
    except HTTPException as e:
        raise e

    filename = f"{student.name}_{avatar.filename}"
    filepath = os.path.join(AVATAR_DIR, filename)
    with open(filepath, "wb") as buffer:
        shutil.copyfileobj(avatar.file, buffer)

    student.avatar = f"/static/avatars/{filename}"
    db.commit()

    return RedirectResponse(url=f"/student/{student.id}", status_code=303)


# ========== ДОБАВЛЕНИЕ ОЦЕНКИ ==========
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
    """Добавляет новую оценку"""
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
        teacher_name=current_user.username,
        student_id=student_id
    )
    db.add(new_grade)
    db.commit()

    return RedirectResponse(url=f"/student/{student_id}", status_code=303)


# ========== УДАЛЕНИЕ ОЦЕНКИ ==========
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
@app.post("/clubs/add")
async def add_club(
    request: Request,
    name: Annotated[str, Form()],
    teacher: Annotated[str, Form()],
    room: Annotated[str, Form()],
    schedule: Annotated[str, Form()] = "",
    db: Session = Depends(get_db),
    current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Добавляет новый кружок (только для админа)"""
    if not current_user or current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    new_club = ClubDB(
        name=name,
        teacher=teacher,
        room=room,
        schedule=schedule
    )
    db.add(new_club)
    db.commit()

    return RedirectResponse(url="/clubs", status_code=303)


@app.post("/student/{student_id}/join-club")
async def join_club_form(
        student_id: int,
        club_id: Annotated[int, Form()],
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Записывает ученика в кружок"""
    if not current_user:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Только ученики могут записываться в кружки")

    if current_user.student_id != student_id:
        raise HTTPException(status_code=403, detail="Вы можете записать только себя")

    student = db.query(StudentDB).filter(StudentDB.id == student_id).first()
    club = db.query(ClubDB).filter(ClubDB.id == club_id).first()

    if not student or not club:
        raise HTTPException(status_code=404, detail="Ученик или кружок не найдены")

    existing = db.query(StudentClubDB).filter(
        StudentClubDB.student_id == student_id,
        StudentClubDB.club_id == club_id
    ).first()

    if not existing:
        student_club = StudentClubDB(
            student_id=student_id,
            club_id=club_id,
            join_date=datetime.now().strftime("%d.%m.%Y")
        )
        db.add(student_club)
        db.commit()

    return RedirectResponse(url=f"/student/{student_id}", status_code=303)


@app.post("/student/{student_id}/leave-club/{club_id}")
async def leave_club(
        student_id: int,
        club_id: int,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Отписывает ученика от кружка"""
    if not current_user:
        raise HTTPException(status_code=403, detail="Доступ запрещён")

    if current_user.role != UserRole.STUDENT:
        raise HTTPException(status_code=403, detail="Только ученики могут отписываться от кружков")

    if current_user.student_id != student_id:
        raise HTTPException(status_code=403, detail="Вы можете отписать только себя")

    student_club = db.query(StudentClubDB).filter(
        StudentClubDB.student_id == student_id,
        StudentClubDB.club_id == club_id
    ).first()

    if student_club:
        db.delete(student_club)
        db.commit()

    return RedirectResponse(url=f"/student/{student_id}", status_code=303)


# ========== ЛИДЕРЫ ==========
@app.get("/leaders", response_class=HTMLResponse)
async def leaders_board(
    request: Request,
    grade: str = "all",
    min_avg: str = "0",
    sort: str = "avg_desc",
    db: Session = Depends(get_db),
    current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Страница с рейтингом учеников"""
    if not current_user:
        return RedirectResponse(url="/login", status_code=303)

    query = db.query(StudentDB)
    if grade != "all":
        query = query.filter(StudentDB.grade == int(grade))
    students = query.all()

    leaders = []
    for student in students:
        grades = student.grades
        if grades:
            avg_score = sum(g.score for g in grades) / len(grades)
            grades_count = len(grades)
        else:
            avg_score = 0
            grades_count = 0

        subject_scores = {}
        for g in grades:
            if g.subject not in subject_scores:
                subject_scores[g.subject] = []
            subject_scores[g.subject].append(g.score)

        best_subject = None
        if subject_scores:
            best_subject = max(subject_scores.items(), key=lambda x: sum(x[1])/len(x[1]))[0]

        leaders.append({
            'id': student.id,
            'name': student.name,
            'grade': student.grade,
            'avatar': student.avatar,
            'average_score': avg_score,
            'grades_count': grades_count,
            'clubs_count': len(student.clubs),
            'best_subject': best_subject
        })

    min_avg_float = float(min_avg)
    if min_avg_float > 0:
        leaders = [l for l in leaders if l['average_score'] >= min_avg_float]

    if sort == "avg_desc":
        leaders.sort(key=lambda x: x['average_score'], reverse=True)
    elif sort == "avg_asc":
        leaders.sort(key=lambda x: x['average_score'])
    elif sort == "name_asc":
        leaders.sort(key=lambda x: x['name'])
    elif sort == "name_desc":
        leaders.sort(key=lambda x: x['name'], reverse=True)
    elif sort == "grade_asc":
        leaders.sort(key=lambda x: x['grade'])
    elif sort == "grade_desc":
        leaders.sort(key=lambda x: x['grade'], reverse=True)

    all_students = db.query(StudentDB).all()
    all_grades = db.query(GradeDB).all()
    total_grades = len(all_grades)
    school_average = sum(g.score for g in all_grades) / total_grades if total_grades > 0 else 0
    excellent_count = len([l for l in leaders if l['average_score'] >= 4.5])

    stats = {
        'total_students': len(all_students),
        'total_grades': total_grades,
        'school_average': school_average,
        'excellent_count': excellent_count
    }

    return templates.TemplateResponse(
        "leaders.html",
        {
            "request": request,
            "leaders": leaders,
            "stats": stats,
            "current_grade": grade,
            "current_min_avg": min_avg,
            "current_sort": sort,
            "title": "Лидеры успеваемости",
            "current_user": current_user,
            "school_name": "Школа №7"
        }
    )


# ========== АДМИНИСТРАТИВНЫЙ ИНТЕРФЕЙС ==========
def check_admin(current_user: Optional[UserDB]):
    """Проверяет, является ли пользователь администратором"""
    if not current_user or current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Доступ запрещён")


@app.get("/admin/clubs", response_class=HTMLResponse)
async def admin_clubs(
        request: Request,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Страница управления кружками (только ADMIN)"""
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


@app.get("/admin/clubs/{club_id}/edit", response_class=HTMLResponse)
async def edit_club_form(
        request: Request,
        club_id: int,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Форма редактирования кружка"""
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
    """Обновляет данные кружка"""
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


@app.post("/admin/clubs/{club_id}/delete")
async def delete_club(
        club_id: int,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Удаляет кружок"""
    check_admin(current_user)
    club = db.query(ClubDB).filter(ClubDB.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Кружок не найден")
    db.delete(club)
    db.commit()
    return RedirectResponse(url="/admin/clubs", status_code=303)


@app.post("/admin/clubs/bulk-add")
async def bulk_add_clubs(
        request: Request,
        clubs_data: Annotated[str, Form()],
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Массовое добавление кружков"""
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


# ========== УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ==========
@app.get("/admin/users", response_class=HTMLResponse)
async def admin_users(
        request: Request,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Страница управления пользователями"""
    check_admin(current_user)
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
        request: Request,
        user_id: int,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Сброс пароля пользователя"""
    check_admin(current_user)
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    new_password = generate_password()
    user.password = new_password
    db.commit()

    users = db.query(UserDB).all()
    return templates.TemplateResponse(
        "admin_users.html",
        {
            "request": request,
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
    """Удаляет пользователя"""
    check_admin(current_user)
    user = db.query(UserDB).filter(UserDB.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if user.id == current_user.id:
        raise HTTPException(status_code=403, detail="Нельзя удалить самого себя")

    db.delete(user)
    db.commit()
    return RedirectResponse(url="/admin/users", status_code=303)


# ========== СПИСОК КРУЖКОВ ==========
@app.get("/clubs", response_class=HTMLResponse)
async def list_clubs(
        request: Request,
        db: Session = Depends(get_db),
        current_user: Optional[UserDB] = Depends(get_current_user_from_session)
):
    """Показывает список всех кружков"""
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