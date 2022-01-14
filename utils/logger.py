"""
Dredd, discord bot
Copyright (C) 2022 Moksej
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

import time
import logging

from utils.enums import LogType
from logging.handlers import RotatingFileHandler

dredd_logger = logging.getLogger("dredd")
dredd_logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(  # type: ignore
    filename='logs/bot.log',
    encoding='utf-8',
    mode='w',
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    delay=0
)
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
dredd_logger.addHandler(handler)

dredd_commands = logging.getLogger("dredd_commands")
dredd_commands.setLevel(logging.DEBUG)
handler = RotatingFileHandler(  # type: ignore
    filename='logs/commands.log',
    encoding='utf-8',
    mode='w',
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    delay=0
)
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
dredd_commands.addHandler(handler)

wavelink_logger = logging.getLogger('wavelink.player')
wavelink_logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(  # type: ignore
    filename='logs/discord_voice.log',
    encoding='utf-8',
    mode='w',
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    delay=0
)
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
wavelink_logger.addHandler(handler)

del_logger = logging.getLogger('del.py')
del_logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(  # type: ignore
    filename='logs/del.log',
    encoding='utf-8',
    mode='w',
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    delay=0
)
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
del_logger.addHandler(handler)

discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(  # type: ignore
    filename='logs/discord.log',
    encoding='utf-8',
    mode='w',
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    delay=0)
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
discord_logger.addHandler(handler)


async def new_log(bot, timestamp: time, type: int, value: int):
    if not LogType.has_value(type):
        type = -1
        return dredd_logger.warning(f"{LogType(type)} - unknown log type, tried adding {value}")
    dredd_logger.info(f"{LogType(type)} - added {value}")
    query = "SELECT time FROM logging WHERE type = $1 and time > extract(epoch from now())::int - 86400"
    check = await bot.db.fetchval(query, type)  # keep adding +(value) if there are results in the last 24 hours
    if not check or type in {1, 2, 6, } and type != 10:
        await bot.db.execute("INSERT INTO logging VALUES($1, $2, $3)", timestamp, type, value)
    else:
        await bot.db.execute("UPDATE logging SET value = value + $1 WHERE type = $2 AND time = $3", value, type, check)
