from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("", views.catalog_list, name="list"),
    path("search-suggestions/", views.search_suggestions, name="search_suggestions"),
    path("<int:pk>-<slug:slug>/", views.product_detail, name="product_detail"),
]
