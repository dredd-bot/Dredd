"""
Dredd, discord bot
Copyright (C) 2020 Moksej
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

import discord
import os
import random
import typing
import datetime
import time
import json
import config
import asyncpg
import asyncio
import aiohttp
from discord.ext import commands, tasks
from itertools import cycle
from db import emotes

asyncio.set_event_loop(asyncio.SelectorEventLoop())

async def run():
    description = "A bot written in Python that uses asyncpg to connect to a postgreSQL database."

    # NOTE: 127.0.0.1 is the loopback address. If your db is running on the same machine as the code, this address will work
    db = await asyncpg.create_pool(**config.DB_CONN_INFO)

    bot = Bot(description=description, db=db)
    if not hasattr(bot, 'uptime'):
        bot.uptime = datetime.datetime.utcnow()
    try:
        blacklist_user = await bot.db.fetch("SELECT * FROM blacklist")
        for user in blacklist_user:
            bot.blacklisted_users[user['user_id']] = [user['reason']]
        print(f'[BLACKLIST] Successfully loaded user blacklist [{len(blacklist_user)}]')
        blacklist_guild = await bot.db.fetch("SELECT * FROM blockedguilds")
        for guild in blacklist_guild:
            bot.blacklisted_guilds[guild['guild_id']] = [guild['reason']]
        print(f'[BLACKLIST] Successfully loaded user blacklist [{len(blacklist_guild)}]')
        afk_user = await bot.db.fetch("SELECT * FROM userafk")
        for user in afk_user:
            bot.afk_users[user['user_id'], user['guild_id']] = [user['message']]
        print(f'[AFK] AFK users were loaded [{len(afk_user)}]')
        temp_mutees = await bot.db.fetch("SELECT * FROM moddata")
        for res in temp_mutees:
            bot.temp_timer.append((res['guild_id'], res['user_id'], res['mod_id'], res['reason'], res['time'], res['role_id']))
        print(f'[TEMP MUTE] Mutees were loaded [{len(temp_mutees)}]')
        await bot.start(config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        await db.close()
        await bot.logout()


async def get_prefix(bot, message):
    if not message.guild:
        return
    if message.guild:
        prefix = await bot.db.fetchval("SELECT prefix FROM guilds WHERE guild_id= $1", message.guild.id)
        if not await bot.is_admin(message.author):
            custom_prefix = prefix
        elif await bot.is_admin(message.author):
            custom_prefix = ['d ', prefix]
        return custom_prefix
    if custom_prefix is None:
        return



class Bot(commands.AutoShardedBot):
    def __init__(self, **kwargs):
        super().__init__(
            command_prefix = ['rw '],
            case_insensitive = True,
            owner_id = 345457928972533773,
            reconnect = True,
            allowed_mentions = discord.AllowedMentions(roles=False, users=False, everyone=False),
            max_messages=10000
        )
        for extension in config.EXTENSIONS:
            try:
                self.load_extension(extension)
                print(f'[EXTENSION] {extension} was loaded successfully!')
            except Exception as e:
                print(f'[WARNING] Could not load extension {extension}: {e}')

        self.db = kwargs.pop("db")
        self.counter = 0
        self.cmdUsage = {}
        self.cmdUsers = {}
        self.guildUsage = {}

        self.embed_color = 0x0058D6 #0058D6
        self.logembed_color = 0xD66060 #D66060
        self.log_color = 0x1EA2B4 #1EA2B4
        self.error_color = 0xD12312 #D12312
        self.update_color = 0xCCE021 #CCE021
        self.automod_color = 0xb54907 #b54907
        self.logging_color = 0xE08C0B #E08C0B
        self.memberlog_color = 0x55d655 #55d655
        self.join_color = 0xEE621B #EE621B
        
        self.e = emotes
        self.config = config

        self.loop = asyncio.get_event_loop()
        self.session = aiohttp.ClientSession(loop=self.loop)
        self.blacklisted_guilds = {}
        self.blacklisted_users = {}
        self.afk_users = {}
        self.temp_timer = []

    def get(self, k, default=None):
        return super().get(k.lower(), default)

    def get_category(self, name):
        return self.categories.get(name)

    async def is_owner(self, user):
        return await self.db.fetchval("SELECT user_id FROM owners WHERE user_id = $1", user.id)
    
    async def is_admin(self, user):
        if await self.is_owner(user):
            return True
        return await self.db.fetchval("SELECT user_id FROM admins WHERE user_id = $1", user.id)

    async def close(self):
        await self.session.close()
        await super().close()
    
    def create_task_and_count(self, coro):
        self.counter += 1

        async def do_stuff():
            await coro
            self.counter -= 1

        self.loop.create_task(do_stuff())


    async def on_message_edit(self, before, after):

        if before.author.bot:
            return

        if before.content == after.content:
            return

        await self.process_commands(after)

    async def temp_punishment(self, guild: int, user: int, mod: int, reason: str, time: int, role: int):
        await self.db.execute("INSERT INTO moddata(guild_id, user_id, mod_id, reason, time, role_id) VALUES($1, $2, $3, $4, $5, $6)", guild, user, mod, reason, time, role)

        self.temp_timer.append((guild, user, mod, reason, time, role))



loop = asyncio.get_event_loop()
loop.run_until_complete(run())
