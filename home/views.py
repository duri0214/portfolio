from django.urls import reverse_lazy, reverse
from django.views.generic import TemplateView, DetailView, UpdateView, CreateView
from markdown import Markdown
from mdx_gfm import GithubFlavoredMarkdownExtension

from home.models import Post


class IndexView(TemplateView):
    template_name = "home/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["posts"] = Post.objects.all()
        context["featured_posts"] = Post.objects.filter(is_featured=True)
        return context


class PostDetailView(DetailView):
    model = Post
    template_name = "home/post/detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        md = Markdown(extensions=[GithubFlavoredMarkdownExtension()])
        context["content_html"] = md.convert(self.object.content)

        return context


class PostUpdateView(UpdateView):
    model = Post
    template_name = "home/post/update.html"
    fields = ["title", "image", "category", "summary", "content", "is_featured"]

    def get_success_url(self):
        return reverse_lazy("home:post_detail", kwargs={"pk": self.object.pk})


class PostCreateView(CreateView):
    model = Post
    template_name = "home/post/create.html"
    fields = ["title", "image", "category", "summary", "content", "is_featured"]

    def form_valid(self, form):
        form.instance.author = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse("home:post_detail", args=[str(self.object.id)])


class HospitalIndexView(TemplateView):
    template_name = "home/hospital/index.html"
