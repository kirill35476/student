# модуль 2 урок 3 (7) добавили работу с базой данных
# main.py
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi import Form, UploadFile, File
from typing import Annotated
import shutil
import os

from sqlalchemy.orm import Session
from database import get_db, StudentDB, GradeDB, ClubDB, StudentClubDB
from datetime import datetime



# Настройки для загрузки картинок
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


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


app = FastAPI(title="Школа с БД")

# Подключаем статику и шаблоны
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Папка для аватарок
AVATAR_DIR = "static/avatars"
os.makedirs(AVATAR_DIR, exist_ok=True)


# ========== ГЛАВНАЯ СТРАНИЦА (читаем из БД) ==========
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    """
    Главная страница со списком учеников
    Теперь данные берём из базы данных!
    """
    # ✅ Получаем всех учеников из БД
    students = db.query(StudentDB).all()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "students": students,
            "school_name": "Школа №7",
            "title": "Моя школа"
        }
    )



# ========== СТРАНИЦА ПРОФИЛЯ (с оценками и кружками) ==========
@app.get("/student/{student_name}", response_class=HTMLResponse)
async def student_profile(request: Request, student_name: str, db: Session = Depends(get_db)):
    """
    Страница ученика с оценками и кружками
    """
    # Ищем ученика в БД по имени (с подгрузкой оценок и кружков)
    student = db.query(StudentDB).filter(StudentDB.name == student_name).first()

    if not student:
        return templates.TemplateResponse(
            "404.html",
            {"request": request, "name": student_name}
        )

    # Получаем все кружки для выпадающего списка
    all_clubs = db.query(ClubDB).all()

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "student": student,
            "all_clubs": all_clubs,
            "title": f"Профиль: {student.name}"
        }
    )


# ========== ГЛАВНАЯ СТРАНИЦА (читаем из БД) ==========
@app.get("/", response_class=HTMLResponse)
async def home(request: Request, db: Session = Depends(get_db)):
    """
    Главная страница со списком учеников и кружков
    """
    # ✅ Получаем всех учеников из БД
    students = db.query(StudentDB).all()

    # ✅ Получаем все кружки для отображения
    clubs = db.query(ClubDB).limit(6).all()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "students": students,
            "clubs": clubs,  # Добавляем кружки
            "school_name": "Школа №7",
            "title": "Моя школа"
        }
    )
# ========== ФОРМА ДОБАВЛЕНИЯ ==========
@app.get("/add-student-with-avatar", response_class=HTMLResponse)
async def show_add_form(request: Request):
    """Показывает форму добавления ученика"""
    return templates.TemplateResponse(
        "add_student_avatar.html",
        {"request": request, "title": "Добавить ученика с фото"}
    )


# ========== СТРАНИЦА ЛИДЕРОВ С ФИЛЬТРАМИ ==========
@app.get("/leaders", response_class=HTMLResponse)
async def leaders_board(
        request: Request,
        grade: str = "all",
        min_avg: str = "0",
        sort: str = "avg_desc",
        db: Session = Depends(get_db)
):
    """
    Страница с рейтингом учеников по среднему баллу
    с возможностью фильтрации по классу и сортировки
    """
    # Базовый запрос всех учеников
    query = db.query(StudentDB)

    # Фильтр по классу
    if grade != "all":
        query = query.filter(StudentDB.grade == int(grade))

    students = query.all()

    # Собираем статистику для каждого ученика
    leaders_data = []
    for student in students:
        grades = student.grades
        if grades:
            avg_score = sum(g.score for g in grades) / len(grades)

            # Находим лучший предмет
            subject_scores = {}
            for g in grades:
                if g.subject not in subject_scores:
                    subject_scores[g.subject] = []
                subject_scores[g.subject].append(g.score)

            best_subject = None
            best_avg = 0
            for subject, scores in subject_scores.items():
                subject_avg = sum(scores) / len(scores)
                if subject_avg > best_avg:
                    best_avg = subject_avg
                    best_subject = subject

            leaders_data.append({
                'student': student,
                'average_score': avg_score,
                'grades_count': len(grades),
                'clubs_count': len(student.clubs),
                'best_subject': best_subject,
                'best_subject_avg': best_avg
            })
        else:
            leaders_data.append({
                'student': student,
                'average_score': 0,
                'grades_count': 0,
                'clubs_count': len(student.clubs),
                'best_subject': None,
                'best_subject_avg': 0
            })

    # Фильтр по минимальному среднему баллу
    min_avg_float = float(min_avg)
    if min_avg_float > 0:
        leaders_data = [d for d in leaders_data if d['average_score'] >= min_avg_float]

    # Сортировка
    if sort == "avg_desc":
        leaders_data.sort(key=lambda x: x['average_score'], reverse=True)
    elif sort == "avg_asc":
        leaders_data.sort(key=lambda x: x['average_score'])
    elif sort == "name_asc":
        leaders_data.sort(key=lambda x: x['student'].name)
    elif sort == "name_desc":
        leaders_data.sort(key=lambda x: x['student'].name, reverse=True)
    elif sort == "grade_asc":
        leaders_data.sort(key=lambda x: x['student'].grade)
    elif sort == "grade_desc":
        leaders_data.sort(key=lambda x: x['student'].grade, reverse=True)

    # Подготовка данных для шаблона
    leaders = []
    for data in leaders_data:
        leaders.append({
            'id': data['student'].id,
            'name': data['student'].name,
            'grade': data['student'].grade,
            'avatar': data['student'].avatar,
            'average_score': data['average_score'],
            'grades_count': data['grades_count'],
            'clubs_count': data['clubs_count'],
            'best_subject': data['best_subject']
        })

    # Общая статистика
    all_students = db.query(StudentDB).all()
    all_grades = db.query(GradeDB).all()

    total_grades = len(all_grades)
    school_average = sum(g.score for g in all_grades) / total_grades if total_grades > 0 else 0

    # Считаем отличников (средний балл >= 4.5)
    excellent_count = len([l for l in leaders_data if l['average_score'] >= 4.5])

    stats = {
        'total_students': len(all_students),
        'total_grades': total_grades,
        'school_average': school_average,
        'excellent_count': excellent_count
    }

    # Статистика по классам
    class_stats = []
    for g in range(1, 12):
        class_students = [s for s in students if s.grade == g]
        if class_students:
            class_grades = []
            for s in class_students:
                class_grades.extend(s.grades)

            if class_grades:
                class_avg = sum(gr.score for gr in class_grades) / len(class_grades)
            else:
                class_avg = 0

            class_stats.append({
                'grade': g,
                'students_count': len(class_students),
                'total_grades': len(class_grades),
                'avg_score': class_avg
            })

    return templates.TemplateResponse(
        "leaders.html",
        {
            "request": request,
            "leaders": leaders,
            "stats": stats,
            "class_stats": class_stats,
            "current_grade": grade,
            "current_min_avg": min_avg,
            "current_sort": sort,
            "title": "Лидеры успеваемости"
        }
    )
# ========== ДОБАВЛЕНИЕ УЧЕНИКА (сохраняем в БД) ==========
@app.post("/add-student-with-avatar")
async def add_student_with_avatar(
        request: Request,
        name: Annotated[str, Form()],
        grade: Annotated[int, Form()],
        hobby: Annotated[str, Form()],
        avatar: UploadFile = File(...),
        db: Session = Depends(get_db)
):
    """
    ✅ Добавляет нового ученика в базу данных
    """
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

    # ✅ СОЗДАЁМ НОВОГО УЧЕНИКА В БД
    new_student = StudentDB(
        name=name,
        grade=grade,
        hobby=hobby,
        avatar=f"/static/avatars/{filename}"
    )

    # Добавляем в базу данных
    db.add(new_student)
    db.commit()
    db.refresh(new_student)  # Получаем ID, который создала БД

    # Получаем всех учеников для отображения
    students = db.query(StudentDB).all()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "students": students,
            "school_name": "Школа №7",
            "title": "Моя школа",
            "success": f"Ученик {name} добавлен с фото!"
        }
    )

# ========== РЕДАКТИРОВАНИЕ УЧЕНИКА ==========
@app.get("/edit/{student_id}", response_class=HTMLResponse)
async def show_edit_form(request: Request, student_id: int, db: Session = Depends(get_db)):
    """Показывает форму редактирования ученика"""
    student = db.query(StudentDB).filter(StudentDB.id == student_id).first()

    if not student:
        raise HTTPException(status_code=404, detail="Ученик не найден")

    return templates.TemplateResponse(
        "edit_student.html",
        {
            "request": request,
            "student": student,
            "title": f"Редактировать: {student.name}"
        }
    )


@app.post("/edit/{student_id}")
async def update_student(
        request: Request,
        student_id: int,
        name: Annotated[str, Form()],
        grade: Annotated[int, Form()],
        hobby: Annotated[str, Form()],
        db: Session = Depends(get_db)
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

    # Перенаправляем на страницу профиля
    return RedirectResponse(url=f"/student/{name}", status_code=303)


# Если нужно обновлять и аватарку
@app.post("/edit/{student_id}/avatar")
async def update_avatar(
        student_id: int,
        avatar: UploadFile = File(...),
        db: Session = Depends(get_db)
):
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

    return RedirectResponse(url=f"/student/{student.name}", status_code=303)



# ========== УДАЛЕНИЕ УЧЕНИКА (удаляем из БД) ==========
@app.get("/delete-student/{student_name}")
async def delete_student(request: Request, student_name: str, db: Session = Depends(get_db)):
    """
    ✅ Удаляет ученика из базы данных
    """
    # ✅ Находим ученика в БД
    student = db.query(StudentDB).filter(StudentDB.name == student_name).first()

    if not student:
        return templates.TemplateResponse(
            "404.html",
            {"request": request, "name": student_name}
        )

    # Удаляем из базы данных
    db.delete(student)
    db.commit()

    # Получаем обновлённый список
    students = db.query(StudentDB).all()

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "students": students,
            "school_name": "Школа №7",
            "title": "Моя школа",
            "success": f"Ученик {student_name} удалён!"
        }
    )




# ========== ДОБАВЛЕНИЕ ОЦЕНКИ ==========
@app.get("/student/{student_id}/add-grade", response_class=HTMLResponse)
async def show_add_grade_form(request: Request, student_id: int, db: Session = Depends(get_db)):
    """Показывает форму добавления оценки"""
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
        db: Session = Depends(get_db)
):
    """Добавляет новую оценку ученику"""
    # Находим ученика
    student = db.query(StudentDB).filter(StudentDB.id == student_id).first()

    if not student:
        raise HTTPException(status_code=404, detail="Ученик не найден")

    # Создаём оценку
    new_grade = GradeDB(
        subject=subject,
        score=score,
        date=date,
        comment=comment,
        student_id=student_id
    )

    db.add(new_grade)
    db.commit() # Сохраняем изменения в БД

    # Показываем обновлённый профиль
    all_clubs = db.query(ClubDB).all()

    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "student": student,
            "all_clubs": all_clubs,
            "title": f"Профиль: {student.name}",
            "success": f"Оценка по {subject} добавлена!"
        }
    )


# ========== УДАЛЕНИЕ ОЦЕНКИ ==========
@app.post("/grade/{grade_id}/delete")
async def delete_grade(
        request: Request,
        grade_id: int,
        db: Session = Depends(get_db)
):
    """Удаляет оценку"""
    grade = db.query(GradeDB).filter(GradeDB.id == grade_id).first()

    if not grade:
        raise HTTPException(status_code=404, detail="Оценка не найдена")

    student_id = grade.student_id
    db.delete(grade)
    db.commit()

    # Возвращаемся к профилю ученика
    return RedirectResponse(url=f"/student/{student_id}", status_code=303)


# ========== КРУЖКИ ==========
@app.get("/clubs", response_class=HTMLResponse)
async def list_clubs(request: Request, db: Session = Depends(get_db)):
    """Показывает список всех кружков"""
    clubs = db.query(ClubDB).all()
    return templates.TemplateResponse(
        "clubs_list.html",
        {
            "request": request,
            "clubs": clubs,
            "title": "Кружки и секции"
        }
    )


# Добавление кружка (админ-функция)
@app.post("/clubs/add")
async def add_club(
        request: Request,
        name: Annotated[str, Form()],
        teacher: Annotated[str, Form()],
        room: Annotated[str, Form()],
        schedule: Annotated[str, Form()] = "",
        db: Session = Depends(get_db)
):
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
    db: Session = Depends(get_db)
):
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

    return RedirectResponse(url=f"/student/{student.name}", status_code=303)


# Отписать ученика от кружка
@app.post("/student/{student_id}/leave-club/{club_id}")
async def leave_club(
        student_id: int,
        club_id: int,
        db: Session = Depends(get_db)
):
    """Отписывает ученика от кружка"""
    student_club = db.query(StudentClubDB).filter(
        StudentClubDB.student_id == student_id,
        StudentClubDB.club_id == club_id
    ).first()

    if student_club:
        db.delete(student_club)
        db.commit()

    return RedirectResponse(url=f"/student/{student_id}", status_code=303)









# ========== АДМИНИСТРАТИВНЫЙ ИНТЕРФЕЙС ==========

# Страница администрирования кружков
@app.get("/admin/clubs", response_class=HTMLResponse)
async def admin_clubs(request: Request, db: Session = Depends(get_db)):
    """
    Административная страница управления кружками
    """
    clubs = db.query(ClubDB).all()
    return templates.TemplateResponse(
        "admin_clubs.html",
        {
            "request": request,
            "clubs": clubs,
            "title": "Управление кружками (админка)"
        }
    )


# Редактирование кружка
@app.get("/admin/clubs/{club_id}/edit", response_class=HTMLResponse)
async def edit_club_form(request: Request, club_id: int, db: Session = Depends(get_db)):
    """Форма редактирования кружка"""
    club = db.query(ClubDB).filter(ClubDB.id == club_id).first()
    if not club:
        raise HTTPException(status_code=404, detail="Кружок не найден")

    return templates.TemplateResponse(
        "edit_club.html",
        {
            "request": request,
            "club": club,
            "title": f"Редактировать: {club.name}"
        }
    )


@app.post("/admin/clubs/{club_id}/edit")
async def update_club(
        club_id: int,
        name: Annotated[str, Form()],
        teacher: Annotated[str, Form()],
        room: Annotated[str, Form()],
        schedule: Annotated[str, Form()] = "",
        db: Session = Depends(get_db)
):
    """Обновляет данные кружка"""
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
async def delete_club(club_id: int, db: Session = Depends(get_db)):
    """Удаляет кружок"""
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
        db: Session = Depends(get_db)
):
    """
    Добавляет несколько кружков одной строкой
    Формат: Название|Учитель|Кабинет|Расписание
    Каждая строка - новый кружок
    """
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

