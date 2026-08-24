from datetime import timedelta

from django.contrib.auth.models import User
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Project, Task


class PermissionTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user("owner", password="pass12345")
        self.member = User.objects.create_user("member", password="pass12345")
        self.outsider = User.objects.create_user("outsider", password="pass12345")
        self.project = Project.objects.create(name="Launch", owner=self.owner)
        self.task = Task.objects.create(
            title="Draft plan",
            project=self.project,
            assigned_to=self.member,
            due_date=timezone.localdate(),
        )

    def test_assigned_user_can_view_project(self):
        self.client.login(username="member", password="pass12345")
        response = self.client.get(reverse("project_detail", args=[self.project.pk]))
        self.assertEqual(response.status_code, 200)

    def test_outsider_cannot_view_project(self):
        self.client.login(username="outsider", password="pass12345")
        response = self.client.get(reverse("project_detail", args=[self.project.pk]))
        self.assertEqual(response.status_code, 404)

    def test_non_owner_direct_post_cannot_edit_task(self):
        self.client.login(username="member", password="pass12345")
        response = self.client.post(
            reverse("task_update", args=[self.task.pk]),
            {
                "title": "Changed by member",
                "status": Task.Status.DONE,
                "priority": Task.Priority.HIGH,
                "due_date": timezone.localdate(),
                "assigned_to": self.member.pk,
            },
        )
        self.assertEqual(response.status_code, 403)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Draft plan")


class QueryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("owner", password="pass12345")
        self.project = Project.objects.create(name="Data layer", owner=self.user)

    def test_overdue_queryset_excludes_done_tasks(self):
        old_date = timezone.localdate() - timedelta(days=1)
        overdue = Task.objects.create(
            title="Overdue",
            project=self.project,
            assigned_to=self.user,
            due_date=old_date,
            status=Task.Status.TODO,
        )
        Task.objects.create(
            title="Finished",
            project=self.project,
            assigned_to=self.user,
            due_date=old_date,
            status=Task.Status.DONE,
        )

        self.assertQuerySetEqual(Task.objects.overdue(), [overdue])

    def test_project_status_counts_are_annotated(self):
        Task.objects.create(title="One", project=self.project, due_date=timezone.localdate())
        Task.objects.create(
            title="Two",
            project=self.project,
            due_date=timezone.localdate(),
            status=Task.Status.DONE,
        )

        project = Project.objects.with_status_counts().get(pk=self.project.pk)
        self.assertEqual(project.todo_count, 1)
        self.assertEqual(project.in_progress_count, 0)
        self.assertEqual(project.done_count, 1)
