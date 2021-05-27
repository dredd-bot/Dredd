"""Dredd, discord bot
Copyright (C) 2021 Moksej
This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU Affero General Public License for more details.
You should have received a copy of the GNU Affero General Public License
along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import builtins
import contextvars
import gettext
import os.path
from glob import glob

BASE_DIR = "/home/ubuntu/GitHub/Dredd/Dredd-v3/"  # change this if you store your files under `src/` or similar
LOCALE_DEFAULT = 'en_US'
LOCALE_DIR = "locale"
locales = frozenset(map(os.path.basename, filter(os.path.isdir, glob(os.path.join(BASE_DIR, LOCALE_DIR, '*')))))

gettext_translations = {
    locale: gettext.translation(
        'bot',
        languages=(locale,),
        localedir=os.path.join(BASE_DIR, LOCALE_DIR))
    for locale in locales}

gettext_translations['en_US'] = gettext.NullTranslations()
locales |= {'en_US'}


def use_current_gettext(*args, **kwargs):
    if not gettext_translations:
        return gettext.gettext(*args, **kwargs)

    locale = current_locale.get()
    return (
        gettext_translations.get(
            locale,
            gettext_translations[LOCALE_DEFAULT]
        ).gettext(*args, **kwargs)
    )


current_locale = contextvars.ContextVar('i18n')
builtins._ = use_current_gettext


def set_current_locale():
    current_locale.set(LOCALE_DEFAULT)


set_current_locale()
