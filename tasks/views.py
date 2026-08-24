from collections import OrderedDict

from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Prefetch
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CommentForm, ProjectForm, RegisterForm, TaskForm
from .models import Project, Task


def register(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Your account is ready.")
            return redirect("dashboard")
    else:
        form = RegisterForm()

    return render(request, "registration/register.html", {"form": form})


@login_required
def dashboard(request):
    base_tasks = (
        Task.objects.filter(assigned_to=request.user)
        .with_common_relations()
        .order_by("status", "due_date")
    )
    overdue_tasks = base_tasks.overdue()

    grouped_tasks = OrderedDict(
        (status, {"label": label, "tasks": []}) for status, label in Task.Status.choices
    )
    for task in base_tasks:
        grouped_tasks[task.status]["tasks"].append(task)

    return render(
        request,
        "tasks/dashboard.html",
        {
            "grouped_tasks": grouped_tasks,
            "overdue_tasks": overdue_tasks,
        },
    )


@login_required
def project_list(request):
    projects = (
        Project.objects.visible_to(request.user)
        .with_status_counts()
        .select_related("owner")
        .prefetch_related("tasks")
    )
    return render(request, "tasks/project_list.html", {"projects": projects})


@login_required
def project_detail(request, pk):
    project = get_object_or_404(
        Project.objects.visible_to(request.user)
        .with_status_counts()
        .select_related("owner")
        .prefetch_related(Prefetch("tasks", queryset=Task.objects.with_common_relations())),
        pk=pk,
    )
    status_counts = (
        Task.objects.filter(project=project)
        .values("status")
        .annotate(total=Count("id"))
        .order_by("status")
    )
    tasks = project.tasks.all()

    return render(
        request,
        "tasks/project_detail.html",
        {
            "project": project,
            "tasks": tasks,
            "status_counts": status_counts,
        },
    )


@login_required
def project_create(request):
    if request.method == "POST":
        form = ProjectForm(request.POST)
        if form.is_valid():
            project = form.save(commit=False)
            project.owner = request.user
            project.save()
            messages.success(request, "Project created.")
            return redirect("project_detail", pk=project.pk)
    else:
        form = ProjectForm()

    return render(request, "tasks/project_form.html", {"form": form, "project": None})


@login_required
def project_update(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not project.user_can_manage(request.user):
        raise PermissionDenied("Only the project owner can edit this project.")

    if request.method == "POST":
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            form.save()
            messages.success(request, "Project updated.")
            return redirect("project_detail", pk=project.pk)
    else:
        form = ProjectForm(instance=project)

    return render(request, "tasks/project_form.html", {"form": form, "project": project})


@login_required
def project_delete(request, pk):
    project = get_object_or_404(Project, pk=pk)
    if not project.user_can_manage(request.user):
        raise PermissionDenied("Only the project owner can delete this project.")

    if request.method == "POST":
        project.delete()
        messages.success(request, "Project deleted.")
        return redirect("project_list")

    return render(request, "tasks/confirm_delete.html", {"object": project})


@login_required
def task_create(request, project_pk):
    project = get_object_or_404(Project, pk=project_pk)
    if not project.user_can_manage(request.user):
        raise PermissionDenied("Only the project owner can add tasks.")

    if request.method == "POST":
        form = TaskForm(request.POST)
        if form.is_valid():
            task = form.save(commit=False)
            task.project = project
            task.save()
            messages.success(request, "Task created.")
            return redirect("task_detail", pk=task.pk)
    else:
        form = TaskForm()

    return render(
        request,
        "tasks/task_form.html",
        {"form": form, "project": project, "task": None},
    )


@login_required
def task_detail(request, pk):
    task = get_object_or_404(
        Task.objects.visible_to(request.user)
        .with_common_relations()
        .prefetch_related("comments__author"),
        pk=pk,
    )

    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.task = task
            comment.author = request.user
            comment.save()
            messages.success(request, "Comment added.")
            return redirect("task_detail", pk=task.pk)
    else:
        form = CommentForm()

    return render(request, "tasks/task_detail.html", {"task": task, "form": form})


@login_required
def task_update(request, pk):
    task = get_object_or_404(Task.objects.with_common_relations(), pk=pk)
    if not task.user_can_manage(request.user):
        raise PermissionDenied("Only the project owner can edit tasks in this project.")

    if request.method == "POST":
        form = TaskForm(request.POST, instance=task)
        if form.is_valid():
            form.save()
            messages.success(request, "Task updated.")
            return redirect("task_detail", pk=task.pk)
    else:
        form = TaskForm(instance=task)

    return render(
        request,
        "tasks/task_form.html",
        {"form": form, "project": task.project, "task": task},
    )


@login_required
def task_delete(request, pk):
    task = get_object_or_404(Task.objects.with_common_relations(), pk=pk)
    if not task.user_can_manage(request.user):
        raise PermissionDenied("Only the project owner can delete tasks in this project.")

    project_pk = task.project_id
    if request.method == "POST":
        task.delete()
        messages.success(request, "Task deleted.")
        return redirect("project_detail", pk=project_pk)

    return render(request, "tasks/confirm_delete.html", {"object": task})
