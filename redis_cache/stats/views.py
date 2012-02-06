# -*- coding: utf-8 -*-
# Copyright (c) 2011 Andrei Antoukh <niwi@niwi.be>

from django.views.generic import View
from django.shortcuts import render_to_response, get_object_or_404
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect
from django.template import RequestContext
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

from redis_cache.cache import CacheConnectionPool
from redis.connection import DefaultParser
from collections import defaultdict

import redis, re

pools = defaultdict(CacheConnectionPool)

class RedisStatsView(View):
    dbs_rx = re.compile(r'^db(\d+)$', flags=re.U)
    has_redis_cache = True

    def __init__(self, *args, **kwargs):
        if not hasattr(settings, "CACHES"):
            self.has_redis_cache = False

        if not hasattr(self, 'caches'):
            self.__class__.caches = self.get_caches()

        super(RedisStatsView, self).__init__(*args, **kwargs)
    
    def get_caches(self):
        caches = {}
        for name, options in getattr(settings, 'CACHES').iteritems():
            if 'BACKEND' not in options or 'RedisCache' not in options['BACKEND']:
                continue

            cachedict = {'unix_socket_path': None}
            server = options.get('LOCATION', 'localhost:6379')

            try:
                if ":" in server:
                    host, port = server.split(':')
                    cachedict['port'] = int(port)
                    cachedict['host'] = host
                else:
                    cachedict['port'] = cachedict['host'] = None
                    cachedict['unix_socket_path'] = server
            except (ValueError, TypeError):
                raise ImproperlyConfigured("port value must be an integer")

            _options = options.get('OPTIONS', {})
            try:
                cachedict['db'] = int(_options.get('DB', 1))
                cachedict['password'] = _options.get('PASSWORD', None)
            except (ValueError, TypeError):
                raise ImproperlyConfigured("db value must be an integer")

            caches[name] = cachedict
        return caches

    def get_info(self):
        if not self.has_redis_cache:
            return {}

        def parse_dbs(infoobject):
            dbs = {}
            for key, value in infoobject.iteritems():
                rx_match = self.dbs_rx.match(key)
                if rx_match:
                    dbs[str(rx_match.group(1))] = value

            return dbs
        
        global pools

        caches_info = {}
        for name, options in self.caches.iteritems():
            connection_pool = pools[name]\
                .get_connection_pool(parser_class=DefaultParser, **options)

            rclient = redis.Redis(connection_pool=connection_pool)

            caches_info[name] = rclient.info()
            caches_info[name]['dbs'] = parse_dbs(caches_info[name])
            caches_info[name]['options'] = options

        return caches_info

    def get(self, request):
        return render_to_response("redis_cache/stats.html", {},
            context_instance=RequestContext(request))
    
    def post(self, request):
        context = {'info':self.get_info()}
        return render_to_response("redis_cache/stats_include.html", context,
            context_instance=RequestContext(request))

    @method_decorator(login_required)
    def dispatch(self, *args, **kwargs):
        return super(RedisStatsView, self).dispatch(*args, **kwargs)
