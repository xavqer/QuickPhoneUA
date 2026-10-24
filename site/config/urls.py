from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.urls import include, path

from apps.catalog.seo import robots_txt, sitemaps
from apps.catalog.views import home_page, privacy_policy_page

#Checking if website is on
def healthcheck(_request):
    return HttpResponse("ok", content_type="text/plain; charset=utf-8")

urlpatterns = [
    path("upravlinnia-mahazynom/", admin.site.urls),
    path("health/", healthcheck, name="healthcheck"),
    path("robots.txt", robots_txt, name="robots_txt"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path("catalog/", include("apps.catalog.urls", namespace="catalog")),
    path("orders/", include("apps.orders.urls", namespace="orders")),
    path("users/", include("apps.users.urls", namespace="users")),
    path("privacy-policy/", privacy_policy_page, name="privacy_policy"),
    path("", home_page, name="home"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
