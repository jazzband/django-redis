from django.conf.urls.defaults import *


urlpatterns = patterns('',
    (r'^$', 'tests.views.someview'),
)