from django.contrib import admin

from .models import Comment, Project, Task


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("name", "owner")
    search_fields = ("name", "owner__username")
    list_select_related = ("owner",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "project", "assigned_to", "status", "priority", "due_date")
    list_filter = ("status", "priority", "due_date")
    search_fields = ("title", "project__name", "assigned_to__username")
    list_select_related = ("project", "assigned_to")


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("task", "author", "created_at")
    search_fields = ("body", "task__title", "author__username")
    list_select_related = ("task", "author")
