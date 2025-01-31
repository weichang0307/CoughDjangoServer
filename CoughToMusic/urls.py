from django.urls import path
from . import views

urlpatterns = [
    path('create_cough_audio/', views.create_cough_audio, name='upload_audio'),
    path('generate/', views.generate, name='generate'),
    path('get_records/', views.get_records, name='get_records'),
    path('get_music/', views.get_music, name='get_music'),
    path('get_uploads_file/<str:filename>/', views.get_uploads_file, name='get_uploads_file')
]