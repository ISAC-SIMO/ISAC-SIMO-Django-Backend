from django.core.serializers import serialize
from django.db.models.query import QuerySet
from django.template import Library
register = Library()

@register.filter
def json(toPrase):
    try:
        if isinstance(toPrase, QuerySet):
            return serialize('json', toPrase)
        else:
            arr = serialize('json', [toPrase], ensure_ascii=False)
            return arr[1:-1]
    except Exception as e:
        print(e)
        return []