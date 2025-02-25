"""urls.py is used to define the URL patterns for the Django app.
In particular this file allows to link the views to the URLs."""


from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('add_resource/', views.add_resource_view, name='add_resource'),
    path('stream/<int:source_id>/', views.stream_view, name='stream_view'),
    path('stream/<int:source_id>/start/', views.start_recording_view, name='start_recording'),
    path('stream/<int:source_id>/stop/', views.stop_recording_view, name='stop_recording'),
    path('stream/<int:source_id>/add_watermark/', views.add_watermark_view, name='add_watermark'),
    path('stream/<int:source_id>/send_recording/', views.send_recording_view, name='send_recording'),
    path('video_feed/<int:source_id>/', views.video_feed, name='video_feed'),
]
