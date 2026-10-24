from django.urls import path

from . import views

app_name = "orders"

urlpatterns = [
    path("cart/badge/", views.cart_badge, name="cart_badge"),
    path("cart/panel/", views.cart_panel, name="cart_panel"),
    path("cart/add/", views.cart_add, name="cart_add"),
    path("buy-now/", views.buy_now, name="buy_now"),
    path("cart/remove/", views.cart_remove, name="cart_remove"),
    path("checkout/", views.checkout_page, name="checkout"),
    path("checkout/remove/", views.checkout_remove, name="checkout_remove"),
    path("checkout/submit/", views.checkout_submit, name="checkout_submit"),
    path("np/cities/", views.np_city_search, name="np_city_search"),
    path("np/warehouses/", views.np_warehouses, name="np_warehouses"),
    path("np/estimate/", views.np_estimate, name="np_estimate"),
]
