from django.urls import path

from . import views

app_name = "users"

urlpatterns = [
    path("register/", views.register_view, name="register"),
    path("register/verify/", views.register_verify_view, name="register_verify"),
    path("login/", views.login_view, name="login"),
    path("login/verify/", views.login_verify_view, name="login_verify"),
    path("password-reset/", views.password_reset_request_view, name="password_reset_request"),
    path("password-reset/confirm/", views.password_reset_confirm_view, name="password_reset_confirm"),
    path("logout/", views.logout_view, name="logout"),
    path("profile/", views.profile_view, name="profile"),
    path("profile/change-phone/", views.phone_change_request_view, name="phone_change_request"),
    path("profile/change-phone/verify/", views.phone_change_verify_view, name="phone_change_verify"),
]
