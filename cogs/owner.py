"""
Dredd, discord bot
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

import discord
import typing
import inspect

from discord.ext import commands
from discord.utils import escape_markdown
from importlib import reload as importlib_reload

from prettytable import PrettyTable
from utils import btime, default
from utils.paginator import TextPages
from db.cache import LoadCache as LC
from db.cache import CacheManager as CM
from datetime import datetime, timezone

# THIS COG IS NOT MADE WELL
# AS I DIDN'T WANT TO SPEND
# MUCH TIME ON MAKING COGS
# FOR BOT STAFF. MAIN POINT
# WAS TO MAKE EACH COMMAND
# FUNCTIONAL WITHOUT ANY BUGS
# THIS IS WHERE WE AT RIGHT NOW


# noinspection PySimplifyBooleanCheck
class owner(commands.Cog, name="Owner"):

    def __init__(self, bot):
        self.bot = bot
        self.help_icon = "<:crown:756602830986412063>"
        self.big_icon = "https://cdn.discordapp.com/emojis/691667205082841229.png?v=1"

    async def cog_check(self, ctx: commands.Context):
        if not await ctx.bot.is_owner(ctx.author) or ctx.author.id != 345457928972533773:
            raise commands.NotOwner()
        return True

    @commands.group(brief="Main developer commands", invoke_without_command=True)
    async def dev(self, ctx):
        """ Developer commands.
        Used to manage bot stuff."""

        await ctx.send_help(ctx.command)

    @dev.command(name="sql")
    async def sql(self, ctx, *, query):
        """ Execute psql query """
        try:
            if query.__contains__('guild.id'):
                query = query.replace('guild.id', str(ctx.guild.id))
            if query.__contains__('author.id'):
                query = query.replace('author.id', str(ctx.author.id))
            if query.__contains__('channel.id'):
                query = query.replace('channel.id', str(ctx.channel.id))

            if not query.lower().startswith("select"):
                data = await self.bot.db.execute(query)
                return await ctx.send(data)

            data = await self.bot.db.fetch(query)
            if not data:
                return await ctx.send("Table seems to be empty!")
            columns = []
            values = []
            for k in data[0].keys():
                columns.append(k)

            for y in data:
                rows = []
                for v in y.values():
                    rows.append(v)
                values.append(rows)

            x = PrettyTable(columns)
            for d in values:
                x.add_row(d)

            pages = TextPages(ctx,
                              text=f'\n{x}')
            return await pages.paginate()
        except Exception as e:
            await ctx.send(e)

    @dev.command(name='reload-cache', aliases=['rcache'])
    async def dev_reload_cache(self, ctx):
        cache = await LC.reloadall(self.bot)
        await ctx.send("I've successfully reloaded cache!")

    @dev.command(name='reload-config', aliases=['rconfig', 'rconf'])
    async def dev_reload_config(self, ctx):
        importlib_reload(self.bot.config)
        await ctx.send("I've successfully reloaded config!")

    @dev.group(name='category', aliases=['cog'], invoke_without_command=True)
    async def dev_category(self, ctx):
        """ Manage bot categories """
        await ctx.send_help(ctx.command)

    @dev_category.command(name='reload', aliases=['r'])
    async def dev_category_reload(self, ctx, name: str):
        """ Reload category """
        try:
            self.bot.reload_extension(f"cogs.{name}")
            await ctx.send(f"🔁 Reloaded extension **{name}.py**")

        except Exception as e:
            return await ctx.send(f"```py\n{e}```")

    @dev_category.command(name='unload', aliases=['u'])
    async def dev_category_unload(self, ctx, name: str):
        """ Unload category """
        try:
            self.bot.unload_extension(f"cogs.{name}")
            await ctx.send(f"{self.bot.settings['emojis']['misc']['leave']} Unloaded extension **{name}.py**")

        except Exception as e:
            return await ctx.send(f"```py\n{e}```")

    @dev_category.command(name='load', aliases=['l'])
    async def dev_category_load(self, ctx, name: str):
        """ Load category """
        try:
            self.bot.load_extension(f"cogs.{name}")
            await ctx.send(f"{self.bot.settings['emojis']['misc']['join']} Loaded extension **{name}.py**")

        except Exception as e:
            return await ctx.send(f"```py\n{e}```")

    @dev.command(name='update', brief='Change the update')
    async def dev_update(self, ctx, *, update: str):
        await self.bot.db.execute("UPDATE updates SET update = $1, time = $2", update, datetime.now())
        self.bot.updates = {'update': update, 'announced': datetime.now()}
        await ctx.send(f"{self.bot.settings['emojis']['misc']['announce']} | **Changed bot latest news to:**\n{escape_markdown(update, as_needed=False)}")

    @dev.command(name='reboot', aliases=['logout', 'die', 'shut'])
    async def dev_reboot(self, ctx):
        await ctx.send("Logging out now\N{HORIZONTAL ELLIPSIS}")
        await self.bot.close()

    @commands.group(brief='Change bot\'s theme', invoke_without_command=True)
    async def theme(self, ctx):
        await ctx.send_help(ctx.command)

    @theme.command(brief='normal theme', name='normal')
    async def theme_normal(self, ctx):
        await default.change_theme(ctx, 2901114, 'normal', '<:dredd:781660570431913984>')

    @theme.command(brief='easter theme', name='easter')
    async def theme_easter(self, ctx):
        await default.change_theme(ctx, 14642763, 'easter', '<:easter:697748080056991745>')

    @theme.command(brief='valentine theme', name='valentine')
    async def theme_valentine(self, ctx):
        await default.change_theme(ctx, 15890317, 'valentine', '<:valentine:704079542775447623>')

    @theme.command(brief='halloween theme', name='halloween')
    async def theme_halloween(self, ctx):
        await default.change_theme(ctx, 9670800, 'halloween', '<:halloween:704079542980968478>')

    @theme.command(brief='xmas theme', name='xmas')
    async def theme_xmas(self, ctx):
        await default.change_theme(ctx, 10748955, 'xmas', '<:dreddxmas:781660571362918400>')

    @theme.command(brief='beta theme', name='beta')
    async def theme_beta(self, ctx):
        await default.change_theme(ctx, 9019378, 'dreddbeta', '<:dredd:677988736692256779>')

    @dev.group(name='inspect', invoke_without_command=True, aliases=['ins', 'i'])
    async def dev_inspect(self, ctx):
        await ctx.send_help(ctx.command)

    @dev_inspect.command(name='user', aliases=['u'])
    async def dev_inspect_user(self, ctx, *, user: typing.Union[discord.User, str]):

        user = await default.find_user(ctx, user)

        if not user:
            return await ctx.send(f"{ctx.bot.settings['emojis']['misc']['warn']} | User could not be found")

        if not self.bot.get_user(user.id):
            color = ctx.bot.settings['colors']['fetch_color']
        else:
            color = ctx.bot.settings['colors']['embed_color']

        acks = default.bot_acknowledgements(ctx, user, True)
        suggestions = await self.bot.db.fetch("SELECT suggestion_id FROM suggestions WHERE user_id = $1", user.id)
        commands = await self.bot.db.fetchval("SELECT sum(usage) FROM command_logs WHERE user_id = $1", user.id)
        ids = []
        for id in suggestions:
            ids.append(f"{id['suggestion_id']}")
        bls = CM.get(self.bot, 'blacklist', user.id)
        bl = "No." if not bls else f"Yes. **Reason:** {bls['reason']}"
        past = await self.bot.db.fetch("SELECT * FROM bot_history WHERE _id = $1", user.id)

        e = discord.Embed(color=color, timestamp=datetime.now(timezone.utc))
        e.set_author(name=f"{user}'s Information", icon_url=user.avatar_url)
        dm_check = '\n*Blocked from communicating in DMs*' if bls and bls['type'] == 1 else ''
        e.description = f"""
**Full username:** [{user}](https://discord.com/users/{user.id}) {acks if acks else ''}
**Avatar URL:** [Click here]({user.avatar_url})
**Shared servers:** {len([x for x in self.bot.guilds if x.get_member(user.id)])}
**Commands Used:** {commands}
**Suggestions suggested:** {len(suggestions)} {f'**IDs:** {", ".join(ids)}' if len(suggestions) != 0 else ''}
**Blacklisted?** {bl}{dm_check}
**Been blacklisted?** {f"Yes. {len(past)} time(s)" if past != [] else "No"}
"""
        e.set_thumbnail(url=user.avatar_url)
        if past:
            msg = []
            for num, res in enumerate(past, start=1):
                dev = self.bot.get_user(res['dev'])
                msg.append(f"`[{num}]` {escape_markdown(str(user), as_needed=False)} - {'Liftable' if res['liftable'] == 0 else 'Not liftable'}\nIssued by **{dev}** {btime.human_timedelta(res['issued'])}\n**Reason:** {res['reason']}\n")
            e.add_field(name='Previous blacklists:', value=''.join(msg))
        await ctx.send(embed=e)

    @dev_inspect.command(name='server', aliases=['s'])
    async def dev_inspect_server(self, ctx, server: int):
        guild = self.bot.get_guild(server)
        if guild is None:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | That server doesn't seem to exist. Are you sure the server ID is correct?")
        if not guild.chunked:
            await guild.chunk(cache=True)

        acks = default.server_badges(ctx, guild)
        logging = default.server_logs(ctx, guild)
        people = len([x for x in guild.members if not x.bot])
        bots = len([x for x in guild.members if x.bot])
        botfarm = int(100 / len(guild.members) * bots)
        sperms = dict(guild.me.guild_permissions)
        bl = CM.get(self.bot, 'blacklist', guild.id)
        sug_check = '\n\n*Blocked from suggesting suggestions*' if bl and bl['type'] == 0 else ''
        past = await self.bot.db.fetch("SELECT * FROM bot_history WHERE _id = $1", guild.id)
        prefix = CM.get(self.bot, 'prefix', guild.id)
        muterole = await default.get_muterole(ctx, guild)
        language = self.bot.cache.get(self.bot, 'translations', guild.id)
        mod_role = self.bot.cache.get(self.bot, 'mod_role', guild.id)
        admin_role = self.bot.cache.get(self.bot, 'admin_role', guild.id)
        guild_owner = await self.bot.fetch_user(guild.owner_id)
        perm = []
        invites = ''
        try:
            guildinv = await guild.invites()
            for inv in guildinv[:1]:
                invites += f'{inv}'
        except Exception:
            pass
        name = f'[{guild.name}]({invites})' if invites else f"{guild.name}"

        for p in sperms.keys():
            if sperms[p] is True and guild.me.guild_permissions.administrator is False:
                perm.append(f"`{p.replace('_', ' ').title()}`")
        if guild.me.guild_permissions.administrator:
            perm.append('Administrator')

        e = discord.Embed()
        if botfarm > 75 and guild.member_count > 100:
            e.color = self.bot.settings['colors']['deny_color']
            e.title = f"{self.bot.settings['emojis']['misc']['warn']} This server is a possible bot farm. Make sure they aren't abusing the bot."
        else:
            e.color = self.bot.settings['colors']['embed_color']
        e.add_field(name='Important information:', value=f"""
**Server name:** {name} {acks if acks else ''}
**Server ID:** {guild.id}
**Total Members:** {len(guild.members):,} which {people:,} of them are humans and {bots:,} bots. `[Ratio: {botfarm}%]`
**Server Owner:** {guild_owner} ({guild_owner.id})""", inline=False)
        e.add_field(name='Other information:', value=f"""
**Total channels/roles:** {len(guild.channels)} channels / {len(guild.roles)} roles
**Server created at:** {default.date(guild.created_at)}
**Joined server at:** {btime.human_timedelta(guild.get_member(self.bot.user.id).joined_at.replace(tzinfo=None), source=datetime.utcnow())} ({default.date(guild.get_member(self.bot.user.id).joined_at)})
**Prefix:** {escape_markdown(prefix)}
**Language:** {language}
**Mute role:** {f"{muterole.id}" if muterole else 'Not found'}
**Mod & Admin Roles:** {mod_role}; {admin_role}""", inline=False)
        e.add_field(name="My permissions:", value=", ".join(perm))
        e.add_field(name='Logging:', value=logging)
        if past:
            msg = []
            for num, res in enumerate(past, start=1):
                dev = self.bot.get_user(res['dev'])
                msg.append(f"`[{num}]` {escape_markdown(str(guild), as_needed=False)} - {'Liftable' if res['liftable'] == 0 else 'Not liftable'}\nIssued by **{dev}** {btime.human_timedelta(res['issued'])}\n**Reason:** {res['reason']}\n")
            e.add_field(name='Previous blacklists:', value=f"{sug_check}\n" + ''.join(msg), inline=False)
        e.set_thumbnail(url=guild.icon_url)
        await ctx.send(embed=e)

    @dev_inspect.command(name='command', aliases=['c', 'cmd'])
    async def dev_inspect_command(self, ctx, *, command: str):
        cmd = self.bot.get_command(command)
        if cmd is None:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} {command} not found.")
        source = inspect.getsource(cmd.callback)
        obj = self.bot.get_command(command.replace('.', ' '))

        src = obj.callback.__code__
        lines, firstlineno = inspect.getsourcelines(src)
        module = obj.callback.__module__
        location = module.replace('.', '/') + '.py'
        used = await self.bot.db.fetchval("SELECT sum(usage) FROM command_logs WHERE command = $1", str(cmd))
        tot_errors = await self.bot.db.fetchval("SELECT count(*) FROM errors WHERE error_command = $1", str(cmd))
        resolved = await self.bot.db.fetch('SELECT array_agg(error_id), count(*) FROM errors WHERE error_command = $1 AND error_status = $2', str(cmd), 1)
        unresolved = await self.bot.db.fetch('SELECT array_agg(error_id), count(*) FROM errors WHERE error_command = $1 AND error_status = $2', str(cmd), 0)

        e = discord.Embed(color=self.bot.settings['colors']['embed_color'], title="Command Inspection")
        e.description = (f"**Command:** `{cmd}`\n**Location:** {location}\n**Lines:** {firstlineno} - {firstlineno + len(lines) - 1}\n"
                         f"**Total:** {firstlineno + len(lines) - 1 - firstlineno} lines\n**Used:** {used} times\n\n"
                         f"**Total Errors Caught:** {tot_errors}\n**Resolved:** {str(resolved[0]['count'])} - {resolved[0]['array_agg'] or 'No errors'}\n"
                         f"**Unresolved:** {str(unresolved[0]['count'])} - {unresolved[0]['array_agg'] or 'No errors'}")
        e.set_thumbnail(url=cmd.cog.big_icon)
        await ctx.send(embed=e)

    @dev_inspect.command(name='suggestion', aliases=['sug'])
    async def dev_inspect_suggestion(self, ctx, suggestion: int):
        """ Inspect a suggestion """

        db_check = await self.bot.db.fetch("SELECT msg_id, user_id FROM suggestions WHERE suggestion_id = $1", suggestion)

        if not db_check:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} Suggestion with ID `#{suggestion}` not found.")

        try:
            message = await self.bot.get_guild(self.bot.settings['servers']['main']).get_channel(self.bot.settings['channels']['suggestions']).fetch_message(db_check[0]['msg_id'])
            user = self.bot.get_user(db_check[0]['user_id']) or '*unable to get*'
            return await ctx.send(f"Displaying suggestion `#{suggestion}` suggested by {user}", embed=message.embeds[0])
        except discord.errors.NotFound:
            return await ctx.send("Was unable to fetch the message :/")

    @dev.group(brief='Update user ranks', invoke_without_command=True, name='rank')
    async def dev_rank(self, ctx):
        await ctx.send_help(ctx.command)

    @dev_rank.command(brief='Add a rank to an user', name='add')
    async def dev_rank_add(self, ctx, user: discord.User, rank: str):
        """ Add a rank for user """

        ranks = {
            "staff": "admins",
            "booster": "boosters",
            "donator": 256,
            "bot_admin": 2
        }

        if rank not in ranks:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} Rank doesn't exist!")

        check = CM.get(self.bot, ranks[rank], user.id)

        if check:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} Looks like user is already a {rank}")
        else:
            await self.bot.db.execute(f"INSERT INTO {ranks[rank]} VALUES($1, $2)", user.id, '-')
            attr = getattr(self.bot, ranks[rank])
            attr[user.id] = '-'
            rank = 'donator' if ranks[rank] == 'boosters' else 'bot_admin'
            badge = ctx.bot.settings['emojis']['ranks'][rank]
            if CM.get(self.bot, 'badges', user.id):
                await self.bot.db.execute("UPDATE badges SET flags = flags + $1 WHERE _id = $2", ranks[rank], user.id)
            else:
                await self.bot.db.execute("INSERT INTO badges VALUES($1, $2)", user.id, ranks[rank])
            await LC.reloadall(self.bot)
            try:
                dm_message = f"Hey {user}! Just letting you know your rank was updated and you're now a **{rank}**!"
                await user.send(dm_message)
                conf_msg = ' Sent them a DM as well.'
            except Exception:
                conf_msg = ' Was unable to send them a DM.'
                pass
            await ctx.send(f"{badge} **{user}**'s rank was updated and is now a {rank}.{conf_msg} *Also add them a role*")

    @dev_rank.command(brief='Remove rank from an user', name='remove')
    async def dev_rank_remove(self, ctx, user: discord.User, rank: str):
        """ Remove a rank from an user """

        ranks = {
            "staff": "admins",
            "booster": "boosters",
            "donator": 256,
            "bot_admin": 2
        }

        if rank not in ranks:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} Rank doesn't exist!")

        check = CM.get(self.bot, ranks[rank], user.id)

        if not check:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} Looks like user is not a {rank}")
        else:
            await self.bot.db.execute(f"DELETE FROM {ranks[rank]} WHERE user_id = $1", user.id)
            attr = getattr(self.bot, ranks[rank])
            attr.pop(user.id)
            rank = 'donator' if ranks[rank] == 'boosters' else 'bot_admin'
            badge = ctx.bot.settings['emojis']['ranks'][rank]
            badges = CM.get(self.bot, 'badges', user.id)
            await self.bot.db.execute("UPDATE badges SET flags = flags - $1 WHERE _id = $2", ranks[rank], user.id)
            self.bot.badges[user.id] -= ranks[rank]
            try:
                dm_message = f"Hey {user}! Just letting you know your rank was updated and you're not a **{rank}** anymore!"
                await user.send(dm_message)
                conf_msg = ' Sent them a DM as well.'
            except Exception:
                conf_msg = ' Was unable to send them a DM.'
                pass
            await ctx.send(f"{badge} **{user}**'s rank was updated and is not a {rank} anymore.{conf_msg} *Also remove their role*")

    @dev.command(brief='Force leave the server', aliases=['fl', 'force', 'fleave'], name='forceleave')
    async def dev_force_leave(self, ctx, server: int, reason: str):
        guild = self.bot.get_guild(server)

        if guild is None:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} I can't leave that server as I'm not in it.")

        elif guild:
            e = discord.Embed(color=self.bot.settings['colors']['deny_color'], timestamp=datetime.now(timezone.utc))
            e.set_author(name="Left guild forcefully", icon_url=guild.icon_url)
            e.description = f"""
Hey {guild.owner}!
Just wanted to let you know that **{ctx.author}** made me forcefully leave your server: {guild.name} ({guild.id}) with a reason: **{reason}**

If you think that this is a mistake, you may join the [support server]({self.bot.support}) and open a support ticket.
If you'll invite me to that server again without sorting this forceful leave or getting a DM from me that it was a mistake, my owners have full right to execute this leave again.
If this will get out of control blacklist will be issued."""
            msg = ''
            try:
                await guild.owner.send(embed=e)
                msg += f' and DMed the server owner ({guild.owner} ({guild.owner.id}))'
            except Exception:
                msg += '. Unfortunately I failed to DM the owner of that server'
            await guild.leave()
            await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} Successfully left the server{msg}.")
        else:
            return

    @dev.group(name='error', aliases=['err'], invoke_without_command=True)
    async def dev_error(self, ctx):
        await ctx.send_help(ctx.command)

    @dev_error.command(name='fix-error', aliases=['fixerror', 'errfix', 'fixerr', 'fix'])
    async def dev_fix_error(self, ctx, *, error_ids: str):

        fixed = []
        already_fixed = []
        not_found = []
        not_number = []
        error_ids = error_ids.split(' ')
        for error_id in error_ids:
            if not error_id.isdigit():
                not_number.append(error_id)
                continue
            error_id = int(error_id)
            command = await self.bot.db.fetch("SELECT error_command, error_status FROM errors WHERE error_id = $1 ORDER BY error_occured", error_id)

            if command != [] and command[0]['error_status'] == 0:
                await self.bot.db.execute("UPDATE errors SET error_status = $1 WHERE error_command = $2 AND error_id = $3", 1, str(command[0]['error_command']), error_id)
                fixed.append(str(error_id))
                continue
            elif command != [] and command[0]['error_status'] == 1:
                already_fixed.append(str(error_id))
                continue
            elif command == []:
                not_found.append(str(error_id))

        await ctx.channel.send(f"**Fixed:** {', '.join(fixed)}\n**Already were fixed:** {', '.join(already_fixed)}\n**Not found:** {', '.join(not_found)}\n**Not a number:** {', '.join(not_number)}")

    @dev_error.command(name='show-error', aliases=['show'])
    async def dev_error_show(self, ctx, error_id: int):
        """
        Check the error's output
        """
        query = "SELECT DISTINCT error_command, error_msg, error_occured, error_jump, error_status, ROW_NUMBER() OVER (ORDER BY error_occured) FROM errors ORDER BY error_occured"
        errors = await self.bot.db.fetch(query)

        if error_id not in [t['row_number'] for t in errors]:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} Error **#{error_id}** doesn't exist yet.")
        else:
            e = discord.Embed(color=self.bot.settings['colors']['embed_color'])
            e.title = f"Error ID {error_id}"
            e.description = f"```py\n{errors[error_id-1]['error_msg']}```"
            e.add_field(name='Error information:', value=(f"**Error status:** {f'Resolved' if errors[error_id-1]['error_status'] == 1 else 'Unresolved'}\n"
                                                          f"**Error occured:** {default.human_timedelta(errors[error_id-1]['error_occured'], source=datetime.now())}\n"
                                                          f"**Error command:** {errors[error_id-1]['error_command']}"))
            await ctx.send(embed=e)

    @dev_error.command(name='list', aliases=['l'])
    async def dev_error_list(self, ctx):

        resolved = await self.bot.db.fetch('SELECT array_agg(error_id), count(*) FROM errors WHERE error_status = $1', 1)
        unresolved = await self.bot.db.fetch('SELECT array_agg(error_id), count(*) FROM errors WHERE error_status = $1', 0)

        e = discord.Embed(color=self.bot.settings['colors']['embed_color'],
                          title='List of all the errors')

        list1 = []
        for err in resolved[0]['array_agg']:
            list1.append(f"{err}")
        list2 = []
        if unresolved[0]['array_agg']:
            for errs in unresolved[0]['array_agg']:
                list2.append(f"{errs}")
        e.add_field(name='Resolved errors:', value=", ".join(list1))
        if list2 != []:
            e.add_field(name='Unresolved errors:', value=", ".join(list2), inline=False)
        await ctx.send(embed=e)


def setup(bot):
    bot.add_cog(owner(bot))
