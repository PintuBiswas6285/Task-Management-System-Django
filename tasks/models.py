from django.conf import settings
from django.db import models
from django.utils import timezone


class TaskQuerySet(models.QuerySet):
    def visible_to(self, user):
        if not user.is_authenticated:
            return self.none()
        return self.filter(
            models.Q(project__owner=user)
            | models.Q(assigned_to=user)
            | models.Q(project__tasks__assigned_to=user)
        ).distinct()

    def overdue(self):
        return self.filter(
            due_date__lt=timezone.localdate(),
        ).exclude(status=Task.Status.DONE)

    def with_common_relations(self):
        return self.select_related("project", "assigned_to", "project__owner")


class ProjectQuerySet(models.QuerySet):
    def visible_to(self, user):
        if not user.is_authenticated:
            return self.none()
        return self.filter(
            models.Q(owner=user) | models.Q(tasks__assigned_to=user)
        ).distinct()

    def with_status_counts(self):
        return self.annotate(
            todo_count=models.Count(
                "tasks",
                filter=models.Q(tasks__status=Task.Status.TODO),
                distinct=True,
            ),
            in_progress_count=models.Count(
                "tasks",
                filter=models.Q(tasks__status=Task.Status.IN_PROGRESS),
                distinct=True,
            ),
            done_count=models.Count(
                "tasks",
                filter=models.Q(tasks__status=Task.Status.DONE),
                distinct=True,
            ),
        )


class Project(models.Model):
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_projects",
    )

    objects = ProjectQuerySet.as_manager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    def user_can_view(self, user):
        return user.is_authenticated and (
            self.owner_id == user.id or self.tasks.filter(assigned_to=user).exists()
        )

    def user_can_manage(self, user):
        return user.is_authenticated and self.owner_id == user.id


class Task(models.Model):
    class Status(models.TextChoices):
        TODO = "todo", "To Do"
        IN_PROGRESS = "in_progress", "In Progress"
        DONE = "done", "Done"

    class Priority(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"

    title = models.CharField(max_length=180)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TODO,
    )
    priority = models.CharField(
        max_length=20,
        choices=Priority.choices,
        default=Priority.MEDIUM,
    )
    due_date = models.DateField()
    project = models.ForeignKey(
        Project,
        on_delete=models.CASCADE,
        related_name="tasks",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_tasks",
    )

    objects = TaskQuerySet.as_manager()

    class Meta:
        ordering = ["due_date", "priority", "title"]
        indexes = [
            models.Index(fields=["status", "due_date"], name="task_status_due_idx"),
        ]

    def __str__(self):
        return self.title

    def user_can_view(self, user):
        return self.project.user_can_view(user)

    def user_can_manage(self, user):
        return self.project.user_can_manage(user)


class Comment(models.Model):
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.author} on {self.task}"
