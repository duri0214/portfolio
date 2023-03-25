from django.test import TestCase, Client
from django.urls import reverse

from register.models import User


class TestView(TestCase):
    @classmethod
    def setUpTestData(cls):
        tester = User.objects.create_user(email='tester@b.c')
        tester.set_password('12345')
        cls.tester = tester
        cls.article = Articles.objects.create(title='Hello', note='How are you', user=tester)

    def test_status_code_200(self):
        client = Client()
        response = client.get(reverse('vnm:index'))
        self.assertEqual(200, response.status_code)

    def test_login_as_guest(self):
        client = Client()
        response = client.get(reverse('vnm:index'))
        self.assertContains(response, 'ゲストさん')
        client.force_login(user)
        response = client.get(reverse('vnm:index'))
        self.assertContains(response, 'tester@b.cさん')

        # TODO: loginidのテストは mysite/vietnam_research/views.py articlesとlike L62
