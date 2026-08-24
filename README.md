# Task Management System

A small multi-user task manager built for the Race Ai assignment. Users can create projects, add tasks, assign them to teammates, comment on visible tasks, and use a dashboard grouped by task status.

## Tech Stack

- Python 3.12+ recommended
- Django 5.1.4
- MySQL 8.4
- PyMySQL 1.1.1 as the Django MySQL driver
- cryptography 43.0.3 for MySQL 8 password authentication through PyMySQL
- Docker Compose for local MySQL

## Local Setup

1. Create a virtual environment and install dependencies.

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Copy the environment template.

   ```bash
   copy .env.example .env
   ```

3. Start MySQL.

   ```bash
   docker compose up -d
   ```

   The Compose setup grants the app user access to `task_manager` and to Django's `test_task_manager` database used by `manage.py test`.

4. Run migrations.

   ```bash
   python manage.py migrate
   ```

5. Create an admin user if you want admin access.

   ```bash
   python manage.py createsuperuser
   ```

6. Start the app.

   ```bash
   python manage.py runserver
   ```

Open http://127.0.0.1:8000/ and register a user.

## Environment Variables

The app reads `.env` with `python-dotenv`.

| Variable | Default |
| --- | --- |
| `DJANGO_SECRET_KEY` | `dev-only-secret-key` |
| `DJANGO_DEBUG` | `True` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` |
| `MYSQL_DATABASE` | `task_manager` |
| `MYSQL_USER` | `task_user` |
| `MYSQL_PASSWORD` | `task_password` |
| `MYSQL_HOST` | `127.0.0.1` |
| `MYSQL_PORT` | `3306` |

## Functional Notes

- Project membership is defined as either the project owner or a user assigned to at least one task in that project.
- Only the project owner can edit or delete a project.
- Only the project owner can create, edit, or delete tasks within that project.
- Any authenticated user who can view a task can append comments.
- Comments are append-only in the user-facing app.

## MySQL and ORM Write-Up

### 1. MySQL Configuration

The app uses the MySQL backend in [task_manager/settings.py](task_manager/settings.py):

```python
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.getenv("MYSQL_DATABASE", "task_manager"),
        "USER": os.getenv("MYSQL_USER", "task_user"),
        "PASSWORD": os.getenv("MYSQL_PASSWORD", "task_password"),
        "HOST": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "PORT": os.getenv("MYSQL_PORT", "3306"),
        "OPTIONS": {"charset": "utf8mb4"},
    }
}
```

PyMySQL is installed as the MySQLdb-compatible driver in settings:

```python
pymysql.install_as_MySQLdb()
```

### 2. Overdue Tasks Query

Reusable ORM method in [tasks/models.py](tasks/models.py):

```python
Task.objects.overdue()
```

Implementation:

```python
return self.filter(due_date__lt=timezone.localdate()).exclude(status=Task.Status.DONE)
```

Representative SQL from `print(Task.objects.overdue().query)`:

```sql
SELECT `tasks_task`.`id`, `tasks_task`.`title`, `tasks_task`.`status`,
       `tasks_task`.`priority`, `tasks_task`.`due_date`,
       `tasks_task`.`project_id`, `tasks_task`.`assigned_to_id`
FROM `tasks_task`
WHERE (`tasks_task`.`due_date` < 2026-08-24
       AND NOT (`tasks_task`.`status` = done))
ORDER BY `tasks_task`.`due_date` ASC, `tasks_task`.`priority` ASC, `tasks_task`.`title` ASC;
```

This stays as a queryset method because the dashboard and any future reports can reuse the same definition without copying date/status logic.

### 3. Per-Project Status Counts

Reusable ORM method in [tasks/models.py](tasks/models.py):

```python
Project.objects.with_status_counts()
```

Implementation:

```python
return self.annotate(
    todo_count=Count("tasks", filter=Q(tasks__status=Task.Status.TODO), distinct=True),
    in_progress_count=Count("tasks", filter=Q(tasks__status=Task.Status.IN_PROGRESS), distinct=True),
    done_count=Count("tasks", filter=Q(tasks__status=Task.Status.DONE), distinct=True),
)
```

Representative MySQL SQL:

```sql
SELECT `tasks_project`.`id`, `tasks_project`.`name`, `tasks_project`.`description`,
       `tasks_project`.`owner_id`,
       COUNT(DISTINCT CASE WHEN `tasks_task`.`status` = todo THEN `tasks_task`.`id` ELSE NULL END) AS `todo_count`,
       COUNT(DISTINCT CASE WHEN `tasks_task`.`status` = in_progress THEN `tasks_task`.`id` ELSE NULL END) AS `in_progress_count`,
       COUNT(DISTINCT CASE WHEN `tasks_task`.`status` = done THEN `tasks_task`.`id` ELSE NULL END) AS `done_count`
FROM `tasks_project`
LEFT OUTER JOIN `tasks_task` ON (`tasks_project`.`id` = `tasks_task`.`project_id`)
GROUP BY `tasks_project`.`id`;
```

This lets MySQL count rows by status instead of loading all tasks and counting them in Python.

### 4. N+1 Avoidance

Task lists use `select_related` for forward foreign keys that are rendered per row:

```python
Task.objects.with_common_relations()
```

Implementation:

```python
return self.select_related("project", "assigned_to", "project__owner")
```

Project detail uses `prefetch_related` for the reverse project-to-tasks relation:

```python
Project.objects.prefetch_related(
    Prefetch("tasks", queryset=Task.objects.with_common_relations())
)
```

Task detail uses:

```python
Task.objects.with_common_relations().prefetch_related("comments__author")
```

These querysets avoid one extra query per task row for project, assignee, and owner data, and avoid one extra query per comment author on task detail.

### 5. Deliberate Index

The assignment asks for exactly one deliberate index beyond Django's automatic primary-key and foreign-key indexes. This project adds a composite index on task status and due date in [tasks/models.py](tasks/models.py):

```python
models.Index(fields=["status", "due_date"], name="task_status_due_idx")
```

The overdue query filters by `due_date` and excludes the completed status. The dashboard surfaces overdue tasks every time a user lands on the app, so this index supports a real recurring query. I chose `(status, due_date)` because status has a small fixed set and due date narrows the remaining rows for incomplete work. I did not add indexes for low-volume fields like project name because this assignment's most important repeated query is task filtering, not text search.

## Running Tests

```bash
python manage.py test
```

The tests cover project visibility, direct-post permission failure for task edits, overdue filtering, and annotated status counts.
