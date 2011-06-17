from django.core.cache import get_cache
from django.http import HttpResponse


def someview(request):
    cache = get_cache('redis_cache.cache://127.0.0.1')
    cache.set("foo", "bar")
    return HttpResponse("Pants")