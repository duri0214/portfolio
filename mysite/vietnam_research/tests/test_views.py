from django.test import TestCase, Client
from django.urls import reverse

from register.models import User


class TestView(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.create_user(email='tester@b.c').set_password('12345')

    def test_login_and_logout(self):
        user = User.objects.get(email='tester@b.c')
        client = Client()
        response = client.get(reverse('vnm:index'))
        self.assertContains(response, 'ゲストさん')
        client.force_login(user)
        response = client.get(reverse('vnm:index'))
        self.assertContains(response, 'tester@b.cさん')

        # TODO: loginidのテストは mysite/vietnam_research/views.py articlesとlike L62
