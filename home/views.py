from django.views.generic import TemplateView, DetailView

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
