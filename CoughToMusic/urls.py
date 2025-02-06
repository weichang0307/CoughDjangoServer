from django.urls import path
from . import views

urlpatterns = [
    path('create_cough_audio/', views.create_cough_audio, name='upload_audio'),
    path('generate/', views.generate, name='generate'),
    path('get_coughs/', views.get_coughs, name='get_coughs'),
    path('get_music/', views.get_music, name='get_music'),
    path('get_uploads_file/<str:filename>/', views.get_uploads_file, name='get_uploads_file'),
    path('create_user', views.create_user, name='create_user'),
    path('save_music/', views.save_music, name='save_music'),
    path('clean_temper/', views.clean_temper, name='clean_temper'),
]