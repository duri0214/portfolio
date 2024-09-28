from django.urls import reverse_lazy
from django.views.generic import TemplateView, DetailView, UpdateView
from markdown import Markdown
from mdx_gfm import GithubFlavoredMarkdownExtension

from home.models import Post


class IndexView(TemplateView):
    template_name = "home/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["posts"] = Post.objects.all()
        return context


class PostDetailView(DetailView):
    model = Post
    template_name = "home/posts/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        md = Markdown(extensions=[GithubFlavoredMarkdownExtension()])
        context["content_html"] = md.convert(self.object.content)

        return context


class PostUpdateView(UpdateView):
    model = Post
    template_name = "home/posts/update.html"
    fields = ["title", "image", "category", "summary", "content"]

    def get_success_url(self):
        return reverse_lazy("home:post_detail", kwargs={"pk": self.object.pk})
