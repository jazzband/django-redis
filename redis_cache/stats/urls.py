# -*- coding: utf-8 -*-

try:
    from django.conf.urls import *
except ImportError: # django < 1.4
    from django.conf.urls.defaults import *

from .views import RedisStatsView

urlpatterns = patterns('',
    url(r'^$', RedisStatsView.as_view(), name='redis_cache_status'),
)

