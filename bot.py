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

import discord
import asyncio
import asyncpg
import config
import aiohttp
import sys
import psutil
import sr_api
import traceback
import logging
import websockets
import json
import async_cleverbot as ac

from discord.ext import commands

from db.cache import LoadCache, CacheManager, DreddUser, DreddGuild, Database as postgres, ReactionRoles
from utils import i18n, default
from collections import Counter
from typing import Optional, Union, Any
from utils.checks import is_disabled
from colorama import Fore as print_color
from utils.context import EditingContext

dredd_logger = logging.getLogger("dredd")

if sys.version_info < (3, 8, 0) or sys.version_info >= (3, 10, 0):
    raise Exception('Your python version is incompatible, please make sure you have Python 3.8 < 3.10 installed.')


async def run():
    description = "A bot written in Python that uses asyncpg to connect to a postgreSQL database."

    db = await postgres.connect()

    bot = Bot(description=description, db=db)
    if not hasattr(bot, 'uptime'):
        bot.uptime = discord.utils.utcnow()

    async def start_websocket():
        username, password, realm, port = config.WEBSOCKET
        async with websockets.serve(
            bot.handle_websocket,
            "localhost",
            port,
            create_protocol=websockets.basic_auth_protocol_factory(
                realm=realm, credentials=(username, password)
            ),
        ):
            await asyncio.Future()

    bot.keep_alive = bot.loop.create_task(start_websocket())

    try:
        dredd_logger.info("[CACHE] Loading cache.")
        await LoadCache.start(bot)  # type: ignore
        bot.session = aiohttp.ClientSession(loop=bot.loop)
        dredd_logger.info("[BOT] Starting bot.")
        # await bot.start(config.DISCORD_TOKEN)
        await bot.start(config.MAIN_TOKEN)
    except KeyboardInterrupt as e:
        dredd_logger.error(f"[Shutting Down] Occured while booting up: {e}.")
        await db.close()
        await bot.close()


async def get_prefix(bot, message):
    if bot.user.id == 663122720044875796:  # for beta, so I don't accidentally kill both bots
        custom_prefix = ['rw ', 'db ']
        return commands.when_mentioned_or(*custom_prefix)(bot, message)
    prefix = message.guild.data.prefix if message.guild else '!'
    custom_prefix = [prefix]
    if await bot.is_booster(message.author):
        boosters_prefix = message.author.data.prefix if message.author.data.prefix is not None else 'dredd '
        custom_prefix.append(boosters_prefix)
    if await bot.is_admin(message.author):
        custom_prefix.append('d ')

    return commands.when_mentioned_or(*custom_prefix)(bot, message)


# noinspection PyArgumentEqualDefault
class Bot(commands.AutoShardedBot):
    def __init__(self, **kwargs):
        super().__init__(
            command_prefix=get_prefix,
            case_insensitive=True,
            # case_insensitive_prefix=True,
            status=discord.Status.dnd,
            activity=discord.Activity(type=discord.ActivityType.competing, name='a boot up challenge'),
            owner_id=345457928972533773,
            reconnect=True,
            allowed_mentions=discord.AllowedMentions(users=False, roles=False, everyone=False, replied_user=True),
            slash_commands=False,  # Fuck slash commands
            max_messages=10000,
            chunk_guilds_at_startup=True,  # this is here for easy access. In case I need to switch it fast to False I won't need to look at docs.
            intents=discord.Intents(
                guilds=True,  # guild/channel join/remove/update
                members=True,  # member join/remove/update
                bans=True,  # member ban/unban
                emojis=False,  # emoji update
                integrations=False,  # integrations update
                webhooks=False,  # webhook update
                invites=False,  # invite create/delete
                voice_states=True,  # voice state update
                presences=False,  # member/user update for games/activities
                guild_messages=True,  # message create/update/delete
                dm_messages=True,  # message create/update/delete
                guild_reactions=True,  # reaction add/remove/clear
                dm_reactions=True,  # reaction add/remove/clear
                guild_typing=False,  # on typing
                dm_typing=False,  # on typing
            )
        )

        self.config = config

        for extension in config.EXTENSIONS:
            try:
                self.load_extension(extension)
                print(print_color.GREEN, f'[EXTENSION] {extension} was loaded successfully!')
            except Exception as e:
                print(print_color.RED, f'[WARNING] Could not load extension {extension}: {e}')

        self.db: asyncpg.pool.Pool = kwargs.pop("db")
        self.cmdUsage = {}
        self.cmdUsers = {}
        self.guildUsage = {}
        self.process = psutil.Process()
        self.ctx = EditingContext

        self.rr_image = 'https://moksej.xyz/05zRCwEjkA.png'
        self.website = 'https://dreddbot.xyz'
        self.support = 'https://discord.gg/f3MaASW'
        self.invite = 'https://dreddbot.xyz/invite'
        self.privacy = 'https://dreddbot.xyz/privacy-policy'
        self.license = '<https://github.com/TheMoksej/Dredd/blob/master/LICENSE>'
        self.gif_pfp = 'https://cdn.discordapp.com/attachments/667077166789558288/747132112099868773/normal_3.gif'
        self.vote = '<https://discord.boats/bot/667117267405766696/vote>'
        self.source = '<https://github.com/dredd-bot/Dredd/>'
        self.statuspage = '<https://status.dreddbot.xyz>'
        self.require_vote: bool = True
        self.bot_lists = {'dbots': "[Discord Bot Labs](https://dbots.cc/dredd 'bots.discordlabs.org')", 'dboats': "[Discord Boats](https://discord.boats/bot/667117267405766696/vote 'discord.boats')",
                          'dbl': "[Discord Bot list](https://discord.ly/dredd/upvote 'discordbotlist.com')", 'shitgg': "[Top.GG](https://top.gg/bot/667117267405766696/vote 'top.gg')",
                          'dservices': "[Discord Services](https://discordservices.net/bot/dredd 'discordservices.net')", 'void': "[Void Bots](https://voidbots.net/bot/667117267405766696/vote 'voidbots.net')",
                          'discords': "[Discords](https://discords.com/bots/bot/667117267405766696/vote 'discords.com')", 'topcord': "[Topcord](https://topcord.xyz/bot/667117267405766696 'topcord.xyz')"}

        self.cleverbot = ac.Cleverbot(config.CB_TOKEN)
        self.join_counter = Counter()  # counter for anti raid so the bot would ban the user if they try to join more than 5 times in short time span
        self.counter = Counter()  # Counter for global commands cooldown
        self.automod_counter = Counter()  # Counter for automod logs

        self.cache = CacheManager
        self.cache_reload = LoadCache
        self.cmd_edits = {}
        self.dm = {}
        self.log_dm = True
        self.dms = {}  # cache for checks if user was already informed about dm logging
        self.updates = {}
        self.snipes = {}
        self.sr_api = sr_api.Client()
        self.voted = {}

        self.guilds_data = {}
        self.loop = asyncio.get_event_loop_policy().get_event_loop()
        self.guild_loop = {}
        self.to_unmute = {}
        self.to_unban = {}
        self.music_guilds = {}

        self.testers = {}

        # ranks
        self.devs = {}
        self.admins = {}
        self.boosters = {}
        self.lockdown = False
        self.auto_reply = True
        self.settings = {}
        self.radio_stations = {}
        self.blacklist = {}
        self.check_duration = {}

        # guilds / moderation
        self.prefix = {}
        self.moderation = {}
        self.memberlog = {}
        self.joinlog = {}
        self.leavelog = {}
        self.guildlog = {}
        self.joinrole = {}
        self.joinmessage = {}
        self.leavemessage = {}
        self.messageedits = {}
        self.messagedeletes = {}
        self.antihoist = {}
        self.automod = {}
        self.massmention = {}
        self.masscaps = {}
        self.invites = {}
        self.links = {}
        self.spam = {}
        self.modlog = {}
        self.raidmode = {}
        self.temp_bans = {}
        self.temp_mutes = {}
        self.mutes = {}
        self.bans = {}
        self.mute_role = {}
        self.mod_role = {}
        self.admin_role = {}
        self.channels_whitelist = {}
        self.roles_whitelist = {}
        self.users_whitelist = {}
        self.guild_disabled = {}
        self.cog_disabled = {}
        self.case_num = {}
        self.rr = {}

        # other
        self.afk = {}
        self.status_op = {}
        self.snipes_op = {}
        self.nicks_op = {}
        self.badges = {}
        self.disabled_commands = {}
        self.translations = {}
        self.reminders = {}
        self.mode247 = {}
        self.catched_errors = Counter()
        self.rr_setup = {}
        self.automod_time = {}

        # custom stuff
        setattr(discord.TextChannel, "can_send", property(self.send_check))
        setattr(discord.Thread, "can_send", property(self.send_check))
        setattr(discord.Guild, "data", property(self.guild_cache))
        setattr(discord.Message, "rr", property(self.message_roles))
        setattr(discord.User, "data", property(self.user_cache))
        setattr(discord.Member, "data", property(self.user_cache))

    @staticmethod
    def send_check(b) -> bool:
        return b.permissions_for(b.guild.me).send_messages

    def guild_cache(self, g) -> DreddGuild:
        return self.cache.get_guild(self, g.id)  # type: ignore

    def user_cache(self, u) -> DreddUser:
        return self.cache.get_user(self, u)  # type: ignore

    def message_roles(self, msg) -> ReactionRoles:
        return self.cache.get_message(self, msg.id)  # type: ignore

    def get(self, k, default=None):
        return super().get(k.lower(), default)

    async def handle_websocket(self, connection: websockets.WebSocketClientProtocol):
        if not self.is_ready():
            await connection.send(json.dumps({"error": "NOT_READY"}))
        else:
            try:
                async for message in connection:
                    jsonified = json.loads(message)
                    event = jsonified.get("event")
                    if event == "GET_GUILD":
                        data = default.handle_request(self, jsonified["data"])
                        await connection.send(data)
                    elif event == "UPDATE_GUILD":
                        await default.handle_update(self, jsonified["data"])
                        print("done")
                    else:
                        await connection.send("Unknown code.")
            except websockets.ConnectionClosed:
                return
            except Exception as e:
                await connection.send(json.dumps({"error": e}))

    async def close(self) -> None:
        dredd_logger.info("[BOT] Shutting down.")
        await self.session.close()  # type: ignore
        await super().close()

    async def is_owner(self, user) -> Optional[str]:
        return CacheManager.get(self, 'devs', user.id)  # type: ignore

    async def is_admin(self, user) -> Optional[Union[bool, str]]:
        if CacheManager.get(self, 'devs', user.id):  # type: ignore
            return True
        return CacheManager.get(self, 'admins', user.id)  # type: ignore

    async def is_booster(self, user) -> Optional[Union[bool, str]]:
        if CacheManager.get(self, 'devs', user.id):  # type: ignore
            return True
        return CacheManager.get(self, 'boosters', user.id) is not None  # type: ignore

    async def is_blacklisted(self, user) -> Optional[str]:
        return CacheManager.get(self, 'blacklist', user.id)  # type: ignore

    @staticmethod
    async def is_disabled(ctx, command):
        return await is_disabled(ctx, command=command)

    async def on_error(self, event_method: str, *args: Any, **kwargs: Any) -> None:
        if not self.catched_errors.get(event_method):  # so it wouldn't spam the errors
            err, err2, err3 = sys.exc_info()
            error = '```py\n{1}{0}: {2}\n```'.format(err.__name__, ''.join(traceback.format_tb(err3)), err2)
            log_channel = self.get_channel(self.settings['channels']['event-errors'])
            embed = discord.Embed(color=self.settings['colors']['error_color'], timestamp=discord.utils.utcnow())
            embed.description = error
            await log_channel.send(embed=embed, content=f"{self.settings['emojis']['misc']['error']} Error occured on - **{event_method}**")
        return self.catched_errors.update({event_method})

    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.guild:
            i18n.current_locale.set(self.translations.get(interaction.guild.id, 'en_US'))
        await self.process_slash_commands(interaction)

    async def on_message(self, message):
        if message.author.bot or not self.is_ready():
            return
        try:
            ctx = await self.get_context(message, cls=EditingContext)
            if message.guild:
                i18n.current_locale.set(self.translations.get(message.guild.id, 'en_US'))
            if ctx.valid:
                await self.invoke(ctx)
        except Exception:
            return

    async def on_message_edit(self, before, after):
        if before.author.bot or not self.is_ready():
            return

        if after.content != before.content:
            try:
                ctx = await self.get_context(after, cls=EditingContext)
                if after.guild:
                    i18n.current_locale.set(self.translations.get(after.guild.id, 'en_US'))
                if ctx.valid:
                    await self.invoke(ctx)
            except discord.NotFound:
                return


if __name__ == '__main__':
    loop = asyncio.get_event_loop_policy().get_event_loop()
    loop.run_until_complete(run())
