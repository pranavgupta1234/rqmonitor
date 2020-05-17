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
    worker_info_api, list_jobs_api, index_api, get_jobs_dashboard,\
    get_workers_dashboard, get_queues_dashboard, list_queues_api

urlpatterns = [
    path('', index_api, name='index_api'),
    path('get_jobs_dashboard/', get_jobs_dashboard, name='get_jobs_dashboard'),
    path('get_workers_dashboard/', get_workers_dashboard, name='get_workers_dashboard'),
    path('get_queues_dashboard/', get_queues_dashboard, name='get_queues_dashboard'),
    path('queues/', list_queues_api, name='list_queues_api'),
    path('workers/', list_workers_api, name='list_workers_api'),
    path('jobs/', list_jobs_api, name='list_jobs_api'),
    path('workers/delete', delete_single_worker_api, name='delete_single_worker_api'),
    path('workers/info', worker_info_api, name='worker_info_api'),

]
