from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase, Client
from django.urls import reverse

from register.models import User
from vietnam_research.models import Articles, Likes


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

    def test_login_as_logged_user(self):
        client = Client()
        client.force_login(self.tester)
        response = client.get(reverse('vnm:index'))
        print(response.context)
        # self.assertTrue('username' in response.context)
        print(f'response({self.tester.email}): ', response)
        self.assertContains(response, f'{self.tester.username}さん')

    def test_logout(self):
        client = Client()
        client.force_login(self.tester)
        # print(client.)
        # client.request.u

    def test_post_good(self):
        client = Client()

        # create 3 users
        emails = ['tester1@b.c', 'tester2@b.c', 'tester3@b.c']
        [User.objects.create_user(email=x).set_password('12345') for x in emails]

        # already got 'good' from 3 users
        [Likes.objects.create(articles=self.article, user=User.objects.get(email=x)) for x in emails]
        self.assertEqual(3, Likes.objects.filter(articles=self.article).count())

        # click the 'good' then the count should be 4
        # response = client.post(reverse('vnm:likes', kwargs={'user_id': 1, 'article_id': 1}), follow=True)
        response = client.post('/likes/1/1/', {'user_id': 1, 'article_id': 1})
        print(response.status_code)
        print('Articles.objects.all().count(): ', Articles.objects.all().count())
        print('Likes.objects.all().count(): ', f"{Likes.objects.all().count()}(should be 4)")
        self.assertEqual(4, Likes.objects.filter(articles=self.article).count())
        self.assertEqual(200, response.status_code)

        # TODO: postを投げてlikesのレコードが増えるか？なんだけどうまくいってない（loginidの箇所は views.py L67）
        #  https://stackoverflow.com/questions/75412049/i-want-test-the-post-method-by-django
        #  https://teratail.com/questions/ud06pwl036vg7j

    def test_post_good_invalid_access(self):
        # TODO: errorが出ない?
        client = Client()
        with self.assertRaises(ObjectDoesNotExist):
            client.post(reverse('vnm:likes', kwargs={'user_id': 99, 'article_id': 1}), follow=True)
            client.post(reverse('vnm:likes', kwargs={'user_id': 1, 'article_id': 99}), follow=True)
