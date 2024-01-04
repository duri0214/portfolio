from django.test import TestCase
from django.urls import reverse

from register.models import User
from shopping.models import Store


class TestView(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.create_user(email='tester@b.c').set_password('12345')
        Store.objects.create(name='笹塚')
        Store.objects.create(name='新宿')

    def test_get_toppage_200(self):
        response = self.client.get(reverse('shp:index'))
        self.assertEqual(200, response.status_code)
