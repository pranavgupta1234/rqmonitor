"""rqmonitor URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/3.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.urls import path
from .views import list_workers_api, delete_single_worker_api,\
    refresh_workers_list_api, worker_info_api

urlpatterns = [
    path('', list_workers_api, name='list_workers_api'),
    path('delete', delete_single_worker_api, name='delete_single_worker_api'),
    path('refresh', refresh_workers_list_api, name='refresh_workers_list_api'),
    path('info', worker_info_api, name='worker_info_api')
]
