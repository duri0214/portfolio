from django.test import TestCase
from django.urls import reverse

from register.models import User
from warehouse.models import Warehouse, Staff


class TestView(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.create_user(email='tester@b.c').set_password('12345')
        Warehouse.objects.create(
            code='iruma',
            name='入間倉庫',
            address='埼玉県狭山市稲荷山２丁目３',
            width=3,
            height=3,
            depth=3,
            created_at='2023-02-12 00:00:00'
        )
        Staff.objects.create(name='スタッフ1', created_at='2023-02-12 00:00:00', warehouse_id=1)

    def test_get_toppage_200(self):
        response = self.client.get(reverse('war:index'))
        self.assertEqual(200, response.status_code)
