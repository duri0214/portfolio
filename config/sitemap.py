from django.conf import settings
from django.http import HttpResponse
from django.urls import URLPattern, URLResolver, get_resolver


def _normalize_path(path: str) -> str:
    if not path:
        return "/"
    if not path.startswith("/"):
        return f"/{path}"
    return path


def _iter_static_paths(urlpatterns, prefix=""):
    for entry in urlpatterns:
        if isinstance(entry, URLPattern):
            route = getattr(entry.pattern, "_route", None)
            if route is None:
                continue
            if "<" in route or ">" in route:
                continue
            full_route = f"{prefix}{route}"
            yield _normalize_path(full_route)
            continue
        if isinstance(entry, URLResolver):
            route = getattr(entry.pattern, "_route", "")
            if route is None:
                continue
            next_prefix = f"{prefix}{route}"
            yield from _iter_static_paths(entry.url_patterns, next_prefix)


def _collect_public_paths():
    resolver = get_resolver()
    paths = []
    for path in _iter_static_paths(resolver.url_patterns):
        if path.startswith("/admin/"):
            continue
        if path.startswith("/accounts/"):
            continue
        paths.append(path)
    unique_paths = sorted(set(paths))
    return unique_paths


def sitemap_xml(_request):
    base_url = settings.SITE_URL.rstrip("/")
    urls = _collect_public_paths()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    for path in urls:
        lines.append(f"  <url><loc>{base_url}{path}</loc></url>")
    lines.append("</urlset>")
    content = "\n".join(lines) + "\n"
    return HttpResponse(content, content_type="application/xml")
