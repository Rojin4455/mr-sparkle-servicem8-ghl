from django.urls import path
from serviceM8.views import *

urlpatterns = [
    path('servicem8/webhook/', servicem8_webhook2, name='servicem8_webhook'),
]