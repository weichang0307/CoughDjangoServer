from django.urls import path
from . import views

urlpatterns = [
    path('create_cough_audio/', views.create_cough_audio, name='upload_audio'),
    path('generate/', views.generate, name='generate'),
    path('get_coughs/', views.get_coughs, name='get_coughs'),
    path('get_music/', views.get_music, name='get_music'),
    path('get_uploads_file/<str:filename>/', views.get_uploads_file, name='get_uploads_file'),
    path('save_music/', views.save_music, name='save_music'),
    path('clean_temper/', views.clean_temper, name='clean_temper'),
    path('get_user_info/', views.get_user_info, name='get_user_info'),
    path('set_user_info/', views.set_user_info, name='set_user_info'),
    path('sign_up/', views.sign_up, name='sign_up'),
    path('get_cough_info/', views.get_cough_info, name='get_cough_info'),
    path('set_cough_info/', views.set_cough_info, name='set_cough_info'),
    path('get_music_info/', views.get_music_info, name='get_music_info'),
    path('set_music_info/', views.set_music_info, name='set_music_info'),
    path('upload_to_public_cough/', views.upload_to_public_cough, name='upload_to_public_cough'),
    path('upload_to_public_music/', views.upload_to_public_music, name='upload_to_public_music'),
    path('start_record/', views.start_record, name='start_record'),
    path('get_cough_statistics/', views.get_cough_statistics, name='get_cough_statistics'),
    path('get_music_statistics/', views.get_music_statistics, name='get_music_statistics'),
]