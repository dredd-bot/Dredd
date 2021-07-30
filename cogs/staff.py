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
import json

from discord.ext import commands

from utils import checks, default, publicflags
from db.cache import CacheManager as CM
from datetime import datetime, timezone
from utils.checks import admin_only


class staff(commands.Cog, name="Staff"):

    def __init__(self, bot):
        self.bot = bot
        self.help_icon = "<:staff:706190137058525235>"
        self.big_icon = "https://cdn.discordapp.com/emojis/706190137058525235.png?v=1"
        self._last_result = None

    async def cog_check(self, ctx: commands.Context):
        if not await ctx.bot.is_admin(ctx.author):
            raise admin_only()
        return True

    @commands.group(brief="Main staff commands", invoke_without_command=True)
    async def admin(self, ctx):
        """ Bot staff commands.
        Used to manage bot stuff."""

        await ctx.send_help(ctx.command)

    @commands.group(name='blacklist', invoke_without_command=True, aliases=['bl'])
    async def blacklist(self, ctx):
        """ Manage bot's blacklist """
        await ctx.send_help(ctx.command)

    @blacklist.group(name='add', invoke_without_command=True, aliases=['a'])
    async def blacklist_add(self, ctx):
        await ctx.send_help(ctx.command)

    @blacklist.group(name='remove', invoke_without_command=True, aliases=['r'])
    async def blacklist_remove(self, ctx):
        await ctx.send_help(ctx.command)

    @blacklist_add.command(name='user', aliases=['u', 'users', 'member'])
    async def blacklist_add_user(self, ctx, user: discord.User, liftable: int = 0, *, reason: str):
        """ Add user to bot's blacklist
        liftable values:
        0 - liftable
        1 - not liftable"""
        if await self.bot.is_admin(user) and not await self.bot.is_owner(ctx.author):
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | You cannot blacklist {user} because they're a part of bot staff team.")
        bslash = '\n\n'
        apply = f"{f'{bslash}If you wish to appeal, you can [join the support server]({self.bot.support})' if liftable == 0 else ''}"
        check = CM.get(self.bot, 'blacklist', user.id)

        if check and check['type'] == 2:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | **{user}** is already in my blacklist.")
        elif not check or check and check['type'] != 2:
            query = """INSERT INTO blacklist(_id, type, reason, dev, issued, liftable)
                        VALUES($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (_id) DO UPDATE
                        SET type = $2, reason = $3
                        WHERE blacklist._id = $1 """
            await self.bot.db.execute(query, user.id, 2, reason, ctx.author.id, datetime.now(), liftable)
            self.bot.blacklist[user.id] = {'type': 2, 'reason': reason, 'dev': ctx.author.id, 'issued': datetime.now(), 'liftable': liftable}
            badge = self.bot.settings['emojis']['ranks']['blocked']
            await self.bot.db.execute("INSERT INTO badges(_id, flags) VALUES($1, $2)", user.id, 2048)
            self.bot.badges[user.id] = 2048
            await self.bot.db.execute("INSERT INTO bot_history(_id, action, dev, reason, issued, type, liftable) VALUES($1, $2, $3, $4, $5, $6, $7)", user.id, 1, ctx.author.id, reason, datetime.now(), 2, liftable)
            e = discord.Embed(color=self.bot.settings['colors']['deny_color'], title='Blacklist state updated!', timestamp=datetime.now(timezone.utc))
            e.set_author(name=user, icon_url=user.avatar_url)
            e.description = f"Hey!\nI'm sorry, but your blacklist state was updated and you won't be able to use my commands anymore!\n**Reason:** {reason}{apply}"
            try:
                await user.send(embed=e)
                msg = ' and DMed them.'
            except Exception as e:
                msg = f', however error occured while DMing them: {e}'
            await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | I've successfully added **{user}** to the blacklist{msg}")
            await default.blacklist_log(ctx, 0, 0, user, reason)

    @blacklist_add.command(name='server', aliases=['s', 'g', 'guild'])
    async def blacklist_add_server(self, ctx, server: int, liftable: int = 0, *, reason: str):
        """ Add server to bot's blacklist
        liftable values:
        0 - liftable
        1 - not liftable"""
        if await self.bot.db.fetchval("SELECT _id FROM noblack WHERE _id = $1", server):
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | That server is whitelisted and cannot be blacklisted by bot admins.")
        guild = self.bot.get_guild(server)
        if guild is None:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | I cannot find that server, make sure you have provided the correct server id!")
        bslash = '\n\n'
        apply = f"{f'{bslash}If you wish to appeal, you can [join the support server]({self.bot.support})' if liftable == 0 else ''}"
        check = CM.get(self.bot, 'blacklist', guild.id)

        if check and check['type'] == 3:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | **{guild}** is already in my blacklist.")
        elif not check or check and check['type'] != 3:
            owner = guild.owner
            await self.bot.db.execute("DELETE FROM badges WHERE _id = $1", guild.id)
            query = """INSERT INTO blacklist(_id, type, reason, dev, issued, liftable, owner_id, server_name)
                        VALUES($1, $2, $3, $4, $5, $6, $7, $8)
                        ON CONFLICT (_id) DO UPDATE
                        SET type = $2, reason = $3
                        WHERE blacklist._id = $1"""
            await self.bot.db.execute(query, guild.id, 3, reason, ctx.author.id, datetime.now(), liftable, owner.id, guild.name)
            self.bot.blacklist[guild.id] = {'type': 3, 'reason': reason, 'dev': ctx.author.id, 'issued': datetime.now(), 'liftable': liftable, 'owner_id': owner.id, 'server_name': guild.name}
            await self.bot.db.execute("INSERT INTO bot_history(_id, action, dev, reason, issued, type, liftable) VALUES($1, $2, $3, $4, $5, $6, $7)", server, 1, ctx.author.id, reason, datetime.now(), 3, liftable)
            e = discord.Embed(color=self.bot.settings['colors']['deny_color'], title='Blacklist state updated!', timestamp=datetime.now(timezone.utc))
            e.set_author(name=owner, icon_url=owner.avatar_url)
            e.description = f"Hey!\nI'm sorry, but your server's ({guild.name}) blacklist state was updated and you won't be able to invite me to that server!\n**Reason:** {reason}{apply}"
            try:
                await owner.send(embed=e)
                msg = ' and DMed the owner of the server.'
            except Exception as e:
                msg = f', however error occured while DMing the owner of the server: {e}'
            await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | I've successfully added **{guild}** to the blacklist{msg}")
            await guild.leave()
            await default.blacklist_log(ctx, 0, 0, guild, reason)

    @blacklist_add.command(name='suggestions', aliases=['sug'])
    async def blacklist_add_suggestions(self, ctx, server: int, *, reason: str):
        """
        Blacklist server from submitting suggestions
        """
        to_block = self.bot.get_guild(server)

        if not to_block:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} Can't find server with this ID!")

        if await self.bot.db.fetchval("SELECT _id FROM noblack WHERE _id = $1", to_block) and not await ctx.bot.is_owner(ctx.author):
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | That server is whitelisted and cannot be blacklisted by bot admins.")

        check = CM.get(self.bot, 'blacklist', to_block.id)
        if check and check['type'] == 0:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | **{to_block}** is already in my suggestions blacklist.")
        elif check and check['type'] == 3:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | **{to_block}** is blacklisted, you shouldn't even be seeing this message though :/")
        elif not check:
            query = "INSERT INTO blacklist(_id, type, reason, dev, issued, liftable, owner_id, server_name) VALUES($1, $2, $3, $4, $5, $6, $7, $8)"
            query2 = "INSERT INTO bot_history(_id, action, dev, reason, issued, type, liftable) VALUES($1, $2, $3, $4, $5, $6, $7)"
            await self.bot.db.execute(query, to_block.id, 0, reason, ctx.author.id, datetime.now(), 0, to_block.owner.id, to_block.name)
            await self.bot.db.execute(query2, to_block.id, 1, ctx.author.id, reason, datetime.now(), 0, 0)
            self.bot.blacklist[to_block.id] = {'type': 0, 'reason': reason, 'dev': ctx.author.id, 'issued': datetime.now(), 'liftable': 0, 'owner_id': to_block.owner.id, 'server_name': to_block.name}
            await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | I've successfully added **{to_block}** to the suggestions blacklist.")
            await default.blacklist_log(ctx, 0, 1, to_block, reason)

    @blacklist_add.command(name='direct', aliases=['dms'])
    async def blacklist_add_direct(self, ctx, user: discord.User, *, reason: str):
        """
        Blacklist user from sending DMs
        """

        if await ctx.bot.is_admin(user) and not await ctx.bot.is_owner(ctx.author):
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | You cannot blacklist {user} because they're a part of bot staff team.")

        check = CM.get(self.bot, 'blacklist', user.id)

        if check and check['type'] == 2:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} That user is already blacklisted from using my commands.")
        elif check and check['type'] == 1:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} That user is already blacklisted from sending DMs to me.")
        elif not check:
            query1 = "INSERT INTO blacklist(_id, type, reason, dev, issued, liftable) VALUES($1, $2, $3, $4, $5, $6)"
            query2 = "INSERT INTO bot_history(_id, action, dev, reason, issued, type, liftable) VALUES($1, $2, $3, $4, $5, $6, $7)"
            await self.bot.db.execute(query1, user.id, 1, reason, ctx.author.id, datetime.now(), 0)
            await self.bot.db.execute(query2, user.id, 1, ctx.author.id, reason, datetime.now(), 1, 0)
            self.bot.blacklist[user.id] = {'type': 1, 'reason': reason, 'dev': ctx.author.id, 'issued': datetime.now(), 'liftable': 0}
            await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | I've successfully added **{user}** to the DMs blacklist.")
            await default.blacklist_log(ctx, 0, 2, user, reason)

    @blacklist_remove.command(name='user', aliases=['u', 'users', 'member'])
    async def blacklist_remove_user(self, ctx, user: discord.User, *, reason: str):
        """ Remove user from the blacklist """
        check = CM.get(self.bot, 'blacklist', user.id)

        if check and check['type'] == 2:
            if check['liftable'] != 0 and not await ctx.bot.is_owner(ctx.author):
                return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | This user cannot be unblacklisted!")
            await self.bot.db.execute("DELETE FROM blacklist WHERE _id = $1", user.id)
            self.bot.blacklist.pop(user.id)
            await self.bot.db.execute("DELETE FROM badges WHERE _id = $1", user.id)
            self.bot.badges.pop(user.id)
            e = discord.Embed(color=self.bot.settings['colors']['approve_color'], title='Blacklist state updated!', timestamp=datetime.now(timezone.utc))
            e.set_author(name=user, icon_url=user.avatar_url)
            e.description = f"Hey!\nJust wanted to let you know that your blacklist state was updated and you'll be able to use my commands again!\n**Reason:** {reason}"
            try:
                await user.send(embed=e)
                msg = ' and DMed them.'
            except Exception as e:
                msg = f', however error occured while DMing them: {e}'
            await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | I've successfully removed **{user}** from the blacklist{msg}")
            await default.blacklist_log(ctx, 1, 0, user, reason)
        elif check and check['type'] == 1:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | **{user}** is blacklisted from sending DMs, only Moksej is allowed to unblacklist them.")
        elif not check:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | **{user}** is not in my blacklist.")

    @blacklist_remove.command(name='server', aliases=['s', 'g', 'guild'])
    async def blacklist_remove_server(self, ctx, server: int, *, reason: str):
        """ Remove user from the blacklist """
        check = CM.get(self.bot, 'blacklist', server)

        if check and check['type'] == 3:
            if check['liftable'] != 0 and not await ctx.bot.is_owner(ctx.author):
                return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | This server cannot be unblacklisted!")
            await self.bot.db.execute("DELETE FROM blacklist WHERE _id = $1", server)
            self.bot.blacklist.pop(server)
            e = discord.Embed(color=self.bot.settings['colors']['approve_color'], title='Blacklist state updated!', timestamp=datetime.now(timezone.utc))
            e.description = f"Hey!\nJust wanted to let you know that your server ({check['server_name']}) is now unblacklisted and you'll be able to invite me there!\n**Reason:** {reason}"
            try:
                user = self.bot.get_user(check['owner_id'])
                e.set_author(name=user, icon_url=user.avatar_url)
                await user.send(embed=e)
                msg = ' and DMed the server owner.'
            except Exception as e:
                msg = f', however error occured while DMing the server owner: {e}'
            await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | I've successfully removed **{check['server_name']}** from the blacklist{msg}")
            await default.blacklist_log(ctx, 1, 0, server, reason)
        elif check and check['type'] == 0:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | **{server}** is blacklisted from submitting suggestions, you're using the wrong command")
        elif not check:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | **{server}** is not in my blacklist.")

    @blacklist_remove.command(name='suggestions', aliases=['sug'])
    async def blacklist_remove_suggestions(self, ctx, server: int, *, reason: str):
        """
        Unblacklist server from submitting suggestions
        """

        check = CM.get(self.bot, 'blacklist', server)

        if check and check['type'] == 3:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} Server seems to be blacklisted from inviting me.")
        elif check and check['type'] == 0:
            query = "DELETE FROM blacklist WHERE _id = $1"
            await self.bot.db.execute(query, server)
            self.bot.blacklist.pop(server)
            await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} I've successfully unblacklisted **{check['server_name']}** ({server}) from submitting suggestions")
            await default.blacklist_log(ctx, 1, 1, self.bot.get_guild(server), reason)
        elif not check:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} Server doesn't seem to be blacklisted from anything.")

    @admin.command(name='disable-command', aliases=['discmd', 'disablecmd'])
    async def admin_disable_command(self, ctx, command: str, *, reason: str):

        command = self.bot.get_command(command)
        cant_disable = ['jsk', 'dev', 'admin', 'theme', 'help']

        if not command:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | `{command}` doesn\'t exist.")

        elif command in cant_disable or command.parent in cant_disable:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | `{command}` can't be disabled.")

        else:
            if command.parent:
                if await checks.is_disabled(ctx, command):
                    return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | `{command}` is already disabled.")
                else:
                    if not command.name:
                        self.bot.disabled_commands[str(command.parent)] = {'reason': reason, 'dev': ctx.author.id}
                        await self.bot.db.execute("INSERT INTO discmds(command, reason, dev) VALUES($1, $2, $3)", str(command.parent), reason, ctx.author.id)
                        await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command.parent}` and its corresponding subcommands were successfully disabled for {reason}")
                    elif command.name:
                        self.bot.disabled_commands[str(f"{command.parent} {command.name}")] = {'reason': reason, 'dev': ctx.author.id}
                        await self.bot.db.execute("INSERT INTO discmds(command, reason, dev) VALUES($1, $2, $3)", str(f"{command.parent} {command.name}"), reason, ctx.author.id)
                        await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command.parent} {command.name}` and its corresponding subcommands were successfully disabled for {reason}")
            elif not command.parent:
                if await checks.is_disabled(ctx, command):
                    return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | `{command}` is already disabled.")
                else:
                    self.bot.disabled_commands[str(command)] = {'reason': reason, 'dev': ctx.author.id}
                    await self.bot.db.execute("INSERT INTO discmds(command, reason, dev) VALUES($1, $2, $3)", str(command), reason, ctx.author.id)
                    await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command}` was successfully disabled for {reason}")

    @admin.command(name='enable-command', aliases=['enbcmd', 'enablecmd'])
    async def enable_command(self, ctx, *, cmd: str):

        command = self.bot.get_command(cmd)

        if not command:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | `{cmd}` doesn\'t exist.")

        else:
            if command.parent:
                if not await checks.is_disabled(ctx, command):
                    return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | `{command}` is not disabled.")
                else:
                    if not command.name:
                        self.bot.disabled_commands.pop(str(command.parent))
                        await self.bot.db.execute("DELETE FROM discmds WHERE command = $1", str(command.parent))
                        await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command.parent}` and its corresponding subcommands were successfully re-enabled")
                    elif command.name:
                        self.bot.disabled_commands.pop(str(f"{command.parent} {command.name}"))
                        await self.bot.db.execute("DELETE FROM discmds WHERE command = $1", str(f"{command.parent} {command.name}"))
                        await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command.parent} {command.name}` and its corresponding subcommands were successfully re-enabled")
            elif not command.parent:
                if not await checks.is_disabled(ctx, command):
                    return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | `{command}` is not disabled.")
                else:
                    self.bot.disabled_commands.pop(str(command))
                    await self.bot.db.execute("DELETE FROM discmds WHERE command = $1", str(command))
                    await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command}` was successfully re-enabled")

    @commands.group(name='add-badge', invoke_without_command=True, aliases=['addbadge', 'abadge'])
    async def addbadge(self, ctx):
        await ctx.send_help(ctx.command)

    @commands.group(name='remove-badge', invoke_without_command=True, aliases=['removebadge', 'rbadge'])
    async def removebadge(self, ctx):
        await ctx.send_help(ctx.command)

    @addbadge.command(name='user', aliases=['u'])
    async def addbadge_user(self, ctx, user: typing.Union[discord.User, str], badge: str):

        user = await default.find_user(ctx, user)

        if not user:
            return await ctx.send(f"{ctx.bot.settings['emojis']['misc']['warn']} | User could not be found")

        attr = getattr(self.bot, 'settings')
        try:
            attr['emojis']['ranks'][badge]
        except Exception as e:
            e = discord.Embed(color=self.bot.settings['colors']['deny_color'], title='Invalid badge')
            badges = 'Those are the valid ones:\n'
            for badge in attr['emojis']['ranks']:
                badges += f'`{badge}`, '
            e.description = badges[:-2]
            return await ctx.send(embed=e)
        badges = CM.get(self.bot, 'badges', user.id)

        if getattr(publicflags.BotFlags(badges if badges else 0), badge):
            return await ctx.send(f"**{user}** already has {attr['emojis']['ranks'][badge]} badge")
        else:
            badge_value = default.badge_values(ctx)
            if badges:
                self.bot.badges[user.id] += badge_value[badge]
                await self.bot.db.execute("UPDATE badges SET flags = flags + $1 WHERE _id = $2", badge_value[badge], user.id)
            else:
                self.bot.badges[user.id] = badge_value[badge]
                await self.bot.db.execute("INSERT INTO badges(_id, flags) VALUES($1, $2)", user.id, badge_value[badge])
            await ctx.send(f"Added {attr['emojis']['ranks'][badge]} to {user} badges")

    @removebadge.command(name='user', aliases=['u'])
    async def removebadge_user(self, ctx, user: typing.Union[discord.User, str], badge: str):
        user = await default.find_user(ctx, user)

        if not user:
            return await ctx.send(f"{ctx.bot.settings['emojis']['misc']['warn']} | User could not be found")

        attr = getattr(self.bot, 'settings')
        try:
            attr['emojis']['ranks'][badge]
        except Exception as e:
            e = discord.Embed(color=self.bot.settings['colors']['deny_color'], title='Invalid badge')
            badges = 'Those are the valid ones:\n'
            for badge in attr['emojis']['ranks']:
                badges += f'`{badge}`, '
            e.description = badges[:-2]
            return await ctx.send(embed=e)
        badges = CM.get(self.bot, 'badges', user.id)

        if not getattr(publicflags.BotFlags(badges if badges else 0), badge):
            return await ctx.send(f"**{user}** doesn't have {attr['emojis']['ranks'][badge]} badge")
        else:
            badge_value = default.badge_values(ctx)
            self.bot.badges[user.id] -= badge_value[badge]
            await self.bot.db.execute("UPDATE badges SET flags = flags - $1 WHERE _id = $2", badge_value[badge], user.id)
            await ctx.send(f"Removed {attr['emojis']['ranks'][badge]} from {user} badges")

    @addbadge.command(name='server', aliases=['s'])
    async def addbadge_server(self, ctx, server: int, badge: str):
        guild = self.bot.get_guild(server)

        if not guild:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | Server not found")

        attr = getattr(self.bot, 'settings')
        try:
            attr['emojis']['ranks'][badge]
        except Exception as e:
            e = discord.Embed(color=self.bot.settings['colors']['deny_color'], title='Invalid badge')
            badges = 'Those are the valid ones:\n'
            for badge in attr['emojis']['ranks']:
                badges += f'`{badge}`, '
            e.description = badges[:-2]
            return await ctx.send(embed=e)
        badges = CM.get(self.bot, 'badges', guild.id)

        if getattr(publicflags.BotFlags(badges if badges else 0), badge):
            return await ctx.send(f"**{guild}** already has {attr['emojis']['ranks'][badge]}")
        else:
            badge_value = default.badge_values(ctx)
            if badges:
                self.bot.badges[guild.id] += badge_value[badge]
                await self.bot.db.execute("UPDATE badges SET flags = flags + $1 WHERE _id = $2", badge_value[badge], guild.id)
            else:
                self.bot.badges[guild.id] = badge_value[badge]
                await self.bot.db.execute("INSERT INTO badges(_id, flags) VALUES($1, $2)", guild.id, badge_value[badge])
            await ctx.send(f"Added {attr['emojis']['ranks'][badge]} to {guild} badges")

    @removebadge.command(name='server', aliases=['s'])
    async def removebadge_server(self, ctx, server: int, badge: str):
        guild = self.bot.get_guild(server)

        if not guild:
            return await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | Server not found")

        attr = getattr(self.bot, 'settings')
        try:
            attr['emojis']['ranks'][badge]
        except Exception as e:
            e = discord.Embed(color=self.bot.settings['colors']['deny_color'], title='Invalid badge')
            badges = 'Those are the valid ones:\n'
            for badge in attr['emojis']['ranks']:
                badges += f'`{badge}`, '
            e.description = badges[:-2]
            return await ctx.send(embed=e)
        badges = CM.get(self.bot, 'badges', guild.id)

        if not getattr(publicflags.BotFlags(badges if badges else 0), badge):
            return await ctx.send(f"**{guild}** doesn't have {attr['emojis']['ranks'][badge]} badge")
        else:
            badge_value = default.badge_values(ctx)
            self.bot.badges[guild.id] -= badge_value[badge]
            await self.bot.db.execute("UPDATE badges SET flags = flags - $1 WHERE _id = $2", badge_value[badge], guild.id)
            await ctx.send(f"Removed {attr['emojis']['ranks'][badge]} from {guild} badges")

    @commands.command(brief='Approve the suggestion', aliases=['approve'])
    @checks.is_guild(709521003759403063)
    async def suggestapprove(self, ctx, suggestion_id: str, *, reason: commands.clean_content):
        """ Approve the suggestion """
        try:
            await ctx.message.delete()
        except Exception:
            pass
        if not suggestion_id.isdigit():
            return await ctx.author.send(f"{self.bot.settings['emojis']['misc']['red-mark']} | You provided invalid suggestion id. It has to be a digit.")

        suggestion = await self.bot.db.fetch("SELECT * FROM suggestions WHERE suggestion_id = $1 AND status = $2", int(suggestion_id), 0)

        if not suggestion:
            return await ctx.author.send(f"{self.bot.settings['emojis']['misc']['red-mark']} | That suggestion doesn't seem to exist or is already approved/denied.")

        user = await self.bot.fetch_user(suggestion[0]['user_id'])
        suggestion_content = f"{suggestion[0]['suggestion']}"
        suggestion_message = suggestion[0]['msg_id']

        message = await self.bot.get_guild(self.bot.settings['servers']['main']).get_channel(self.bot.settings['channels']['suggestions']).fetch_message(suggestion_message)
        embed = message.embeds[0]

        await self.bot.db.execute("INSERT INTO todos(user_id, todo, time, jump_url) VALUES($1, $2, $3, $4)", 345457928972533773, suggestion_content, datetime.now(), message.jump_url)
        embed.color = self.bot.settings['colors']['approve_color']
        embed.add_field(name="Approval note:", value=reason, inline=False)
        embed.set_footer(text=f"Suggestion was approved by {ctx.author}")
        await message.clear_reactions()
        await message.edit(embed=embed)

        await self.bot.db.execute("UPDATE suggestions SET status = $1, reason = $2 WHERE user_id = $3 AND suggestion_id = $4", 1, reason, user.id, int(suggestion_id))
        trackers = await self.bot.db.fetch("SELECT user_id FROM track_suggestions WHERE _id = $1", int(suggestion_id))
        for res in trackers:
            e = discord.Embed(color=self.bot.settings['colors']['approve_color'], description=f"The following suggestion was approved by {ctx.author}\n**Approval note:** {reason}\n\n**Suggestion:**\n>>> {suggestion_content}")
            e.set_author(name=f"Suggested by {user} | #{suggestion_id}", icon_url=user.avatar_url)
            e.set_footer(text="You're either an author of this suggestion or you're following this suggestion's status")
            user = self.bot.get_user(res['user_id'])
            try:
                # await self.bot.db.execute("DELETE FROM track_suggestions WHERE user_id = $1 AND _id = $2", user.id, int(suggestion_id))
                await user.send(embed=e)
            except Exception as e:
                pass

    @commands.command(brief='Deny the suggestion', aliases=['deny'])
    @checks.is_guild(709521003759403063)
    async def suggestdeny(self, ctx, suggestion_id: str, *, reason: commands.clean_content):
        """ Deny the suggestion """
        try:
            await ctx.message.delete()
        except Exception:
            pass
        if not suggestion_id.isdigit():
            return await ctx.author.send(f"{self.bot.settings['emojis']['misc']['red-mark']} | You provided invalid suggestion id. It has to be a digit.")

        suggestion = await self.bot.db.fetch("SELECT * FROM suggestions WHERE suggestion_id = $1 AND status = $2", int(suggestion_id), 0)

        if not suggestion:
            return await ctx.author.send(f"{self.bot.settings['emojis']['misc']['red-mark']} | That suggestion doesn't seem to exist or is already approved/denied.")

        user = await self.bot.fetch_user(suggestion[0]['user_id'])
        suggestion_content = f"{suggestion[0]['suggestion']}"
        suggestion_message = suggestion[0]['msg_id']

        message = await self.bot.get_guild(self.bot.settings['servers']['main']).get_channel(self.bot.settings['channels']['suggestions']).fetch_message(suggestion_message)
        embed = message.embeds[0]

        embed.color = self.bot.settings['colors']['deny_color']
        embed.add_field(name="Denial note:", value=reason, inline=False)
        embed.set_footer(text=f"Suggestion was denied by {ctx.author}")
        await message.clear_reactions()
        await message.edit(embed=embed)

        await self.bot.db.execute("UPDATE suggestions SET status = $1, reason = $2 WHERE user_id = $3 AND suggestion_id = $4", 1, reason, user.id, int(suggestion_id))
        trackers = await self.bot.db.fetch("SELECT user_id FROM track_suggestions WHERE _id = $1", int(suggestion_id))
        for res in trackers:
            e = discord.Embed(color=self.bot.settings['colors']['deny_color'], description=f"The following suggestion was denied by {ctx.author}\n**Denial note:** {reason}\n\n**Suggestion:**\n>>> {suggestion_content}")
            e.set_author(name=f"Suggested by {user} | #{suggestion_id}", icon_url=user.avatar_url)
            e.set_footer(text="You're either an author of this suggestion or you're following this suggestion's status")
            user = self.bot.get_user(res['user_id'])
            try:
                await self.bot.db.execute("DELETE FROM track_suggestions WHERE user_id = $1 AND _id = $2", user.id, int(suggestion_id))
                await user.send(embed=e)
            except Exception as e:
                pass

    @commands.command(brief='Deny the suggestion', aliases=['sdelete'])
    @checks.is_guild(709521003759403063)
    async def suggestdelete(self, ctx, suggestion_id: str, *, reason: commands.clean_content):
        """ Deny the suggestion """
        try:
            await ctx.message.delete()
        except Exception:
            pass
        if not suggestion_id.isdigit():
            return await ctx.author.send(f"{self.bot.settings['emojis']['misc']['red-mark']} | You provided invalid suggestion id. It has to be a digit.")

        suggestion = await self.bot.db.fetch("SELECT * FROM suggestions WHERE suggestion_id = $1 AND status = $2", int(suggestion_id), 0)

        if not suggestion:
            return await ctx.author.send(f"{self.bot.settings['emojis']['misc']['red-mark']} | That suggestion doesn't seem to exist or is already approved/denied.")

        user = await self.bot.fetch_user(suggestion[0]['user_id'])
        suggestion_content = f"{suggestion[0]['suggestion']}"
        suggestion_message = suggestion[0]['msg_id']

        message = await self.bot.get_guild(self.bot.settings['servers']['main']).get_channel(self.bot.settings['channels']['suggestions']).fetch_message(suggestion_message)
        await message.delete()

        await self.bot.db.execute("DELETE FROM suggestions WHERE suggestion_id = $1", int(suggestion_id))
        trackers = await self.bot.db.fetch("SELECT user_id FROM track_suggestions WHERE _id = $1", int(suggestion_id))
        for res in trackers:
            e = discord.Embed(color=self.bot.settings['colors']['error_color'], description=f"The following suggestion was deleted by {ctx.author}\n**Delete note:** {reason}\n\n**Suggestion:**\n>>> {suggestion_content}")
            e.set_author(name=f"Suggested by {user} | #{suggestion_id}", icon_url=user.avatar_url)
            e.set_footer(text="You're either an author of this suggestion or you're following this suggestion's status")
            user = self.bot.get_user(res['user_id'])
            try:
                await self.bot.db.execute("DELETE FROM track_suggestions WHERE user_id = $1 AND _id = $2", user.id, int(suggestion_id))
                await user.send(embed=e)
            except Exception as e:
                pass

    @commands.command(brief='Mark suggestion as done', aliases=['sdone'])
    @checks.is_guild(709521003759403063)
    async def suggestdone(self, ctx, suggestion_id: str, *, note: commands.clean_content = None):
        """ Mark suggestion as done. """

        try:
            await ctx.message.delete()
        except Exception:
            pass
        if not suggestion_id.isdigit():
            return await ctx.author.send(f"{self.bot.settings['emojis']['misc']['red-mark']} | You provided invalid suggestion id. It has to be a digit.")

        suggestion = await self.bot.db.fetch("SELECT * FROM suggestions WHERE suggestion_id = $1 AND status != $2", int(suggestion_id), 2)

        if not suggestion:
            return await ctx.author.send(f"{self.bot.settings['emojis']['misc']['red-mark']} | That suggestion doesn't seem to exist or is already implemented")

        user = await self.bot.fetch_user(suggestion[0]['user_id'])
        suggestion_content = f"{suggestion[0]['suggestion']}"
        suggestion_message = suggestion[0]['msg_id']

        message = await self.bot.get_guild(self.bot.settings['servers']['main']).get_channel(self.bot.settings['channels']['suggestions']).fetch_message(suggestion_message)
        embed = message.embeds[0]

        await self.bot.db.execute("DELETE FROM todos WHERE user_id = $1 AND todo = $2", 345457928972533773, suggestion_content)
        embed.color = self.bot.settings['colors']['approve_color']
        if note:
            embed.add_field(name="Note left:", value=note, inline=False)
        embed.set_footer(text=f"Suggestion was marked as done by {ctx.author}")
        await message.clear_reactions()
        await message.edit(embed=embed)

        note = note or 'No note left.'
        await self.bot.db.execute("UPDATE suggestions SET status = $1, reason = $2 WHERE user_id = $3 AND suggestion_id = $4", 2, note, user.id, int(suggestion_id))
        trackers = await self.bot.db.fetch("SELECT user_id FROM track_suggestions WHERE _id = $1", int(suggestion_id))
        for res in trackers:
            e = discord.Embed(color=self.bot.settings['colors']['approve_color'], description=f"The following suggestion was marked as done by {ctx.author}\n**Note:** {note}\n\n**Suggestion:**\n>>> {suggestion_content}")
            e.set_author(name=f"Suggested by {user} | #{suggestion_id}", icon_url=user.avatar_url)
            e.set_footer(text="You're either an author of this suggestion or you're following this suggestion's status")
            user = self.bot.get_user(res['user_id'])
            try:
                await self.bot.db.execute("DELETE FROM track_suggestions WHERE user_id = $1 AND _id = $2", user.id, int(suggestion_id))
                await user.send(embed=e)
            except Exception as e:
                pass

    @admin.command(brief="DM a user", description="Direct message an user")
    async def dm(self, ctx, id: int, msg_id: typing.Optional[int], *, msg: str):
        """ Send a DM to an user """
        try:
            await ctx.message.delete()
        except Exception as e:
            pass
        try:
            num = len(self.bot.dm)
            try:
                user = self.bot.dm[id]
            except Exception as e:
                num = num + 1
                user = self.bot.dm[num] = id
            user = self.bot.get_user(user)
            if not user:
                self.bot.dm.pop(num)
                return await ctx.author.send(f"{self.bot.settings['emojis']['misc']['warn']} User not found")
            if msg_id:
                dm_channel = user.dm_channel
                try:
                    message = await dm_channel.fetch_message(msg_id)
                except Exception:
                    await user.send(msg)
                await message.reply(msg)
                msg = f"**Reply to:** {message.content}\n\n{msg}"
            else:
                await user.send(msg)
            logchannel = self.bot.get_channel(self.bot.settings['channels']['dm'])
            logembed = discord.Embed(description=msg,
                                     color=0x81C969,
                                     timestamp=datetime.now(timezone.utc))
            logembed.set_author(name=f"I've sent a DM to {user} | #{num}", icon_url=user.avatar_url)
            logembed.set_footer(text=f"User ID: {user.id}")
            await logchannel.send(embed=logembed)
        except discord.errors.Forbidden:
            await ctx.author.send("Couldn't send message to that user. Maybe he's not in the same server with me?")
        except Exception as e:
            await ctx.author.send(e)

    @commands.command(aliases=['addtester', 'atester', 'rtester', 'removetester'])
    async def tester(self, ctx, guild_id: int):
        guild = self.bot.get_guild(guild_id)
        is_tester = CM.get(self.bot, 'testers', guild_id)
        if not guild and not is_tester:
            return await ctx.send("I'm not in that guild thus I cannot add them to the testers list.")
        elif guild and not is_tester:
            self.bot.testers[guild_id] = guild.name
            return await ctx.send(f"Added {guild} ({guild_id}) to testers list, they'll be able to use beta commands now.")
        elif guild and is_tester:
            self.bot.testers.pop(guild_id)
            return await ctx.send(f"Removed {guild} ({guild_id}) from testers list.")

    @commands.command(aliases=['radioadd', 'addradio'], brief="Add a radio station")
    async def addradiostation(self, ctx, url: str, *, name: str):

        with open("db/radio_stations.json", "r") as f:
            data = json.load(f)

        try:
            check = data[f"{name}"]
            return await ctx.send(f"Radio station {name} already exists.")
        except KeyError:
            data[f"{name}"] = url
            self.bot.radio_stations[f"{name}"] = url

        with open("db/radio_stations.json", "w") as f:
            json.dump(data, f, indent=4)
        await ctx.send(f"Added {name} to the list.")

    @commands.command(aliases=['radioremove', 'removeradio', 'remradio'], brief="Remove a radio station")
    async def removeradiostation(self, ctx, *, name: str):
        with open("db/radio_stations.json", "r") as f:
            data = json.load(f)

        try:
            data.pop(f"{name}")
            self.bot.radio_stations.pop(f"{name}")
        except KeyError:
            return await ctx.send(f"Radio station {name} doesn't exist.")

        with open("db/radio_stations.json", "w") as f:
            json.dump(data, f, indent=4)
        await ctx.send(f"Removed {name} from the list.")


def setup(bot):
    bot.add_cog(staff(bot))
