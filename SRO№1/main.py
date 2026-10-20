from datetime import datetime, timedelta, timezone

from bson import ObjectId
from pymongo import MongoClient, ASCENDING
from pymongo.errors import PyMongoError


# =========================================================
# РЕЕСТР УЧЕБНЫХ ПРОЕКТОВ — СРО, ВАРИАНТ 7
# Технология: MongoDB + Python
# =========================================================

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "student_project_registry"


def connect_db():
    """Подключение к MongoDB и создание индексов."""
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)
    client.admin.command("ping")
    db = client[DB_NAME]

    db.projects.create_index("status")
    db.projects.create_index("owner_id")
    db.users.create_index("email", unique=True)
    db.tasks.create_index([("assignee_id", 1), ("status", 1)])
    db.tasks.create_index([("project_id", 1), ("status", 1)])
    db.tasks.create_index([("status", 1), ("due_date", 1)])

    return client, db


def seed_database(db):
    """Заполнение базы 5 проектами, 10 пользователями и 30 задачами."""
    if db.projects.count_documents({}) > 0:
        print("База уже содержит проекты. Повторное заполнение пропущено.")
        return

    users = []
    for i in range(1, 11):
        users.append({
            "full_name": f"Студент {i:02d}",
            "email": f"student{i:02d}@example.com",
            "role": "teacher" if i == 1 else "student",
            "group": "ИС-23" if i <= 5 else "ИС-24"
        })

    user_ids = db.users.insert_many(users).inserted_ids
    now = datetime.now(timezone.utc)

    projects = []
    for i in range(1, 6):
        projects.append({
            "title": f"Учебный проект {i}",
            "description": f"Описание учебного проекта {i}",
            "status": "active" if i < 5 else "planning",
            "owner_id": user_ids[0],
            "member_ids": [
                user_ids[(i + j) % len(user_ids)]
                for j in range(1, 4)
            ],
            "created_at": now - timedelta(days=i * 3)
        })

    project_ids = db.projects.insert_many(projects).inserted_ids

    statuses = ["todo", "in_progress", "done", "cancelled"]
    priorities = ["low", "medium", "high"]

    tasks = []
    for i in range(30):
        tasks.append({
            "project_id": project_ids[i % 5],
            "title": f"Задача {i + 1:02d}",
            "description": "Синтетическая задача для демонстрации",
            "assignee_id": user_ids[(i % 9) + 1],
            "status": statuses[i % 4],
            "priority": priorities[i % 3],
            "due_date": now + timedelta(days=(i % 13) - 6),
            "created_at": now
        })

    db.tasks.insert_many(tasks)

    print("База успешно заполнена.")
    print("Проекты:", db.projects.count_documents({}))
    print("Пользователи:", db.users.count_documents({}))
    print("Задачи:", db.tasks.count_documents({}))


def show_documents(documents):
    """Вывод документов в консоль."""
    documents = list(documents)

    if not documents:
        print("Записи не найдены.")
        return

    for document in documents:
        for key, value in document.items():
            if isinstance(value, ObjectId):
                document[key] = str(value)
        print(document)


def get_id(collection_name, db):
    """Получение ID существующей записи."""
    show_documents(db[collection_name].find())
    value = input("Введите ObjectId: ").strip()

    if not ObjectId.is_valid(value):
        raise ValueError("Некорректный ObjectId")

    return ObjectId(value)


# =========================================================
# CRUD-ОПЕРАЦИИ
# =========================================================

def create_user(db):
    name = input("ФИО: ").strip()
    email = input("Email: ").strip().lower()

    if not name or "@" not in email:
        print("Укажите ФИО и корректный email.")
        return

    user_id = db.users.insert_one({
        "full_name": name,
        "email": email,
        "role": "student",
        "group": "ИС-23"
    }).inserted_id

    print("Пользователь создан:", user_id)


def create_project(db):
    print("Выберите руководителя из списка пользователей.")
    owner_id = get_id("users", db)

    title = input("Название проекта: ").strip()
    description = input("Описание: ").strip()

    if not title:
        print("Название не может быть пустым.")
        return

    project_id = db.projects.insert_one({
        "title": title,
        "description": description,
        "status": "active",
        "owner_id": owner_id,
        "member_ids": [owner_id],
        "created_at": datetime.now(timezone.utc)
    }).inserted_id

    print("Проект создан:", project_id)


def create_task(db):
    print("Выберите проект:")
    project_id = get_id("projects", db)

    if db.projects.find_one({"_id": project_id}) is None:
        print("Проект не найден.")
        return

    print("Выберите исполнителя:")
    assignee_id = get_id("users", db)

    if db.users.find_one({"_id": assignee_id}) is None:
        print("Исполнитель не найден.")
        return

    title = input("Название задачи: ").strip()
    if not title:
        print("Название задачи не может быть пустым.")
        return

    due = input("Срок (ГГГГ-ММ-ДД), например 2026-11-30: ")

    try:
        due_date = datetime.strptime(due, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        print("Неверный формат даты.")
        return

    task_id = db.tasks.insert_one({
        "project_id": project_id,
        "title": title,
        "description": "",
        "assignee_id": assignee_id,
        "status": "todo",
        "priority": "medium",
        "due_date": due_date,
        "created_at": datetime.now(timezone.utc)
    }).inserted_id

    print("Задача создана:", task_id)


def update_task(db):
    print("Список задач:")
    task_id = get_id("tasks", db)

    status = input(
        "Новый статус (todo/in_progress/done/cancelled): "
    ).strip()

    if status not in {"todo", "in_progress", "done", "cancelled"}:
        print("Недопустимый статус.")
        return

    result = db.tasks.update_one(
        {"_id": task_id},
        {"$set": {
            "status": status,
            "updated_at": datetime.now(timezone.utc)
        }}
    )

    print("Изменено записей:", result.modified_count)


def delete_task(db):
    print("Список задач:")
    task_id = get_id("tasks", db)

    result = db.tasks.delete_one({"_id": task_id})
    print("Удалено записей:", result.deleted_count)


# =========================================================
# 8 ДЕМОНСТРАЦИОННЫХ ЗАПРОСОВ
# =========================================================

def query_1(db):
    """1. Все проекты."""
    print("\n1. ВСЕ ПРОЕКТЫ")
    show_documents(db.projects.find().sort("title", ASCENDING))


def query_2(db):
    """2. Активные проекты."""
    print("\n2. АКТИВНЫЕ ПРОЕКТЫ")
    show_documents(db.projects.find({"status": "active"}))


def query_3(db):
    """3. Участники выбранного проекта."""
    print("\n3. УЧАСТНИКИ ПРОЕКТА")
    project_id = get_id("projects", db)
    project = db.projects.find_one({"_id": project_id})

    if project:
        show_documents(db.users.find({
            "_id": {"$in": project.get("member_ids", [])}
        }))
    else:
        print("Проект не найден.")


def query_4(db):
    """4. Задачи выбранного исполнителя."""
    print("\n4. ЗАДАЧИ ИСПОЛНИТЕЛЯ")
    user_id = get_id("users", db)

    show_documents(db.tasks.find({
        "assignee_id": user_id
    }).sort("due_date", ASCENDING))


def query_5(db):
    """5. Задачи выбранного проекта."""
    print("\n5. ЗАДАЧИ ПРОЕКТА")
    project_id = get_id("projects", db)

    show_documents(db.tasks.find({
        "project_id": project_id
    }).sort("due_date", ASCENDING))


def query_6(db):
    """6. Открытые задачи высокого приоритета."""
    print("\n6. ВЫСОКИЙ ПРИОРИТЕТ")

    show_documents(db.tasks.find({
        "priority": "high",
        "status": {"$in": ["todo", "in_progress"]}
    }))


def query_7(db):
    """7. Просроченные незавершённые задачи."""
    print("\n7. ПРОСРОЧЕННЫЕ ЗАДАЧИ")

    show_documents(db.tasks.find({
        "due_date": {"$lt": datetime.now(timezone.utc)},
        "status": {"$nin": ["done", "cancelled"]}
    }).sort("due_date", ASCENDING))


def query_8(db):
    """8. Агрегация задач по статусам выбранного проекта."""
    print("\n8. СТАТИСТИКА ЗАДАЧ ПРОЕКТА")
    project_id = get_id("projects", db)

    pipeline = [
        {"$match": {"project_id": project_id}},
        {"$group": {
            "_id": "$status",
            "count": {"$sum": 1}
        }},
        {"$sort": {"count": -1}}
    ]

    show_documents(db.tasks.aggregate(pipeline))


# =========================================================
# МЕНЮ ПРИЛОЖЕНИЯ
# =========================================================

def main():
    client = None

    try:
        client = MongoClient(
            MONGO_URI,
            serverSelectionTimeoutMS=3000
        )
        client.admin.command("ping")
        db = client[DB_NAME]

        # Индексы для типовых запросов
        db.projects.create_index("status")
        db.projects.create_index("owner_id")
        db.users.create_index("email", unique=True)
        db.tasks.create_index([("assignee_id", 1), ("status", 1)])
        db.tasks.create_index([("project_id", 1), ("status", 1)])
        db.tasks.create_index([("status", 1), ("due_date", 1)])

        seed_database(db)

        menu = """
========================================
       РЕЕСТР УЧЕБНЫХ ПРОЕКТОВ
========================================
1. Все проекты
2. Активные проекты
3. Участники проекта
4. Задачи исполнителя
5. Задачи проекта
6. Задачи высокого приоритета
7. Просроченные задачи
8. Статистика проекта
9. Создать пользователя
10. Создать проект
11. Создать задачу
12. Изменить статус задачи
13. Удалить задачу
0. Выход
"""

        actions = {
            "1": query_1,
            "2": query_2,
            "3": query_3,
            "4": query_4,
            "5": query_5,
            "6": query_6,
            "7": query_7,
            "8": query_8,
            "9": create_user,
            "10": create_project,
            "11": create_task,
            "12": update_task,
            "13": delete_task
        }

        while True:
            print(menu)
            choice = input("Выберите пункт: ").strip()

            if choice == "0":
                print("Завершение работы.")
                break

            action = actions.get(choice)

            if action:
                try:
                    action(db)
                except ValueError as error:
                    print("Ошибка:", error)
                except PyMongoError as error:
                    print("Ошибка MongoDB:", error)
            else:
                print("Неизвестная команда.")

    except PyMongoError as error:
        print("Не удалось подключиться к MongoDB.")
        print("Проверьте, что MongoDB запущена.")
        print("Если используется Atlas, проверьте MONGO_URI.")
        print("Детали:", error)

    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    main()
проверь его работает ли он коректно или нет