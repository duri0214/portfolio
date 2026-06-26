# Djangoでいいね！をつくる2026

## はじめに

Webアプリをいったん作れるようになったあとに、まず知りたくなる機能があります。

それが「いいね！」です。

ログイン、投稿、ボタン、非同期通信、DB保存、件数表示が小さくまとまっているので、Djangoの練習題材としてちょうどいいです。しかも、作るとアプリが急に「使えるもの」っぽくなります。

この記事では、以前書いた [Djangoでいいね！をつくる](https://qiita.com/YoshitakaOkada/items/1eb1257b7c4aa286cc13) を2026年版として整理し直します。

元記事の構成はシンプルです。

- 記事モデルを作る
- いいねモデルを作る
- ボタンを押したらAjaxでいいねする
- いいね数を画面上で更新する

2026年版では、その考え方を残しつつ、次の点を少しだけ現代寄りにします。

- いいねするユーザーは `request.user` から取る
- 同じユーザーが同じ記事に複数回いいねできないようにDB制約を置く
- 一覧表示では、いいね数と自分が押したかどうかをまとめて取得する
- `fetch` と `JsonResponse` で小さく返す

## 参考

- [Djangoでいいね！をつくる](https://qiita.com/YoshitakaOkada/items/1eb1257b7c4aa286cc13)
- [Django documentation: Making queries](https://docs.djangoproject.com/en/stable/topics/db/queries/)
- [Django documentation: Query Expressions](https://docs.djangoproject.com/en/stable/ref/models/expressions/)
- [Django documentation: Cross Site Request Forgery protection](https://docs.djangoproject.com/en/stable/howto/csrf/)
- [Issue #458: Djangoでいいね！をつくる を2025にする](https://github.com/duri0214/portfolio/issues/458)

## 作るもの

記事に対して、ログインユーザーが「いいね！」を付けたり外したりできるようにします。

画面としては、記事カードに次のようなボタンを置くイメージです。

```text
いいね！ (12)
```

押すたびに状態を切り替えます。

- 未いいねなら、いいねを作成する
- いいね済みなら、いいねを削除する
- 最新のいいね数を返す
- ボタンの見た目と件数を画面上で更新する

ここではアプリ名を `blog` として説明します。既存アプリに入れる場合は、`blog` を自分のアプリ名に読み替えてください。

## モデル

まず、記事モデルといいねモデルを作ります。

ポイントは、`Like` を「ユーザーと記事の組み合わせ」として扱うことです。

```python:blog/models.py
from django.conf import settings
from django.db import models
from django.db.models import Count, Exists, OuterRef


class Article(models.Model):
    """ユーザーが投稿する記事。"""

    title = models.CharField("タイトル", max_length=200)
    body = models.TextField("本文")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="投稿者",
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField("公開日時", auto_now_add=True)

    @classmethod
    def with_like_state(cls, user):
        """記事ごとのいいね数と、ログインユーザーのいいね状態を付けて返す。"""
        queryset = cls.objects.annotate(likes_count=Count("likes"))
        if not user.is_authenticated:
            return queryset.annotate(liked_by_me=models.Value(False))

        liked_articles = Like.objects.filter(article=OuterRef("pk"), user=user)
        return queryset.annotate(liked_by_me=Exists(liked_articles))


class Like(models.Model):
    """記事に対するユーザーのいいね。"""

    article = models.ForeignKey(
        Article,
        verbose_name="記事",
        related_name="likes",
        on_delete=models.CASCADE,
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="ユーザー",
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["article", "user"],
                name="unique_article_like_user",
            )
        ]
```

`UniqueConstraint` を入れておくと、同じユーザーが同じ記事に複数回いいねすることをDB側で防げます。

アプリ側で `exists()` を見てから作成していても、二重クリックや同時リクエストで重複する可能性はあります。こういう「絶対に守りたいルール」は、モデルにも置いておくと安心です。

モデルを変更したら、マイグレーションを作成して反映します。

```bash:console
$ python manage.py makemigrations
$ python manage.py migrate
```

## 一覧表示

記事一覧では、記事本体に加えて次の2つが必要です。

- その記事のいいね数
- ログイン中の自分がいいね済みかどうか

テンプレートの中で記事ごとに `Like.objects.filter(...)` を呼びたくなりますが、それをやると記事数ぶんクエリが増えます。

なので、一覧を作る時点で `with_like_state()` を使います。

```python:blog/views.py
from django.views.generic import ListView

from blog.models import Article


class ArticleListView(ListView):
    model = Article
    template_name = "blog/index.html"
    context_object_name = "articles"

    def get_queryset(self):
        return Article.with_like_state(self.request.user).order_by("-created_at")
```

これで、テンプレート側では `article.likes_count` と `article.liked_by_me` をそのまま使えます。

## いいねを切り替えるView

いいねボタンはPOSTで処理します。

ここで大事なのは、`user_id` をURLやPOST本文から受け取らないことです。

```text
NG: /likes/1/10/  # article_id と user_id をURLに載せる
OK: /likes/1/     # article_id だけをURLに載せる
```

「誰が押したか」は、ログイン済みの `request.user` から分かります。

```python:blog/views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from blog.models import Article, Like


class LikeToggleView(LoginRequiredMixin, View):
    """記事へのいいねを登録または解除する。"""

    def post(self, request, article_id):
        article = get_object_or_404(Article, pk=article_id)
        like = Like.objects.filter(article=article, user=request.user).first()

        if like:
            like.delete()
            liked_by_me = False
        else:
            Like.objects.create(article=article, user=request.user)
            liked_by_me = True

        return JsonResponse(
            {
                "liked_by_me": liked_by_me,
                "likes_count": article.likes.count(),
            }
        )
```

未ログインユーザーに対しては `LoginRequiredMixin` がログインページへ誘導します。

JavaScript側でJSONの `401` を受けたい場合は、明示的に `JsonResponse({"error": "login_required"}, status=401)` を返す形でもよいです。画面全体のログイン導線に合わせて選びます。

## URL

一覧画面といいね切り替え用のURLを用意します。

```python:blog/urls.py
from django.urls import path

from blog.views import ArticleListView, LikeToggleView

app_name = "blog"

urlpatterns = [
    path("", ArticleListView.as_view(), name="index"),
    path("likes/<int:article_id>/", LikeToggleView.as_view(), name="likes"),
]
```

## テンプレート

記事ごとにいいねボタンを表示します。

`data-article-id` に記事IDを入れておき、JavaScriptから読み取れるようにします。

```html:blog/templates/blog/index.html
{% for article in articles %}
  <article>
    <h2>{{ article.title }}</h2>
    <p>{{ article.body }}</p>

    <button
      type="button"
      class="like-toggle{% if article.liked_by_me %} is-liked{% endif %}"
      data-article-id="{{ article.id }}"
      {% if not user.is_authenticated %}disabled{% endif %}
    >
      いいね！
      <span class="like-count">({{ article.likes_count }})</span>
    </button>
  </article>
{% endfor %}
```

未ログイン時はボタンを `disabled` にしています。

ここは好みで、ログインページへのリンクを出してもよいです。

```html:blog/templates/blog/index.html
{% if not user.is_authenticated %}
  <a href="{% url 'login' %}?next={{ request.path }}">ログインしていいねする</a>
{% endif %}
```

## fetchでPOSTする

ボタンを押したら、いいね用URLへPOSTします。

DjangoでPOSTするので、CSRFトークンを `X-CSRFToken` に入れます。

```html:blog/templates/blog/index.html
<script>
  const likeButtons = document.querySelectorAll(".like-toggle");

  for (const button of likeButtons) {
    button.addEventListener("click", async () => {
      const articleId = button.dataset.articleId;
      const response = await fetch(`/blog/likes/${articleId}/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": "{{ csrf_token }}",
        },
      });

      if (!response.ok) {
        return;
      }

      const data = await response.json();
      const count = button.querySelector(".like-count");

      count.textContent = `(${data.likes_count})`;
      button.classList.toggle("is-liked", data.liked_by_me);
    });
  }
</script>
```

これで、画面遷移なしでいいね数とボタン状態が切り替わります。

## テスト

最低限、次の3つは確認しておくと安心です。

- ログインユーザーがいいねできる
- もう一度押すと解除できる
- 未ログインユーザーはいいねできない

```python:blog/tests/test_views.py
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from blog.models import Article, Like


class LikeToggleViewTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="user",
            password="password",
        )
        self.article = Article.objects.create(
            title="Djangoでいいね！",
            body="いいね機能のテストです。",
            author=self.user,
        )

    def test_login_user_can_like_article(self):
        """
        シナリオ:
        - 入力: ログイン済みユーザーと記事。
        - 処理: いいねAPIへPOSTする。
        - 期待値: Likeが作成され、いいね数1件のJSONが返ること。
        """
        self.client.login(username="user", password="password")

        response = self.client.post(
            reverse("blog:likes", kwargs={"article_id": self.article.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Like.objects.count(), 1)
        self.assertJSONEqual(
            response.content,
            {"liked_by_me": True, "likes_count": 1},
        )

    def test_login_user_can_unlike_article(self):
        """
        シナリオ:
        - 入力: すでにいいね済みの記事。
        - 処理: 同じユーザーでいいねAPIへPOSTする。
        - 期待値: Likeが削除され、いいね数0件のJSONが返ること。
        """
        Like.objects.create(article=self.article, user=self.user)
        self.client.login(username="user", password="password")

        response = self.client.post(
            reverse("blog:likes", kwargs={"article_id": self.article.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Like.objects.count(), 0)
        self.assertJSONEqual(
            response.content,
            {"liked_by_me": False, "likes_count": 0},
        )

    def test_anonymous_user_cannot_like_article(self):
        """
        シナリオ:
        - 入力: 未ログインユーザーと記事。
        - 処理: いいねAPIへPOSTする。
        - 期待値: ログインが必要になり、Likeが作成されないこと。
        """
        response = self.client.post(
            reverse("blog:likes", kwargs={"article_id": self.article.pk})
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Like.objects.count(), 0)
```

実行します。

```bash:console
$ python manage.py test blog
```

## 実装するときの注意点

### user_idを画面から送らない

いいね機能で一番避けたいのは、画面から送られてきた `user_id` をそのまま信用することです。

ログインユーザーはサーバー側のセッションで分かるので、`request.user` を使います。

```python
user = request.user
```

これだけで十分です。

### 重複いいねはDBでも防ぐ

アプリ側でチェックしていても、二重クリックや複数タブからの操作で同時にPOSTされることがあります。

`UniqueConstraint` を入れておけば、最後の砦としてDBが守ってくれます。

### 一覧画面でクエリを増やさない

いいね機能は、作った直後は簡単に見えます。

ただし、記事一覧で1件ずつ「この人はいいねした？」を問い合わせると、記事数が増えたときに急に重くなります。

`Count` と `Exists` で一覧に状態を付けてからテンプレートへ渡すと、後から困りにくいです。

## 既存実装に合わせるなら

このリポジトリでは、`vietnam_research` に記事投稿といいね機能があります。

考え方はこの記事と同じです。

- `Articles`: 投稿記事
- `Likes`: 記事とユーザーの組み合わせ
- `LikesView`: POSTでいいねを切り替える
- `LikeRepository`: いいねの作成、削除、存在確認、件数取得

既存実装を更新するなら、まずは以下の観点で見るとよいです。

- URLに `user_id` が含まれていないか
- `Likes` に一意制約があるか
- 未ログイン時のレスポンスが画面の期待と合っているか
- 一覧表示で記事ごとの追加クエリが増えていないか
- フロント側でCSRFトークンを送っているか

## まとめ

いいね機能は小さいですが、Webアプリの大事な要素が詰まっています。

- ログインユーザーとデータを結びつける
- 中間テーブルで多対多っぽい関係を表現する
- DB制約で重複を防ぐ
- POSTで状態を変更する
- JSONを返して画面だけ更新する

Webアプリを一度作れるようになったあと、「次に何を作ると一段わかるか」と聞かれたら、いいね機能はかなり良い題材です。
