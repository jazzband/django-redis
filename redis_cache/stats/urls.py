# -*- coding: utf-8 -*-

from django.conf.urls.defaults import *
from .views import RedisStatsView

urlpatterns = patterns('',
    url(r'^$', RedisStatsView.as_view(), name='redis_cache_status'),
)

