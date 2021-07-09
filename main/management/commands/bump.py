"""
Bump VERSION in settings file.
Must include "VERSION = x.x.x" in settings.py
Requires semantic_version library

COMMAND USAGE:
python manage.py bump              -> Updates to Next Patch
python manage.py bump --to=2.2.2   -> Updates Version Number to 2.2.2
python manage.py bump --type=major -> Updates to Next Major
python manage.py bump --type=minor -> Updates to Next Minor
python manage.py bump --type=patch -> Updates to Next Patch
"""
__author__ = "Niush Sitaula"

from django.core.management.base import BaseCommand
from django.conf import settings
import semantic_version

class Command(BaseCommand):
    CURRENT_VERSION = getattr(settings, "VERSION", "0.0.0")
    help = 'Bump VERSION in settings file'

    def add_arguments(self, parser):
        parser.add_argument('--to', help='Version Number')
        parser.add_argument('--type', type=str, choices=["major","minor","patch"], help='Bump Type. Accepts either of [major, minor, patch]')

    def handle(self, *args, **options):
        FINAL_VERSION = str(self.CURRENT_VERSION).strip()

        # UPDATE TO SPECIFIC VERSION
        if options.get('to'):
          FINAL_VERSION = options.get('to')
          if semantic_version.validate(FINAL_VERSION):
            FINAL_VERSION = str(FINAL_VERSION).strip()
            return self.update_settings(FINAL_VERSION)
          else:
            self.stdout.write(self.style.ERROR("Unable to Prase Version. Invalid value in '--to' argument. It must follow valid SemVer scheme."))
            return
        
        # UPDATE TO NEXT OF GIVEN TYPE
        elif options.get('type'):
          FINAL_VERSION = semantic_version.Version(FINAL_VERSION)
          if options.get('type') == "major":
            FINAL_VERSION = FINAL_VERSION.next_major()
          elif options.get('type') == "minor":
            FINAL_VERSION = FINAL_VERSION.next_minor()
          elif options.get('type') == "patch":
            FINAL_VERSION = FINAL_VERSION.next_patch()
          else:
            self.stdout.write(self.style.ERROR("Invalid Version Update Type Provided."))
            return
          return self.update_settings(str(FINAL_VERSION))

        # DEFAULT BUMPS TO NEXT PATCH
        else:
          FINAL_VERSION = semantic_version.Version(FINAL_VERSION)
          FINAL_VERSION = FINAL_VERSION.next_patch()
          return self.update_settings(str(FINAL_VERSION))
    
    def update_settings(self, FINAL_VERSION:str):
      import fileinput
      import re
      
      with fileinput.FileInput('isac_simo/settings.py', inplace=True, backup='.bak') as file:
        for line in file:
          if re.match(r"VERSION ?= ?['\"]"+self.CURRENT_VERSION+"['\"]", line):
            print(("VERSION = '" + FINAL_VERSION + "'"))
          else:
            print(line, end='')
      
      self.stdout.write(self.style.SUCCESS('VERSION UPDATED TO: ' + FINAL_VERSION))