# ISAC-SIMO

[![License](https://img.shields.io/badge/License-Apache2-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0) [![Slack](https://img.shields.io/badge/Join-Slack-blue)](https://callforcode.org/slack) [![Python 3.9](https://img.shields.io/badge/python-v3.9-blue)](https://github.com/ISAC-SIMO/ISAC-SIMO-Django-Backend)

[![CircleCI](https://circleci.com/gh/buildchange/ISAC-SIMO_Django/tree/master.svg?style=shield)](https://circleci.com/gh/buildchange/ISAC-SIMO_Django/?branch=master) ![Website](https://img.shields.io/website?down_message=offline&up_message=online&url=https%3A%2F%2Fwww.isac-simo.net%2F)

Intelligent Supervision Assistant for Construction - Sistema Inteligente de Monitoreo de Obra

> [View documentation](https://www.isac-simo.net/docs/) at isac-simo.net

### Django Backend Repository
---
### Bash Script:
```sh
pip install --upgrade pip
pip install pipenv
pipenv install
```

>Setup Postgresql or any desired Django supported database.
>
>Create ``` .env ``` file using ``` .env.example ``` and provide environment variables as required.
>
>``` database_settings.py ``` needs to be updated as per your database setup (or use DATABASE_URL in ``` .env ``` file)
```sh
pipenv run python manage.py migrate
pipenv run python manage.py createsuperuser
```

### Running Tests:
```sh
pipenv run python manage.py test --debug-mode --debug-sql --parallel
```
OR simply run without any flags:
```sh
pipenv run python manage.py test
```

### How to Bump Application Version?
<details>
    <summary>Click to view</summary>

We use SemVer scheme to manage the version number. We have created a Django Command to upgrade the version in the settings file.

#### Command Usage:
- `pipenv run python manage.py bump`              → Updates to Next Patch
- `pipenv run python manage.py bump --to=2.2.2`   → Updates Version Number to 2.2.2
- `pipenv run python manage.py bump --type=major` → Updates to Next Major
- `pipenv run python manage.py bump --type=minor` → Updates to Next Minor
- `pipenv run python manage.py bump --type=patch` → Updates to Next Patch

Releases and Tags can then be created accordingly.

</details>

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
- USER TYPES = "User", "Engineer", "Government", "Project Admin", "Admin"
- View detailed [Developer Guide](https://www.isac-simo.net/docs/developer-guide/) & [Web Application Guide](https://www.isac-simo.net/docs/web-application/)

## Contributing
Please read [our contributing guidelines](CONTRIBUTING.md) for details of how you can get involved and please abide by the [Code of Conduct](CONTRIBUTING.md#code-of-conduct).

## Contributors
<a href="https://github.com/ISAC-SIMO/ISAC-SIMO-Django-Backend/graphs/contributors">
  <img src="https://contributors-img.web.app/image?repo=ISAC-SIMO/ISAC-SIMO-Django-Backend" />
</a>

## License
This project is licensed under the Apache Software License, Version 2, unless otherwise stated.  Separate third party code objects invoked within this project are licensed by their respective providers pursuant to their own separate licenses. Contributions are subject to the [Developer Certificate of Origin, Version 1.1 (DCO)](https://developercertificate.org/) and the [Apache Software License, Version 2](http://www.apache.org/licenses/LICENSE-2.0.txt).

> A Call for Code with The Linux Foundation
> 
> Developed By: Build Change
> 
> Supported By: IBM
