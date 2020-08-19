# ISAC-SIMO
#### Django Backend Repository
---
#### Bash Script:
```sh
pip3 install --user python-dotenv
pip3 install --user django
virtualenv -p python3 env
source env/bin/activate
pip install -r requirements.txt
```
>If using pipenv (e.g. for windows) then use this:
```sh
pipenv install
```
```sh
python manage.py migrate
python manage.py createsuperuser
```
##### You can also use ``` bash pull.sh ``` script after updating the username inside the file to trigger reload

#### Procfile to Run In Root Port:
```sh
web: python manage.py runserver 0.0.0.0:$PORT
```

### Details for Pythonanywhere:
<details>
    <summary>Click to view</summary>

#### Useful .bashrc Alias for the project if hosted in Pythonanywhere:

<details>
    <summary>Click to view</summary>

```sh
alias toenv="cd /home/{{username}}/isac && source env/bin/activate"

alias server.log="cd /var/log && tail -f {{username}}.pythonanywhere.com.server.log"
alias error.log="cd /var/log && tail -f {{username}}.pythonanywhere.com.error.log"
alias access.log="cd /var/log && tail -f {{username}}.pythonanywhere.com.access.log"

alias server.up="toenv && sed -i 's/MAINTENANCE=True/MAINTENANCE=False/g' .env && touch /var/www/{{username}}_pythonanywhere_com_wsgi.py"
alias server.down="toenv && sed -i 's/MAINTENANCE=False/MAINTENANCE=True/g' .env && touch /var/www/{{username}}_pythonanywhere_com_wsgi.py"

alias reload="touch /var/www/{{username}}_pythonanywhere_com_wsgi.py"
```

</details>

#### Pythonanywhere wsgi.py:

<details>
    <summary>Click to view</summary>

```python
import os
import sys
from dotenv import load_dotenv

project_home = u'/home/{{username}}/isac'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

load_dotenv(os.path.join(project_home, '.env'))

os.environ['DJANGO_SETTINGS_MODULE'] = 'isac_simo.settings'

from django.core.wsgi import get_wsgi_application
from django.contrib.staticfiles.handlers import StaticFilesHandler
application = StaticFilesHandler(get_wsgi_application())
```

</details>

#### Static Files:

<details>
    <summary>Click to view</summary>

| URL           | Directory                      |
| ------------- |:------------------------------:|
| /static/      | /home/{{username}}/isac/static |
| /media/       | /home/{{username}}/isac/media  |

</details>

#### If Static Files that does not exist e.g. https://example.com/static/bad-directory keeps throwing unhandled error use this temporary fix:

<details>
    <summary>Click to view</summary>

Inside ```env/lib/python3.7/site-packages/django/core/handlers/base.py``` find ```get_response``` without leading underscore and change it to as below:

```python
from django.shortcuts import render

def get_response(self, request):
    """Return an HttpResponse object for the given HttpRequest."""
    # Setup default url resolver for this thread
    set_urlconf(settings.ROOT_URLCONF)
    try:
        response = self._middleware_chain(request)

        response._closable_objects.append(request)

        # If the exception handler returns a TemplateResponse that has not
        # been rendered, force it to be rendered.
        if not getattr(response, 'is_rendered', True) and callable(getattr(response, 'render', None)):
            response = response.render()

        if response.status_code == 404:
            logger.warning(
                'Not Found: %s', request.path,
                extra={'status_code': 404, 'request': request},
            )

        return response
    except:
        return render(request, '404.html', status=404)
```

</details>

</details>

### Note:
- Create ``` .env ``` file using ``` .env.example ``` and fill as required
- ``` database_settings.py ``` needs to be updated (or use DATABASE_URL in ``` .env ``` file)
- USER TYPES = "User", "Engineer", "Government", "Project Admin", "Admin"
- Can only register as User or Project Admin.
- Project Admin can only manage self projects and linked stuffs.


> Developed By: Build Change

> Supported By: IBM