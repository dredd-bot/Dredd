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
import asyncio
import aiohttp
import re
import shlex
import argparse

from discord.ext import commands
from discord.utils import escape_markdown
from collections import Counter
from datetime import datetime

from utils import default, btime
from utils.checks import BannedMember, MemberID, moderator, admin
from utils.paginator import Pages
from db.cache import CacheManager as cm


class Arguments(argparse.ArgumentParser):
    def error(self, message):
        raise RuntimeError(message)


class moderation(commands.Cog, name='Moderation', aliases=['Mod']):
    def __init__(self, bot):
        self.bot = bot
        self.help_icon = '<:bann:747192603640070237>'
        self.big_icon = 'https://cdn.discordapp.com/emojis/747192603640070237.png?v=1'

    # async def cog_check(self, ctx):
    #     if ctx.guild is None:
    #         return False
    #     return True

    async def _basic_cleanup_strategy(self, ctx, search):
        count = 0
        async for msg in ctx.history(limit=search, before=ctx.message):
            if msg.author == ctx.me:
                await msg.delete()
                count += 1
        return {'Bot': count}

    async def _complex_cleanup_strategy(self, ctx, search):
        prefixes = self.bot.prefix[ctx.guild.id]

        def check(m):
            return m.author == ctx.me or m.content.startswith(prefixes)

        deleted = await ctx.channel.purge(limit=search, check=check, before=ctx.message)
        return Counter(m.author.display_name for m in deleted)

    async def do_removal(self, ctx, limit, predicate, *, before=None, after=None):
        if limit > 2000:
            return await ctx.send(_("{0} Limit exceeded by **{1}**").format(
                self.bot.settings['emojis']['misc']['warn'], limit - 2000
            ))

        if before is None:
            before = ctx.message
        else:
            before = discord.Object(id=before)

        if after is not None:
            after = discord.Object(id=after)

        try:
            deleted = await ctx.channel.purge(limit=limit, before=before, after=after, check=predicate)
        except discord.Forbidden as e:
            return await ctx.send(_("{0} Looks like I'm missing permissions!").format(self.bot.settings['emojis']['misc']['warn']))
        except discord.HTTPException as e:
            return await ctx.send(_("{0} Error occured!\n`{1}`").format(self.bot.settings['emojis']['misc']['warn'], e))
        except Exception as e:
            return await ctx.send(_("{0} Error occured!\n`{1}`").format(self.bot.settings['emojis']['misc']['warn'], e))

        spammers = Counter(m.author.display_name for m in deleted)
        deleted = len(deleted)
        if deleted == 1:
            messages = [_("Purged **1** message")]
        else:
            messages = [_("Purged **{0}** messages").format(deleted)]
        if deleted:
            messages.append('')
            spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
            messages.extend(f'**{name}**: {count}' for name, count in spammers)

        to_send = '\n'.join(messages)

        if len(to_send) > 2000:
            await ctx.send(_("Purged **{0}** messages").format(deleted), delete_after=10)
        else:
            message = to_send
            await ctx.send(message, delete_after=10)

    @commands.command(brief='Clean up the bot\'s messages')
    @moderator(manage_messages=True)
    @commands.cooldown(1, 5, commands.BucketType.member)
    @commands.guild_only()
    async def cleanup(self, ctx, search=100):
        """
        Cleans up the bot's messages from the channel.
        If the bot has Manage Messages permissions then it will try to delete messages that look like they invoked the bot as well.
        """

        strategy = self._basic_cleanup_strategy
        if ctx.me.permissions_in(ctx.channel).manage_messages:
            strategy = self._complex_cleanup_strategy

        spammers = await strategy(ctx, search)
        deleted = sum(spammers.values())
        messages = [_('{0} message{1} removed.').format(deleted, _(" was") if deleted == 1 else _("s were"))]
        if deleted:
            messages.append(_('\nTotal messages by user:'))
            spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
            messages.extend(f'- **{author}**: {count}' for author, count in spammers)

        await ctx.send('\n'.join(messages))

    @commands.command(brief="Change member's nickname", aliases=['setnick', 'snick', 'nickset', 'nset', 'nick'])
    @moderator(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def setnickname(self, ctx, members: commands.Greedy[discord.Member], *, new_nick: commands.clean_content = None):
        """
        Changes member's nickname in the server.
        If multiple members are provided, they all get their nicknames changed in the server.
        """

        if len(members) == 0:
            return await ctx.send(_("{0} | You're missing an argument - **members**").format(self.bot.settings['emojis']['misc']['warn']))

        if new_nick and len(new_nick) > 32:
            return await ctx.send(_("{0} Nicknames can only be 32 characters long."
                                    " You're {1} characters over.").format(self.bot.settings['emojis']['misc']['warn'], len(new_nick) - 32))

        if len(set(members)) > 10:
            return await ctx.send(_("{0} | You can only change 10 members nickname at once."))

        if len(set(members)) != 0:
            changed, failed, success, fail = [], [], 0, 0
            for member in set(members):
                if member == ctx.author:
                    failed.append(_("{0} ({1}) - **You can change your nickname by using slash commands**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                if member.top_role.position >= ctx.guild.me.top_role.position:
                    failed.append(_("{0} ({1}) - **Member is above me in the role hierarchy or has the same role**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                if member.top_role.position >= ctx.author.top_role.position:
                    failed.append(_("{0} ({1}) - **Member is above you in the role hierarchy or has the same role**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                try:
                    await member.edit(nick=new_nick, reason=f"Invoked by: {ctx.author}")
                    changed.append(f"{member.mention} ({member.id})")
                    success += 1
                except Exception as e:
                    failed.append(f"{member.mention} ({member.id}) - {e}")
                    fail += 1
                    continue
        try:
            renamed, not_renamed = "", ""
            if changed and not failed:
                renamed += _("**I've successfully re-named {0} member(s):**\n").format(success)
                for num, res in enumerate(changed, start=0):
                    renamed += f"`[{num+1}]` {res}\n"
                await ctx.send(renamed)
            if changed and failed:
                renamed += _("**I've successfully re-named {0} member(s):**\n").format(success)
                not_renamed += _("**However I failed to re-name the following {0} member(s):**\n").format(fail)
                for num, res in enumerate(changed, start=0):
                    renamed += f"`[{num+1}]` {res}\n"
                for num, res in enumerate(failed, start=0):
                    not_renamed += f"`[{num+1}]` {res}\n"
                await ctx.send(renamed + not_renamed)
            if not changed and failed:
                not_renamed += _("**I failed to re-name all the members:**\n")
                for num, res in enumerate(failed, start=0):
                    not_renamed += f"`[{num+1}]` {res}\n"
                await ctx.send(not_renamed)
        except Exception as e:
            self.bot.dispatch('silent_error', ctx, e)
            return await ctx.send(_("{0} Something failed with sending the message, "
                                    "I've sent this error to my developers and they should hopefully resolve it soon.").format(
                                        self.bot.settings['emojis']['misc']['warn']
                                    ))

    @commands.command(brief='Dehoist members')
    @moderator(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    @commands.guild_only()
    async def dehoist(self, ctx, *, nickname: str = None):
        """"""

        if nickname and len(nickname) > 32:
            return await ctx.send(_("{0} Nicknames can only be 32 characters long."
                                    " You're {1} characters over.").format(self.bot.settings['emojis']['misc']['warn'], len(new_nick) - 32))
        nickname = nickname or 'z (hoister)'

        dehoisted, failed, success_list, success, fail = [], [], [], 0, 0
        await ctx.send(_("Started dehoisting process..."))
        for member in ctx.guild.members:
            if not member.display_name[0].isalnum():
                try:
                    await member.edit(nick=nickname, reason=default.responsible(ctx.author, 'dehoisting.'))
                    dehoisted.append(f"{member.mention} ({member.id})")
                    success_list.append(member)
                    success += 1
                except discord.HTTPException:
                    failed.append(_("{0} ({1}) - **Failed to dehoist them.**"))
                    fail += 1
                    continue
                except discord.Forbidden:
                    failed.append(_("{0} ({1}) - **Looks like I'm missing permissions to dehoist them.**"))
                    fail += 1
                    continue
            else:
                continue
        if success == 0:
            return await ctx.send(_("{0} No hoisters were found.").format(self.bot.settings['emojis']['misc']['warn']))

        try:
            renamed, not_renamed = "", ""
            limit_20 = _("List is limited to 20.")
            if dehoisted and not failed:
                renamed += _("**I've successfully dehoisted {0} member(s):**\n").format(success)
                for num, res in enumerate(dehoisted[:20], start=0):
                    renamed += f"`[{num+1}]` {res}\n"
                if len(dehoisted) > 20:
                    renamed += limit_20
                await ctx.send(renamed)
                self.bot.dispatch('dehoist', ctx.guild, ctx.author, success_list)
            if dehoisted and failed:
                renamed += _("**I've successfully dehoisted {0} member(s):**\n").format(success)
                not_renamed += _("**However I failed to dehoist the following {0} member(s):**\n").format(fail)
                for num, res in enumerate(dehoisted[:10], start=0):
                    renamed += f"`[{num+1}]` {res}\n"
                for num, res in enumerate(failed[:10], start=0):
                    not_renamed += f"`[{num+1}]` {res}\n"
                message = _("List is limited to 10.")
                if len(dehoisted) > 10:
                    renamed += message
                if len(failed) > 10:
                    not_renamed += message
                await ctx.send(renamed + not_renamed)
                self.bot.dispatch('dehoist', ctx.guild, ctx.author, success_list)
            if not dehoisted and failed:
                not_renamed += _("**I failed to dehoist all the members:**\n")
                for num, res in enumerate(failed[:20], start=0):
                    not_renamed += f"`[{num+1}]` {res}\n"
                if len(failed) > 20:
                    not_renamed += limit_20
                await ctx.send(not_renamed)
        except Exception as e:
            self.bot.dispatch('silent_error', ctx, e)
            return await ctx.send(_("{0} Something failed with sending the message, "
                                    "I've sent this error to my developers and they should hopefully resolve it soon.").format(
                                        self.bot.settings['emojis']['misc']['warn']
                                    ))

    @commands.command(brief='Kick member from the server', aliases=['masskick'])
    @moderator(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def kick(self, ctx, members: commands.Greedy[discord.Member], *, reason: commands.clean_content = None):
        """
        Kick a member from the server.
        If multiple members are provided, they all get kicked from the server.
        """

        if len(members) == 0:
            return await ctx.send(_("{0} | You're missing an argument - **members**").format(
                self.bot.settings['emojis']['misc']['warn']
            ))

        reason = reason or None

        if reason and len(reason) > 450:
            return await ctx.send(_("{0} Reason can only be 450 characters long."
                                    " You're {1} characters over.").format(
                                        self.bot.settings['emojis']['misc']['warn'], len(reason) - 450
                                    ))

        if len(set(members)) > 10:
            return await ctx.send(_("{0} | You can only kick 10 members at once.").format(self.bot.settings['emojis']['misc']['warn']))

        if len(set(members)) != 0:
            kicked, failed, success_kick, success, fail = [], [], [], 0, 0
            for member in set(members):
                if member == ctx.author:
                    failed.append(_("{0} ({1}) - **You are the member though?**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                if member.top_role.position >= ctx.guild.me.top_role.position:
                    failed.append(_("{0} ({1}) - **Member is above me in the role hierarchy or has the same role**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                elif member.top_role.position >= ctx.author.top_role.position:
                    failed.append(_("{0} ({1}) - **Member is above you in the role hierarchy or has the same role**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                else:
                    try:
                        await ctx.guild.kick(member, reason=default.responsible(ctx.author, reason))
                        kicked.append(f"{member.mention} ({member.id})")
                        success += 1
                        success_kick.append(member)
                    except discord.Forbidden:
                        failed.append(_("{0} ({1}) - **Missing permissions? Do they have administrator?**").format(
                            member.mention, member.id
                        ))
                        fail += 1
                        continue
                    except discord.HTTPException:
                        failed.append(_("{0} ({1}) - **Kicking failed**").format(
                            member.mention, member.id
                        ))
                        fail += 1
                        continue
            try:
                booted, not_booted = "", ""
                if kicked and not failed:
                    booted += _("**I've successfully kicked {0} member(s):**\n").format(success)
                    for num, res in enumerate(kicked, start=0):
                        booted += f"`[{num+1}]` {res}\n"
                    await ctx.send(booted)
                    self.bot.dispatch('kick', ctx.guild, ctx.author, success_kick, reason)
                if kicked and failed:
                    booted += _("**I've successfully kicked {0} member(s):**\n").format(success)
                    not_booted += _("**However, I failed to kick the following {0} member(s):**\n").format(fail)
                    for num, res in enumerate(kicked, start=0):
                        booted += f"`[{num+1}]` {res}\n"
                    for num, res in enumerate(failed, start=0):
                        not_booted += f"`[{num+1}]` {res}\n"
                    await ctx.send(booted + not_booted)
                    self.bot.dispatch('kick', ctx.guild, ctx.author, success_kick, reason)
                if not kicked and failed:
                    not_booted += _("**I failed to kick all the members:**\n")
                    for num, res in enumerate(failed, start=0):
                        not_booted += f"`[{num+1}]` {res}\n"
                    await ctx.send(not_booted)
            except Exception as e:
                self.bot.dispatch('silent_error', ctx, e)
                return await ctx.send(_("{0} Something failed with sending the message, "
                                        "I've sent this error to my developers and they should hopefully resolve it soon.").format(
                                        self.bot.settings['emojis']['misc']['warn']
                                    ))

    @commands.command(brief='Ban member from the server', aliases=['massban', 'tempban'])
    @moderator(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def ban(self, ctx, members: commands.Greedy[discord.Member], duration: typing.Optional[btime.FutureTime], *, reason: commands.clean_content = None):
        """
        Ban a member from the server.
        If multiple members are provided, they all get banned from the server.
        """

        if len(members) == 0:
            return await ctx.send(_("{0} | You're missing an argument - **members**").format(
                self.bot.settings['emojis']['misc']['warn']
            ))

        reason = reason or None

        if reason and len(reason) > 450:
            return await ctx.send(_("{0} Reason can only be 450 characters long."
                                    " You're {1} characters over.").format(
                                        self.bot.settings['emojis']['misc']['warn'], len(reason) - 450
                                    ))

        if len(set(members)) > 10:
            return await ctx.send(_("{0} | You can only ban 10 members at once.").format(self.bot.settings['emojis']['misc']['warn']))

        if len(set(members)) != 0:
            banned, failed, success_ban, success, fail = [], [], [], 0, 0
            for member in set(members):
                if member == ctx.author:
                    failed.append(_("{0} ({1}) - **You are the member though?**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                if member.top_role.position >= ctx.guild.me.top_role.position:
                    failed.append(_("{0} ({1}) - **Member is above me in the role hierarchy or has the same role**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                elif member.top_role.position >= ctx.author.top_role.position:
                    failed.append(_("{0} ({1}) - **Member is above you in the role hierarchy or has the same role**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                else:
                    try:
                        await ctx.guild.ban(member, reason=default.responsible(ctx.author, reason), delete_message_days=0)
                        await default.execute_temporary(ctx, 2, member, ctx.author, ctx.guild, None, duration, reason)
                        banned.append(f"{member.mention} ({member.id})")
                        success += 1
                        success_ban.append(member)
                    except discord.Forbidden:
                        failed.append(_("{0} ({1}) - **Missing permissions? Do they have administrator?**").format(
                            member.mention, member.id
                        ))
                        fail += 1
                        continue
                    except discord.HTTPException:
                        failed.append(_("{0} ({1}) - **Banning failed**").format(member.mention, member.id))
                        fail += 1
                        continue
            try:
                booted, not_booted = "", ""
                if banned and not failed:
                    booted += _("**I've successfully banned {0} member(s){1}:**\n").format(success, _(' for {0}').format(btime.human_timedelta(duration.dt, source=ctx.message.created_at, suffix=None)) if duration is not None else '')
                    for num, res in enumerate(banned, start=0):
                        booted += f"`[{num+1}]` {res}\n"
                    await ctx.send(booted)
                    self.bot.dispatch('ban', ctx.guild, ctx.author, success_ban, duration if duration else None, reason, ctx.message.created_at)
                if banned and failed:
                    booted += _("**I've successfully banned {0} member(s){1}:**\n").format(success, _(' for {0}').format(btime.human_timedelta(duration.dt, source=ctx.message.created_at, suffix=None)) if duration is not None else '')
                    not_booted += _("**However, I failed to ban the following {0} member(s):**\n").format(fail)
                    for num, res in enumerate(banned, start=0):
                        booted += f"`[{num+1}]` {res}\n"
                    for num, res in enumerate(failed, start=0):
                        not_booted += f"`[{num+1}]` {res}\n"
                    await ctx.send(booted + not_booted)
                    self.bot.dispatch('ban', ctx.guild, ctx.author, success_ban, duration if duration else None, reason, ctx.message.created_at)
                if not banned and failed:
                    not_booted += _("**I failed to ban all the members:**\n")
                    for num, res in enumerate(failed, start=0):
                        not_booted += f"`[{num+1}]` {res}\n"
                    await ctx.send(not_booted)
            except Exception as e:
                self.bot.dispatch('silent_error', ctx, e)
                return await ctx.send(_("{0} Something failed with sending the message, "
                                        "I've sent this error to my developers and they should hopefully resolve it soon.").format(
                                        self.bot.settings['emojis']['misc']['warn']
                                    ))

    @commands.command(brief='Softban member from the server', aliases=['soft-ban'])
    @moderator(ban_members=True, manage_messages=True)
    @commands.guild_only()
    @commands.bot_has_permissions(ban_members=True, manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def softban(self, ctx, members: commands.Greedy[discord.Member], *, reason: commands.clean_content = None):
        """
        Soft-ban a member from the server.
        If multiple members are provided, they all get soft-banned from the server.
        """

        if len(members) == 0:
            return await ctx.send(_("{0} | You're missing an argument - **members**").format(
                self.bot.settings['emojis']['misc']['warn']
            ))

        reason = reason or None

        if reason and len(reason) > 450:
            return await ctx.send(_("{0} Reason can only be 450 characters long."
                                    " You're {1} characters over.").format(
                                        self.bot.settings['emojis']['misc']['warn'], len(reason) - 450
                                    ))

        if len(set(members)) > 10:
            return await ctx.send(_("{0} | You can only soft-ban 10 members at once.").format(self.bot.settings['emojis']['misc']['warn']))

        if len(set(members)) != 0:
            banned, failed, success_ban, success, fail = [], [], [], 0, 0
            for member in set(members):
                if member == ctx.author:
                    failed.append(_("{0} ({1}) - **You are the member though?**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                if member.top_role.position >= ctx.guild.me.top_role.position:
                    failed.append(_("{0} ({1}) - **Member is above me in the role hierarchy or has the same role**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                elif member.top_role.position >= ctx.author.top_role.position:
                    failed.append(_("{0} ({1}) - **Member is above you in the role hierarchy or has the same role**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                else:
                    try:
                        await ctx.guild.ban(member, reason=default.responsible(ctx.author, reason), delete_message_days=7)
                        await ctx.guild.unban(member, reason=default.responsible(ctx.author, reason))
                        banned.append(f"{member.mention} ({member.id})")
                        success += 1
                        success_ban.append(member)
                    except discord.Forbidden:
                        failed.append(_("{0} ({1}) - **Missing permissions? Do they have administrator?**").format(
                            member.mention, member.id
                        ))
                        fail += 1
                        continue
                    except discord.HTTPException:
                        failed.append(_("{0} ({1}) - **Banning failed**").format(member.mention, member.id))
                        fail += 1
                        continue
            try:
                booted, not_booted = "", ""
                if banned and not failed:
                    booted += _("**I've successfully soft-banned {0} member(s):**\n").format(success)
                    for num, res in enumerate(banned, start=0):
                        booted += f"`[{num+1}]` {res}\n"
                    await ctx.send(booted)
                    self.bot.dispatch('softban', ctx.guild, ctx.author, success_ban, reason)
                if banned and failed:
                    booted += _("**I've successfully soft-banned {0} member(s):**\n").format(success)
                    not_booted += _("**However, I failed to soft-ban the following {0} member(s):**\n").format(fail)
                    for num, res in enumerate(banned, start=0):
                        booted += f"`[{num+1}]` {res}\n"
                    for num, res in enumerate(failed, start=0):
                        not_booted += f"`[{num+1}]` {res}\n"
                    await ctx.send(booted + not_booted)
                    self.bot.dispatch('softban', ctx.guild, ctx.author, success_ban, reason)
                if not banned and failed:
                    not_booted += _("**I failed to soft-ban all the members:**\n")
                    for num, res in enumerate(failed, start=0):
                        not_booted += f"`[{num+1}]` {res}\n"
                    await ctx.send(not_booted)
            except Exception as e:
                self.bot.dispatch('silent_error', ctx, e)
                return await ctx.send(_("{0} Something failed with sending the message, "
                                        "I've sent this error to my developers and they should hopefully resolve it soon.").format(
                                        self.bot.settings['emojis']['misc']['warn']
                                    ))

    @commands.command(brief='Hackban user from the server', aliases=['hack-ban'])
    @moderator(ban_members=True)
    @commands.guild_only()
    @commands.has_guild_permissions(ban_members=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def hackban(self, ctx, users: commands.Greedy[MemberID], *, reason: commands.clean_content = None):
        """ Hack-ban a user from the server

        Users must be IDs else it won't work. """
        if len(set(users)) == 0:
            raise commands.MissingRequiredArgument(self.hackban.params['users'])

        if len(set(users)) > 20:
            return await ctx.send(_("{0} | You can only hack-ban 20 users at once.").format(self.bot.settings['emojis']['misc']['warn']))

        reason = reason or None

        if reason and len(reason) > 450:
            return await ctx.send(_("{0} Reason can only be 450 characters long."
                                    " You're {1} characters over.").format(
                                        self.bot.settings['emojis']['misc']['warn'], len(reason) - 400
                                    ))

        failed, success, fail_count, suc_count, banned = [], [], 0, 0, []
        await ctx.send(_("Starting the process, this might take a while."))
        for user in set(users):
            try:
                m = await commands.MemberConverter().convert(ctx, str(user))
                if m is not None:
                    failed.append(_("{0} ({0.id}) - **User is in this server, use `ban` command instead.**").format(m))
                    fail_count += 1
                    continue
            except Exception:
                pass
            try:
                user = await self.bot.try_user(user)
            except Exception:
                failed.append(_("{0} User doesn't seem to exist, are you sure the ID is correct?").format(user))
                fail_count += 1
                continue
            reason = _('No reason provided.') if reason is None else reason
            await ctx.guild.ban(user, reason=default.responsible(ctx.author, reason), delete_message_days=0)
            success.append(_("{0} ({0.id})").format(user))
            banned.append(user)
            suc_count += 1

        try:
            booted, not_booted = "", ""
            if success and not failed:
                booted += _("**I've successfully hack-banned {0} member(s):**\n").format(suc_count)
                for num, res in enumerate(success, start=0):
                    booted += f"`[{num+1}]` {res}\n"
                await ctx.send(booted)
                self.bot.dispatch('hackban', ctx.guild, ctx.author, banned, reason)
            if success and failed:
                booted += _("**I've successfully hack-banned {0} member(s):**\n").format(suc_count)
                not_booted += _("**However, I failed to hack-ban the following {0} member(s):**\n").format(fail_count)
                for num, res in enumerate(success, start=0):
                    booted += f"`[{num+1}]` {res}\n"
                for num, res in enumerate(failed, start=0):
                    not_booted += f"`[{num+1}]` {res}\n"
                await ctx.send(booted + not_booted)
                self.bot.dispatch('hackban', ctx.guild, ctx.author, banned, reason)
            if not success and failed:
                not_booted += _("**I failed to hack-ban all the members:**\n")
                for num, res in enumerate(failed, start=0):
                    not_booted += f"`[{num+1}]` {res}\n"
                await ctx.send(not_booted)
        except Exception as e:
            self.bot.dispatch('silent_error', ctx, e)
            return await ctx.send(_("{0} Something failed with sending the message, "
                                    "I've sent this error to my developers and they should hopefully resolve it soon.").format(
                                    self.bot.settings['emojis']['misc']['warn']
                                ))

    @commands.command(brief='Unban user from the server', aliases=['uba'])
    @moderator(ban_members=True)
    @commands.guild_only()
    @commands.bot_has_permissions(ban_members=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def unban(self, ctx, banned_user: BannedMember, *, reason: commands.clean_content = None):
        """ Unbans a banned user from this server """

        reason = reason or None

        if reason and len(reason) > 450:
            return await ctx.send(_("{0} Reason can only be 450 characters long."
                                    " You're {1} characters over.").format(
                                        self.bot.settings['emojis']['misc']['warn'], len(reason) - 400
                                    ))

        try:
            await ctx.guild.unban(banned_user.user, reason=default.responsible(ctx.author, reason))
            await ctx.send(_("I've successfully unbanned **{0}** for **{1}**").format(
                banned_user.user, _('No reason provided.') if reason is None else reason
            ))
            await default.execute_untemporary(ctx, 1, banned_user.user, ctx.guild)
            self.bot.dispatch('unban', ctx.guild, ctx.author, [banned_user.user], reason)
        except Exception as e:
            self.bot.dispatch('silent_error', ctx, e)
            return await ctx.send(_("{0} Something failed with sending the message, "
                                    "I've sent this error to my developers and they should hopefully resolve it soon.").format(
                                        self.bot.settings['emojis']['misc']['warn']
                                    ))

    @commands.command(brief='Unban everyone from the server', aliases=['massunban', 'ubaall', 'massuba'])
    @moderator(ban_members=True)
    @commands.guild_only()
    @commands.bot_has_permissions(ban_members=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def unbanall(self, ctx, *, reason: commands.clean_content = None):
        """ Unban everyone from the server """
        bans = len(await ctx.guild.bans())

        if bans == 0:
            return await ctx.send(_("{0} This server has no bans.").format(self.bot.settings['emojis']['misc']['warn']))

        reason = reason or None

        if reason and len(reason) > 450:
            return await ctx.send(_("{0} Reason can only be 450 characters long."
                                    " You're {1} characters over.").format(
                                        self.bot.settings['emojis']['misc']['warn'], len(reason) - 400
                                    ))

        def check(r, u):
            return u.id == ctx.author.id and r.message.id == checkmsg.id

        loop = True
        total_unbanned = []
        while loop:
            try:
                checkmsg = await ctx.channel.send(_("Are you sure you want to unban all **{0}** members from this server?").format(bans))
                await checkmsg.add_reaction(f"{self.bot.settings['emojis']['misc']['white-mark']}")
                await checkmsg.add_reaction(f"{self.bot.settings['emojis']['misc']['red-mark']}")
                reaction, user = await self.bot.wait_for('reaction_add', check=check, timeout=180.0)

                if str(reaction) == f"{self.bot.settings['emojis']['misc']['white-mark']}":
                    loop = False
                    try:
                        await checkmsg.clear_reactions()
                    except Exception:
                        pass
                    await checkmsg.edit(content=_("Unbanning all members..."))
                    fail = 0
                    for member in await ctx.guild.bans():
                        try:
                            await ctx.guild.unban(member.user, reason=default.responsible(ctx.author, reason))
                            await default.execute_untemporary(ctx, 1, member.user, ctx.guild)
                            total_unbanned.append(member.user)
                            count = bans - len(await ctx.guild.bans())
                        except discord.HTTPException:
                            fail += 1
                            pass
                    await checkmsg.edit(content=_("I've successfully unbanned **{0}/{1}** members.").format(bans - fail, bans))
                    self.bot.dispatch('unban', ctx.guild, ctx.author, total_unbanned, reason)
                elif str(reaction) == f"{self.bot.settings['emojis']['misc']['red-mark']}":
                    loop = False
                    await checkmsg.edit(content=_("I will not unban anyone."), delete_after=20)
                    try:
                        await checkmsg.clear_reactions()
                    except Exception:
                        pass
                else:
                    await checkmsg.edit(content=_('Wrong emoji; please try again.'), delete_after=20)
                    try:
                        await checkmsg.clear_reactions()
                    except Exception:
                        pass

            except asyncio.TimeoutError:
                return

            except Exception as e:
                self.bot.dispatch('silent_error', ctx, e)
                return await ctx.send(_("{0} Something failed with sending the message, "
                                        "I've sent this error to my developers and they should hopefully resolve it soon.").format(
                                        self.bot.settings['emojis']['misc']['warn']
                                    ))

    @commands.command(brief='Mute member in the server', aliases=['tempmute'])
    @moderator(manage_roles=True)
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def mute(self, ctx, members: commands.Greedy[discord.Member], duration: typing.Optional[btime.FutureTime], *, reason: commands.clean_content = None):
        """ Mute members in the server

        If duration is provided, they'll get unmuted after the duration ends
        If multiple members are provided, all of them will get muted."""

        reason = reason or None

        muterole = await default.get_muterole(ctx, ctx.guild, True)

        if len(set(members)) == 0:
            return await ctx.send(_("{0} | You're missing an argument - **members**").format(
                self.bot.settings['emojis']['misc']['warn']
            ))

        if reason and len(reason) > 450:
            return await ctx.send(_("{0} Reason can only be 450 characters long."
                                    " You're {1} characters over.").format(
                                        self.bot.settings['emojis']['misc']['warn'], len(reason) - 450
                                    ))

        if len(set(members)) > 10:
            return await ctx.send(_("{0} | You can only mute 10 members at once.").format(self.bot.settings['emojis']['misc']['warn']))

        if muterole.position > ctx.guild.me.top_role.position:
            return await ctx.send(_("{0} | The muted role is above me in the role hierarchy, "
                                    "so I cannot access it. Please lower {1}, so I can access the role and mute the member(s).").format(
                                        self.bot.settings['emojis']['misc']['warn'], muterole.mention
                                    ))

        if len(set(members)) != 0:
            muted, notmuted, success_mute, success, fail = [], [], [], 0, 0
            for member in set(members):
                if member == ctx.author:
                    notmuted.append(_("{0} ({1}) - **You are the member though?**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                if member.top_role.position >= ctx.guild.me.top_role.position:
                    notmuted.append(_("{0} ({1}) - **Member is above me in the role hierarchy or has the same role**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                elif member.top_role.position >= ctx.author.top_role.position:
                    notmuted.append(_("{0} ({1}) - **Member is above you in the role hierarchy or has the same role**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                elif member.guild_permissions.administrator:
                    notmuted.append(_("{0} ({1}) - **Member is an administrator, muting them will do nothing**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                if muterole in member.roles:
                    notmuted.append(_("{0} ({1}) - **Member looks to be already muted.**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                try:
                    await member.add_roles(muterole, reason=default.responsible(ctx.author, reason))
                    await default.execute_temporary(ctx, 1, member, ctx.author, ctx.guild, muterole, duration, reason)
                    muted.append(f"{member.mention} ({member.id})")
                    success_mute.append(member)
                    success += 1
                except discord.Forbidden:
                    notmuted.append(_("{0} ({1}) - **I do not have permissions to add that role for whatever reason.**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                except discord.HTTPException:
                    notmuted.append(f"{0} ({1}) - **Failed to add the mute role.**").format(
                        member.mention, member.id
                    )
                    fail += 1
                    continue

            try:
                mute, not_muted = "", ""
                if muted and not notmuted:
                    mute += _("**I've successfully muted {0} member(s){1}:**\n").format(success, _(' for {0}').format(btime.human_timedelta(duration.dt, source=ctx.message.created_at, suffix=None)) if duration is not None else '')
                    for num, res in enumerate(muted, start=0):
                        mute += f"`[{num+1}]` {res}\n"
                    await ctx.send(mute)
                    self.bot.dispatch('mute', ctx.guild, ctx.author, success_mute, duration if duration else None, reason, ctx.message.created_at)
                if muted and notmuted:
                    mute += _("**I've successfully muted {0} member(s){1}:**\n").format(success, _(' for {0}').format(btime.human_timedelta(duration.dt, source=ctx.message.created_at, suffix=None)) if duration is not None else '')
                    not_muted += _("**However, I failed to mute the following {0} member(s):**\n").format(fail)
                    for num, res in enumerate(muted, start=0):
                        mute += f"`[{num+1}]` {res}\n"
                    for num, res in enumerate(notmuted, start=0):
                        not_muted += f"`[{num+1}]` {res}\n"
                    await ctx.send(mute + not_muted)
                    self.bot.dispatch('mute', ctx.guild, ctx.author, success_mute, duration if duration else None, reason, ctx.message.created_at)
                if not muted and notmuted:
                    not_muted += _("**I failed to mute all the members:**\n")
                    for num, res in enumerate(notmuted, start=0):
                        not_muted += f"`[{num+1}]` {res}\n"
                    await ctx.send(not_muted)
            except Exception as e:
                self.bot.dispatch('silent_error', ctx, e)
                return await ctx.send(_("{0} Something failed with sending the message, "
                                        "I've sent this error to my developers and they should hopefully resolve it soon.").format(
                                        self.bot.settings['emojis']['misc']['warn']
                                    ))

    @commands.command(brief='Unmute member in the server')
    @moderator(manage_roles=True)
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def unmute(self, ctx, members: commands.Greedy[discord.Member], *, reason: commands.clean_content = None):
        """ Unmute member in the server

        If multiple members are provided, all of them will get unmuted."""

        reason = reason or None

        muterole = await default.get_muterole(ctx, ctx.guild, True)

        if len(set(members)) == 0:
            return await ctx.send(_("{0} | You're missing an argument - **members**").format(
                self.bot.settings['emojis']['misc']['warn']
            ))

        if reason and len(reason) > 450:
            return await ctx.send(_("{0} Reason can only be 450 characters long."
                                    " You're {1} characters over.").format(
                                        self.bot.settings['emojis']['misc']['warn'], len(reason) - 450
                                    ))

        if len(set(members)) > 10:
            return await ctx.send(_("{0} | You can only unmute 10 members at once.").format(self.bot.settings['emojis']['misc']['warn']))

        if muterole.position > ctx.guild.me.top_role.position:
            return await ctx.send(_("{0} | The muted role is above me in the role hierarchy, "
                                    "so I cannot access it. Please lower {1}, so I can access the role and mute the member(s).").format(
                                        self.bot.settings['emojis']['misc']['warn'], muterole.mention
                                    ))

        if len(set(members)) != 0:
            notmuted, muted, success_unmute, fail, success = [], [], [], 0, 0
            for member in set(members):
                if member == ctx.author:
                    notmuted.append(_("{0} ({1}) - **You are the member though?**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                if member.top_role.position >= ctx.guild.me.top_role.position:
                    notmuted.append(_("{0} ({1}) - **Member is above me in the role hierarchy, or they have the same role**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                elif member.top_role.position >= ctx.author.top_role.position:
                    notmuted.append(_("{0} ({1}) - **Member is above you in the role hierarchy or has the same role**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                if muterole not in member.roles:
                    notmuted.append(_("{0} ({1}) - **Member doesn't seem to be muted.**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                try:
                    await member.remove_roles(muterole, reason=default.responsible(ctx.author, reason))
                    await default.execute_untemporary(ctx, 1, member, ctx.guild)
                    muted.append(f"{member.mention} ({member.id})")
                    success += 1
                    success_unmute.append(member)
                except discord.Forbidden:
                    notmuted.append(_("{0} ({1}) - **I do not have permissions to remove that role for whatever reason.**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                except discord.HTTPException:
                    notmuted.append(_("{0} ({1}) - **Failed to remove the mute role.**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue

            try:
                unmuted, not_muted = "", ""
                if muted and not notmuted:
                    unmuted += _("**I've successfully unmuted {0} member(s):**\n").format(success)
                    for num, res in enumerate(muted, start=0):
                        unmuted += f"`[{num+1}]` {res}\n"
                    await ctx.send(unmuted)
                    self.bot.dispatch('unmute', ctx.guild, ctx.author, success_unmute, reason)
                if muted and notmuted:
                    unmuted += _("**I've successfully unmuted {0} member(s):**\n").format(success)
                    not_muted += _("**However, I failed to unmute the following {0} member(s):**\n").format(fail)
                    for num, res in enumerate(muted, start=0):
                        unmuted += f"`[{num+1}]` {res}\n"
                    for num, res in enumerate(notmuted, start=0):
                        not_muted += f"`[{num+1}]` {res}\n"
                    await ctx.send(unmuted + not_muted)
                    self.bot.dispatch('unmute', ctx.guild, ctx.author, success_unmute, reason)
                if not muted and notmuted:
                    not_muted += _("**I failed to unmute all the members:**\n")
                    for num, res in enumerate(notmuted, start=0):
                        not_muted += f"`[{num+1}]` {res}\n"
                    await ctx.send(not_muted)
            except Exception as e:
                self.bot.dispatch('silent_error', ctx, e)
                return await ctx.send(_("{0} Something failed with sending the message, "
                                        "I've sent this error to my developers and they should hopefully resolve it soon.").format(
                                        self.bot.settings['emojis']['misc']['warn']
                                    ))

    @commands.command(brief='Voice mute member in the server', aliases=['vmute'])
    @moderator(mute_members=True)
    @commands.guild_only()
    @commands.bot_has_guild_permissions(mute_members=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def voicemute(self, ctx, members: commands.Greedy[discord.Member], *, reason: commands.clean_content = None):
        """ Voice mute an annoying member in voice channel.

        If multiple members are passed, all of them will get voice muted.
        They need to be in voice channel in order to voice mute them. """

        reason = reason or None

        if len(set(members)) == 0:
            return await ctx.send(_("{0} | You're missing an argument - **members**").format(
                self.bot.settings['emojis']['misc']['warn']
            ))

        if reason and len(reason) > 450:
            return await ctx.send(_("{0} Reason can only be 450 characters long."
                                    " You're {1} characters over.").format(
                                        self.bot.settings['emojis']['misc']['warn'], len(reason) - 450
                                    ))

        if len(set(members)) > 10:
            return await ctx.send(_("{0} | You can only voice mute 10 members at once.").format(self.bot.settings['emojis']['misc']['warn']))

        if len(set(members)) != 0:
            voice_muted, notmuted, success_vmute, success, fail = [], [], [], 0, 0
            for member in set(members):
                if member == ctx.author:
                    notmuted.append(_("{0} ({1}) - **You are the member though?**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                elif member.voice is None:
                    notmuted.append(_("{0} ({1}) - **Member is not in a voice channel.**").format(member.mention, member.id))
                    fail += 1
                    continue
                elif member.voice.mute is True:
                    notmuted.append(_("{0} ({1}) - **Member is already voice muted.**").format(member.mention, member.id))
                    fail += 1
                    continue
                try:
                    await member.edit(mute=True, reason=default.responsible(ctx.author, reason))
                    voice_muted.append(f"{member.mention} ({member.id})")
                    success_vmute.append(member)
                    success += 1
                except discord.Forbidden:
                    notmuted.append(_("{0} ({1}) - **I'm missing permissions to perform this action**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                except discord.HTTPException:
                    notmuted.append(_("{0} ({1}) - **Failed. Not sure what though ¯\_(ツ)_/¯**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue

            try:
                vmuted, not_muted = "", ""
                if voice_muted and not notmuted:
                    vmuted += _("**I've successfully voice muted {0} member(s):**\n").format(success)
                    for num, res in enumerate(voice_muted, start=0):
                        vmuted += f"`[{num+1}]` {res}\n"
                    await ctx.send(vmuted)
                    self.bot.dispatch('voice_mute', ctx.guild, ctx.author, success_vmute, reason)
                if voice_muted and notmuted:
                    vmuted += _("**I've successfully voice muted {0} member(s):**\n").format(success)
                    not_muted += _("**However, I failed to voice mute the following {0} member(s):**\n").format(fail)
                    for num, res in enumerate(voice_muted, start=0):
                        vmuted += f"`[{num+1}]` {res}\n"
                    for num, res in enumerate(notmuted, start=0):
                        not_muted += f"`[{num+1}]` {res}\n"
                    await ctx.send(vmuted + not_muted)
                    self.bot.dispatch('voice_mute', ctx.guild, ctx.author, success_vmute, reason)
                if not voice_muted and notmuted:
                    not_muted += _("**I failed to voice mute all the members:**\n")
                    for num, res in enumerate(notmuted, start=0):
                        not_muted += f"`[{num+1}]` {res}\n"
                    await ctx.send(not_muted)
            except Exception as e:
                self.bot.dispatch('silent_error', ctx, e)
                return await ctx.send(_("{0} Something failed with sending the message, "
                                        "I've sent this error to my developers and they should hopefully resolve it soon.").format(
                                        self.bot.settings['emojis']['misc']['warn']
                                    ))

    @commands.command(brief='Voice unmute member in the server', aliases=['vunmute'])
    @moderator(mute_members=True)
    @commands.guild_only()
    @commands.bot_has_guild_permissions(mute_members=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def voiceunmute(self, ctx, members: commands.Greedy[discord.Member], *, reason: commands.clean_content = None):
        """ Voice unmute an annoying member in voice channel.

        If multiple members are passed, all of them will get voice unmuted.
        They need to be in voice channel in order to voice unmute them. """

        reason = reason or None

        if len(set(members)) == 0:
            return await ctx.send(_("{0} | You're missing an argument - **members**").format(
                self.bot.settings['emojis']['misc']['warn']
            ))

        if reason and len(reason) > 450:
            return await ctx.send(_("{0} Reason can only be 450 characters long."
                                    " You're {1} characters over.").format(
                                        self.bot.settings['emojis']['misc']['warn'], len(reason) - 450
                                    ))

        if len(set(members)) > 10:
            return await ctx.send(_("{0} | You can only voice unmute 10 members at once.").format(self.bot.settings['emojis']['misc']['warn']))

        if len(set(members)) != 0:
            voice_unmuted, notmuted, success_unvmute, success, fail = [], [], [], 0, 0
            for member in set(members):
                if member == ctx.author:
                    notmuted.append(_("{0} ({1}) - **You can't unvoice mute yourself.**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                if member.voice is None:
                    notmuted.append(_("{0} ({1}) - **Member is not in a voice channel.**").format(member.mention, member.id))
                    fail += 1
                    continue
                if member.voice.mute is False:
                    notmuted.append(_("{0} ({1}) - **Member is not voice muted.**").format(member.mention, member.id))
                    fail += 1
                    continue
                try:
                    await member.edit(mute=False, reason=default.responsible(ctx.author, reason))
                    voice_unmuted.append(f"{member.mention} ({member.id})")
                    success_unvmute.append(member)
                    success += 1
                except discord.Forbidden:
                    notmuted.append(f"{member.mention} ({member.id}) - **I'm missing permissions to perform this action**")
                    fail += 1
                    continue
                except discord.HTTPException:
                    notmuted.append(f"{member.mention} ({member.id}) - **Failed. Not sure what though**")
                    fail += 1
                    continue

            try:
                vunmuted, not_muted = "", ""
                if voice_unmuted and not notmuted:
                    vunmuted += _("**I've successfully voice unmuted {0} member(s):**\n").format(success)
                    for num, res in enumerate(voice_unmuted, start=0):
                        vunmuted += f"`[{num+1}]` {res}\n"
                    await ctx.send(vunmuted)
                    self.bot.dispatch('voice_unmute', ctx.guild, ctx.author, success_unvmute, reason)
                if voice_unmuted and notmuted:
                    vunmuted += _("**I've successfully voice unmuted {0} member(s):**\n").format(success)
                    not_muted += _("**However I failed to voice unmute the following {0} member(s):**\n").format(fail)
                    for num, res in enumerate(voice_unmuted, start=0):
                        vunmuted += f"`[{num+1}]` {res}\n"
                    for num, res in enumerate(notmuted, start=0):
                        not_muted += f"`[{num+1}]` {res}\n"
                    await ctx.send(vunmuted + not_muted)
                    self.bot.dispatch('voice_unmute', ctx.guild, ctx.author, success_unvmute, reason)
                if not voice_unmuted and notmuted:
                    not_muted += _("**I failed to voice unmute all the members:**\n")
                    for num, res in enumerate(notmuted, start=0):
                        not_muted += f"`[{num+1}]` {res}\n"
                    await ctx.send(not_muted)
            except Exception as e:
                self.bot.dispatch('silent_error', ctx, e)
                return await ctx.send(_("{0} Something failed with sending the message, "
                                        "I've sent this error to my developers and they should hopefully resolve it soon.").format(
                                        self.bot.settings['emojis']['misc']['warn']
                                    ))

    @commands.command(brief='Warn a member', aliases=['addwarn'])
    @moderator(manage_messages=True)
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def warn(self, ctx, members: commands.Greedy[discord.Member], *, reason: commands.clean_content = None):
        """ Warn a member in the server
        If multiple members are provided they all will get warned.

        Member will get a DM when he'll get warned, you can use `silent` feature to send warning into DMs annonymously.
        Example: `warn <member> [--s] [reason]`"""

        if len(set(members)) == 0:
            return await ctx.send(_("{0} | You're missing an argument - **members**").format(
                self.bot.settings['emojis']['misc']['warn']
            ))

        if reason and len(reason) > 450:
            return await ctx.send(_("{0} Reason can only be 450 characters long."
                                    " You're {1} characters over.").format(
                                        self.bot.settings['emojis']['misc']['warn'], len(reason) - 450
                                    ))

        if len(set(members)) > 10:
            return await ctx.send(_("{0} | You can only warn 10 members at once.").format(self.bot.settings['emojis']['misc']['warn']))

        if len(set(members)) > 0:
            warned, failed, success_warn, success, fail = [], [], [], 0, 0
            embed = discord.Embed(color=self.bot.settings['colors']['deny_color'], title=_('Warning!'), timestamp=datetime.utcnow())
            # Thanks Duck for this idea - https://quacky.xyz/
            if reason and reason.lower().startswith('--s'):
                reason = reason[3:] or "No reason"
            elif reason and not reason.lower().startswith('--s') or reason is None:
                embed.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)
            reason = reason or "No reason"
            for member in set(members):
                if member == ctx.author:
                    failed.append(_("{0} ({1}) - **You are the member though?**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                if member.top_role.position >= ctx.author.top_role.position:
                    failed.append(_("{0} ({1}) - **Member is above you in the role hierarchy or has the same role**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                if member.bot:
                    failed.append(_("{0} ({1}) - **Member is a bot.**").format(member.mention, member.id))
                    fail += 1
                    continue
                else:
                    try:
                        embed.description = _("You were warned in **{0}** for:\n{1}").format(ctx.guild.name, reason)
                        await member.send(embed=embed)
                    except Exception as e:
                        print(e)
                        pass
                    warned.append(f"{member.mention} ({member.id})")
                    success_warn.append(member)
                    success += 1
                    continue

            try:
                warn = ""
                not_warned = ""
                if warned and not failed:
                    warn += _("**I've successfully warned {0} member(s):**\n").format(success)
                    for num, res in enumerate(warned, start=0):
                        warn += f"`[{num+1}]` {res}\n"
                    await ctx.send(warn)
                    self.bot.dispatch('warn', ctx.guild, ctx.author, success_warn, reason)
                if warned and failed:
                    warn += _("**I've successfully warned {0} member(s):**\n").format(success)
                    not_warned += _("**However I failed to warn the following {0} member(s):**\n").format(fail)
                    for num, res in enumerate(warned, start=0):
                        warn += f"`[{num+1}]` {res}\n"
                    for num, res in enumerate(failed, start=0):
                        not_warned += f"`[{num+1}]` {res}\n"
                    await ctx.send(warn + not_warned)
                    self.bot.dispatch('warn', ctx.guild, ctx.author, success_warn, reason)
                if not warned and failed:
                    not_warned += _("**I failed to warn all the members:**\n")
                    for num, res in enumerate(failed, start=0):
                        not_warned += f"`[{num+1}]` {res}\n"
                    await ctx.send(not_warned)
            except Exception as e:
                self.bot.dispatch('silent_error', ctx, e)
                return await ctx.send(_("{0} Something failed with sending the message, "
                                        "I've sent this error to my developers and they should hopefully resolve it soon.").format(
                                        self.bot.settings['emojis']['misc']['warn']
                                    ))

    @commands.group(aliases=['clear', 'delete', 'prune'], brief="Manage messages in the chat", invoke_without_command=True)
    @commands.guild_only()
    @moderator(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx, search=100):
        """
        Purge messages in the chat. Default amount is set to **100**
        This will not purge pins.
        """
        await ctx.message.delete()

        def pins(m):
            if not m.pinned:
                return True
            return False
        await self.do_removal(ctx, search, pins)

    @purge.command(brief='Purge all the messages')
    @moderator(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def all(self, ctx, search=100):
        """
        Purge all the messages in chat. Default amount is set to **100**
        This will purge everything, pins as well.
        """
        await ctx.message.delete()
        await self.do_removal(ctx, search, lambda e: True)

    @purge.command(brief="User messages", description="Clear messages sent from an user")
    @moderator(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def user(self, ctx, member: discord.Member, search=100):
        """ Removes user messages """
        await ctx.message.delete()
        await self.do_removal(ctx, search, lambda e: e.author == member)

    @purge.command(name='bot', brief="Bot messages")
    @moderator(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def _bot(self, ctx, prefix=None, search=100):
        """Removes a bot user's messages and messages with their optional prefix."""

        def predicate(m):
            return (m.webhook_id is None and m.author.bot) or (prefix and m.content.startswith(prefix))

        await self.do_removal(ctx, search, predicate)

    @purge.command(brief="Embed messages")
    @moderator(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def embeds(self, ctx, search=100):
        """Removes messages that have embeds in them."""
        await self.do_removal(ctx, search, lambda e: len(e.embeds))

    @purge.command(brief="Image messages")
    @moderator(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def images(self, ctx, search=100):
        """Removes messages that have embeds or attachments."""
        await self.do_removal(ctx, search, lambda e: len(e.embeds) or len(e.attachments))

    @purge.command(brief="Messages containing the given word")
    @moderator(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def contains(self, ctx, *, substr: str):
        """Removes all messages containing a substring.
        The substring must be at least 3 characters long.
        """
        if len(substr) < 3:
            await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} substring must be at least 3 characters long.")
        else:
            await self.do_removal(ctx, 100, lambda e: substr in e.content)

    @purge.command(name='emoji', brief="Custom emoji messages")
    @moderator(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def _emoji(self, ctx, search=100):
        """Removes all messages containing custom emoji."""
        custom_emoji = re.compile(r'<:(\w+):(\d+)>')

        def predicate(m):
            return custom_emoji.search(m.content)

        await self.do_removal(ctx, search, predicate)

    @purge.command(brief="Custom messages")
    @moderator(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    async def custom(self, ctx, *, args: str):
        """A more advanced purge command.
        This command uses a powerful "command line" syntax.
        Most options support multiple values to indicate 'any' match.
        If the value has spaces it must be quoted.
        The messages are only deleted if all options are met unless
        the `--or` flag is passed, in which case only if any is met.
        The following options are valid.
        `--user`: A mention or name of the user to remove.
        `--contains`: A substring to search for in the message.
        `--starts`: A substring to search if the message starts with.
        `--ends`: A substring to search if the message ends with.
        `--search`: How many messages to search. Default 100. Max 2000.
        `--after`: Messages must come after this message ID.
        `--before`: Messages must come before this message ID.
        Flag options (no arguments):
        `--bot`: Check if it's a bot user.
        `--embeds`: Check if the message has embeds.
        `--files`: Check if the message has attachments.
        `--emoji`: Check if the message has custom emoji.
        `--reactions`: Check if the message has reactions
        `--or`: Use logical OR for all options.
        `--not`: Use logical NOT for all options.
        """
        parser = Arguments(add_help=False, allow_abbrev=False)
        parser.add_argument('--user', nargs='+')
        parser.add_argument('--contains', nargs='+')
        parser.add_argument('--starts', nargs='+')
        parser.add_argument('--ends', nargs='+')
        parser.add_argument('--or', action='store_true', dest='_or')
        parser.add_argument('--not', action='store_true', dest='_not')
        parser.add_argument('--emoji', action='store_true')
        parser.add_argument('--bot', action='store_const', const=lambda m: m.author.bot)
        parser.add_argument('--embeds', action='store_const', const=lambda m: len(m.embeds))
        parser.add_argument('--files', action='store_const', const=lambda m: len(m.attachments))
        parser.add_argument('--reactions', action='store_const', const=lambda m: len(m.reactions))
        parser.add_argument('--search', type=int, default=100)
        parser.add_argument('--after', type=int)
        parser.add_argument('--before', type=int)

        try:
            args = parser.parse_args(shlex.split(args))
        except Exception as e:
            await ctx.send(str(e))
            return

        predicates = []
        if args.bot:
            predicates.append(args.bot)

        if args.embeds:
            predicates.append(args.embeds)

        if args.files:
            predicates.append(args.files)

        if args.reactions:
            predicates.append(args.reactions)

        if args.emoji:
            custom_emoji = re.compile(r'<:(\w+):(\d+)>')
            predicates.append(lambda m: custom_emoji.search(m.content))

        if args.user:
            users = []
            converter = commands.MemberConverter()
            for u in args.user:
                try:
                    user = await converter.convert(ctx, u)
                    users.append(user)
                except Exception as e:
                    await ctx.send(str(e))
                    return

            predicates.append(lambda m: m.author in users)

        if args.contains:
            predicates.append(lambda m: any(sub in m.content for sub in args.contains))

        if args.starts:
            predicates.append(lambda m: any(m.content.startswith(s) for s in args.starts))

        if args.ends:
            predicates.append(lambda m: any(m.content.endswith(s) for s in args.ends))

        op = all if not args._or else any

        def predicate(m):
            r = op(p(m) for p in predicates)
            if args._not:
                return not r
            return r

        args.search = max(0, min(2000, args.search))  # clamp from 0-2000
        await self.do_removal(ctx, args.search, predicate, before=args.before, after=args.after)

    @commands.command(brief='Nuke the channel', aliases=['clone'])
    @admin(manage_channels=True)
    @commands.guild_only()
    @commands.bot_has_permissions(manage_channels=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def nuke(self, ctx, channel: discord.TextChannel = None, *, reason: commands.clean_content = None):
        """ Nuke any server in the channel.
        This command will clone the selected channel and create another one with exact permissions """

        channel = channel or ctx.channel
        reason = reason or None

        try:
            new_channel = await channel.clone(reason=default.responsible(ctx.author, reason))
            await new_channel.edit(position=channel.position)
            await new_channel.send(_("{0} Successfully nuked the channel. Deleting this message in 30 seconds.").format(self.bot.settings['emojis']['misc']['white-mark']), delete_after=30)
            await channel.delete()
        except Exception as e:
            self.bot.dispatch('silent_error', ctx, e)
            return await ctx.send(_("{0} Something failed with sending the message, "
                                    "I've sent this error to my developers and they should hopefully resolve it soon.").format(
                                        self.bot.settings['emojis']['misc']['warn']
                                    ))

    @commands.command(brief='Freeze the server', aliases=['freeze-server'])
    @moderator(manage_roles=True)
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def freeze(self, ctx, reason: str = None):
        """ Freezes everyone from sending messages in the server """

        permissions = ctx.guild.default_role.permissions
        if permissions.send_messages:
            permissions.update(send_messages=False)
            await ctx.guild.default_role.edit(permissions=permissions, reason=default.responsible(ctx.author, reason))
            try:
                await ctx.send(_("{0} Server is now frozen!").format(self.bot.settings['emojis']['misc']['white-mark']))
            except Exception:
                await ctx.message.add_reaction(f"{self.bot.settings['emojis']['misc']['white-mark']}")
        elif not permissions.send_messages:
            await ctx.send(_("{0} Server is already frozen!").format(self.bot.settings['emojis']['misc']['warn']))

    @commands.command(brief='Unfreeze the server', aliases=['unfreeze-server'])
    @moderator(manage_roles=True)
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def unfreeze(self, ctx, reason: str = None):
        """ Unfreezes everyone from sending messages in the server """

        permissions = ctx.guild.default_role.permissions

        if not permissions.send_messages:
            permissions.update(send_messages=True)
            await ctx.guild.default_role.edit(permissions=permissions, reason=default.responsible(ctx.author, reason))
            try:
                await ctx.send(_("{0} Server is now unfrozen!").format(self.bot.settings['emojis']['misc']['white-mark']))
            except Exception:
                await ctx.message.add_reaction(f"{self.bot.settings['emojis']['misc']['white-mark']}")
        elif permissions.send_messages:
            await ctx.send(_("{0} Server is not frozen!").format(self.bot.settings['emojis']['misc']['warn']))

    @commands.command(brief='Create a role', aliases=['rolecreate'])
    @moderator(manage_roles=True)
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def createrole(self, ctx, *, name: str):
        """ Create a role in the server """

        if len(name) > 100:
            raise commands.BadArgument(_("Role name can't be longer than 100 characters"))
        else:
            await ctx.guild.create_role(name=name, permissions=ctx.guild.default_role.permissions, color=discord.Color.dark_grey())
            await ctx.send(_("{0} Created role named **{1}**").format(self.bot.settings['emojis']['misc']['white-mark'], name))

    @commands.command(brief='Delete a role', aliases=['delrole', 'roledel', 'roledelete'])
    @moderator(manage_roles=True)
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def deleterole(self, ctx, role: discord.Role, *, reason: str = None):
        """ Delete a role in the server """

        reason = reason or 'No reason'

        if role.position >= ctx.guild.me.top_role.position:
            return await ctx.send(_("{0} I cannot delete that role as it's higher or equal in role hiararchy!").format(
                self.bot.settings['emojis']['misc']['warn']
            ))
        elif role.position >= ctx.author.top_role.position:
            return await ctx.send(_("{0} You cannot delete that role as it's higher or equal in role hiararchy!").format(
                self.bot.settings['emojis']['misc']['warn']
            ))
        try:
            await role.delete(reason=default.responsible(ctx.author, reason))
            await ctx.send(_("{0} Successfully deleted the role!").format(self.bot.settings['emojis']['misc']['white-mark']))
        except discord.HTTPException:
            return await ctx.send(_("{0} Failed to delete the role, not sure why.").format(
                self.bot.settings['emojis']['misc']['warn']
            ))
        except discord.Forbidden:
            return await ctx.send(_("{0} Looks like I'm missing permissions, but that's not possible.").format(
                self.bot.settings['emojis']['misc']['warn']
            ))

    @commands.command(brief='Add a role to member(s)', aliases=['arole', 'addrole'], name='add-role')
    @moderator(manage_roles=True)
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def add_role(self, ctx, members: commands.Greedy[discord.Member], role: discord.Role, *, reason: commands.clean_content = None):
        """ Add a role to a member. Mentioning multiple members will add a role to multiple members. """
        reason = reason or None

        if len(set(members)) == 0:
            raise commands.MissingRequiredArgument(self.add_role.params['members'])

        if reason and len(reason) > 450:
            return await ctx.send(_("{0} Reason can only be 450 characters long."
                                    " You're {1} characters over.").format(
                                        self.bot.settings['emojis']['misc']['warn'], len(reason) - 450
                                    ))

        if len(set(members)) > 15:
            return await ctx.send(_("{0} | You can only add a role to 15 members at once.").format(self.bot.settings['emojis']['misc']['warn']))

        if len(set(members)) != 0:
            added, notadded, success, fail = [], [], 0, 0
            for member in set(members):
                if member.top_role.position >= ctx.guild.me.top_role.position:
                    notadded.append(_("{0} ({1}) - **Member is above me in the role hierarchy or has the same role**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                elif member.top_role.position > ctx.author.top_role.position:
                    notadded.append(_("{0} ({1}) - **Member is above you in the role hierarchy or has the same role**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                elif role in member.roles:
                    notadded.append(_("{0} ({1}) - **Member already has that role**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                elif role.position >= ctx.guild.me.top_role.position:
                    notadded.append(_("{0} ({1}) - **The role is either higher than me or is my highest**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                elif role.position >= ctx.author.top_role.position and ctx.author != ctx.guild.owner:
                    notadded.append(_("{0} ({1}) - **The role is either higher than you or is your highest**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                try:
                    await member.add_roles(role, reason=default.responsible(ctx.author, reason))
                    added.append(f"{member.mention} ({member.id})")
                    success += 1
                except discord.Forbidden:
                    notadded.append(_("{0} ({1}) - **I'm missing permissions to perform this action**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                except discord.HTTPException:
                    notadded.append(_("{0} ({1}) - **Failed. Not sure what though ¯\_(ツ)_/¯**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue

            try:
                addedrole, not_added = "", ""
                if added and not notadded:
                    addedrole += _("**I've successfully added a role to {0} member(s):**\n").format(success)
                    for num, res in enumerate(added, start=0):
                        addedrole += f"`[{num+1}]` {res}\n"
                    await ctx.send(addedrole)
                if added and notadded:
                    addedrole += _("**I've successfully added a role to {0} member(s):**\n").format(success)
                    not_added += _("**However, I failed to add the role to the following {0} member(s):**\n").format(fail)
                    for num, res in enumerate(added, start=0):
                        addedrole += f"`[{num+1}]` {res}\n"
                    for num, res in enumerate(notadded, start=0):
                        not_added += f"`[{num+1}]` {res}\n"
                    await ctx.send(addedrole + not_added)
                if not added and notadded:
                    not_added += _("**I failed to add a role to all the members:**\n")
                    for num, res in enumerate(notadded, start=0):
                        not_added += f"`[{num+1}]` {res}\n"
                    await ctx.send(not_added)
            except Exception as e:
                self.bot.dispatch('silent_error', ctx, e)
                return await ctx.send(_("{0} Something failed with sending the message, "
                                        "I've sent this error to my developers and they should hopefully resolve it soon.").format(
                                        self.bot.settings['emojis']['misc']['warn']
                                    ))

    @commands.command(brief='Remove a role to member(s)', aliases=['rrole', 'removerole'], name='remove-role')
    @moderator(manage_roles=True)
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def remove_role(self, ctx, members: commands.Greedy[discord.Member], role: discord.Role, *, reason: commands.clean_content = None):
        """ Remove a role to a member. Mentioning multiple members will remove a role from multiple members. """
        reason = reason or None

        if len(set(members)) == 0:
            raise commands.MissingRequiredArgument(self.remove_role.params['members'])

        if reason and len(reason) > 450:
            return await ctx.send(_("{0} Reason can only be 450 characters long."
                                    " You're {1} characters over.").format(
                                        self.bot.settings['emojis']['misc']['warn'], len(reason) - 450
                                    ))

        if len(set(members)) > 15:
            return await ctx.send(_("{0} | You can only remove a role from 15 members at once.").format(self.bot.settings['emojis']['misc']['warn']))

        if len(set(members)) != 0:
            removed, notremoved, success, fail = [], [], 0, 0
            for member in set(members):
                if member.top_role.position >= ctx.guild.me.top_role.position:
                    notremoved.append(_("{0} ({1}) - **Member is above me in the role hierarchy or has the same role**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                elif member.top_role.position >= ctx.author.top_role.position:
                    notremoved.append(_("{0} ({1}) - **Member is above you in the role hierarchy or has the same role**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                elif role not in member.roles:
                    notremoved.append(_("{0} ({1}) - **Member doesn't have that role**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                elif role.position >= ctx.guild.me.top_role.position:
                    notremoved.append(_("{0} ({1}) - **The role is either higher than me or is my highest**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                try:
                    await member.remove_roles(role, reason=default.responsible(ctx.author, reason))
                    removed.append(f"{member.mention} ({member.id})")
                    success += 1
                except discord.Forbidden:
                    notremoved.append(_("{0} ({1}) - **I'm missing permissions to perform this action**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue
                except discord.HTTPException:
                    notremoved.append(_("{0} ({1}) - **Failed. Not sure what though ¯\_(ツ)_/¯**").format(
                        member.mention, member.id
                    ))
                    fail += 1
                    continue

            try:
                rrole, not_removed = "", ""
                if removed and not notremoved:
                    rrole += _("**I've successfully removed a role from {0} member(s):**\n").format(success)
                    for num, res in enumerate(removed, start=0):
                        rrole += f"`[{num+1}]` {res}\n"
                    await ctx.send(rrole)
                if removed and notremoved:
                    rrole += _("**I've successfully removed a role from {0} member(s):**\n").format(success)
                    not_removed += _("**However, I failed to remove the role from the following {0} member(s):**\n").format(fail)
                    for num, res in enumerate(removed, start=0):
                        rrole += f"`[{num+1}]` {res}\n"
                    for num, res in enumerate(notremoved, start=0):
                        not_removed += f"`[{num+1}]` {res}\n"
                    await ctx.send(rrole + not_removed)
                if not removed and notremoved:
                    not_removed += _("**I failed to remove a role from all the members:**\n")
                    for num, res in enumerate(notremoved, start=0):
                        not_removed += f"`[{num+1}]` {res}\n"
                    await ctx.send(not_removed)
            except Exception as e:
                self.bot.dispatch('silent_error', ctx, e)
                return await ctx.send(_("{0} Something failed with sending the message, "
                                        "I've sent this error to my developers and they should hopefully resolve it soon.").format(
                                        self.bot.settings['emojis']['misc']['warn']
                                    ))

    @commands.command(brief='Edit a reason of a case', aliases=['editcase', 'editreason'])
    @moderator(manage_messages=True)
    @commands.guild_only()
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def reason(self, ctx, case_id: int, *, new_reason: str):
        """ Edit the reason of a case """

        if new_reason and len(new_reason) > 450:
            return await ctx.send(_("{0} Reason can only be 450 characters long."
                                    " You're {1} characters over.").format(
                                        self.bot.settings['emojis']['misc']['warn'], len(new_reason) - 450
                                    ))

        case_check = await self.bot.db.fetch("SELECT * FROM modlog WHERE guild_id = $1 AND case_num = $2", ctx.guild.id, case_id)

        if not case_check:
            return await ctx.send(_("{0} Case `#{1}` doesn't exist.").format(self.bot.settings['emojis']['misc']['warn'], case_id))

        channel = ctx.guild.get_channel(case_check[0]['channel_id'])
        try:
            message = await channel.fetch_message(case_check[0]['message_id'])
        except discord.NotFound:
            return await ctx.send(_("{0} Unknown message! Make sure I have permissions "
                                    "to see the logging channel and if that message exists.").format(self.bot.settings['emojis']['misc']['warn']))
        except discord.Forbidden:
            return await ctx.send(_("{0} Looks like I'm missing permissions to get that message").format(self.bot.settings['emojis']['misc']['warn']))
        except discord.HTTPException:
            return await ctx.send(_("{0} Retrieving the message failed.").format(self.bot.settings['emojis']['misc']['warn']))

        old_reason = await self.bot.db.fetchval("SELECT reason FROM modlog WHERE guild_id = $1 AND case_num = $2", ctx.guild.id, case_id)
        old_reason = old_reason or "No reason"
        embed = message.embeds[0]
        new_description = embed.description[:-len(old_reason)] + new_reason  # not using .replace cause then it replaces even usernames etc
        embed.description = new_description
        await message.edit(embed=embed)
        query = 'UPDATE modlog SET reason = $1 WHERE guild_id = $2 AND case_num = $3'
        await self.bot.db.execute(query, new_reason, ctx.guild.id, case_id)

        await ctx.channel.send(content=_('Successfully edited case `#{0}` reason').format(case_id), embed=embed)

    @commands.command(brief='Delete existing case', aliases=['removecase', 'remove'])
    @moderator(manage_messages=True)
    @commands.guild_only()
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def deletecase(self, ctx, case_id: int, *, reason: str):
        """ Delete the existing case """

        if reason and len(reason) > 450:
            return await ctx.send(_("{0} Reason can only be 450 characters long."
                                    " You're {1} characters over.").format(
                                        self.bot.settings['emojis']['misc']['warn'], len(reason) - 450
                                    ))

        case_check = await self.bot.db.fetch("SELECT * FROM modlog WHERE guild_id = $1 AND case_num = $2", ctx.guild.id, case_id)

        if not case_check:
            return await ctx.send(_("{0} Case `#{1}` doesn't exist.").format(self.bot.settings['emojis']['misc']['warn'], case_id))
        channel = ctx.guild.get_channel(case_check[0]['channel_id'])

        embed = discord.Embed(color=self.bot.settings['colors']['approve_color'],
                              title=_("{0} Case was deleted").format(self.bot.settings['emojis']['logs']['guildedit']),
                              timestamp=datetime.utcnow())
        embed.set_author(name=ctx.author, icon_url=ctx.author.avatar_url, url=f'https://discord.com/users/{ctx.author.id}')
        embed.description = _("**Case ID:** {0}\n**Moderator:** {1} ({2})\n**Reason:** {3}").format(
            case_id, ctx.author, ctx.author.id, reason
        )
        await self.bot.db.execute("DELETE FROM modlog WHERE guild_id = $1 AND case_num = $2", ctx.guild.id, case_id)
        if not channel:
            await ctx.send(_("{0} Case `#{1}` was successfuly deleted, but I was unable to send a log message to "
                             "the logging channel in which case was logged. *It was most likely deleted*").format(
                                 self.bot.settings['emojis']['misc']['white-mark'], case_id
                             ))
        else:
            message = _("{0} Case `#{1}` was successfully deleted.").format(
                self.bot.settings['emojis']['misc']['white-mark'], case_id
            )
            try:
                await channel.send(embed=embed)
            except Exception as e:
                print(e)
                message += _(" I was unable to send a message to your logging channel.")
                pass
            await ctx.send(message)

    @commands.command(brief="Get case information", aliases=['case'])
    @moderator(manage_messages=True)
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def showcase(self, ctx, case_id: int):

        case_check = await self.bot.db.fetch("SELECT * FROM modlog WHERE guild_id = $1 AND case_num = $2", ctx.guild.id, case_id)

        if not case_check:
            return await ctx.send(_("{0} Case `#{1}` doesn't exist.").format(self.bot.settings['emojis']['misc']['warn'], case_id))

        channel = ctx.guild.get_channel(case_check[0]['channel_id'])
        try:
            message = await channel.fetch_message(case_check[0]['message_id'])
        except discord.NotFound:
            return await ctx.send(_("{0} Unknown message! Make sure I have permissions "
                                    "to see the logging channel and if that message exists.").format(self.bot.settings['emojis']['misc']['warn']))
        except discord.Forbidden:
            return await ctx.send(_("{0} Looks like I'm missing permissions to get that message").format(self.bot.settings['emojis']['misc']['warn']))
        except discord.HTTPException:
            return await ctx.send(_("{0} Retrieving the message failed.").format(self.bot.settings['emojis']['misc']['warn']))

        embed = message.embeds[0]
        await ctx.send(content=_("Showing you case `#{0}` information").format(case_id), embed=embed)

    @commands.command(brief='Check user history of punishments', aliases=['punishments'])
    @moderator(manage_messages=True)
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def history(self, ctx, user: discord.User):
        """ Get a history of user's punishments """

        case_check = await self.bot.db.fetch("SELECT * FROM modlog WHERE guild_id = $1 AND user_id = $2 ORDER BY case_num", ctx.guild.id, user.id)
        no_msg = _("{0} {1} doesn't have any punishments history.").format(self.bot.settings['emojis']['misc']['warn'], user)
        temp_mutes = cm.get(self.bot, 'temp_mutes', f'{user.id}, {ctx.guild.id}')
        temp_bans = cm.get(self.bot, 'temp_bans', f'{user.id}, {ctx.guild.id}')

        if not case_check:
            return await ctx.send(no_msg)

        history = []
        bans, warns, mutes, kicks, softbans = 0, 0, 0, 0, 0
        for data in case_check:
            if not data['reason']:
                continue
            if data['action'] == 1:
                action = 'ban'
                bans += 1
            elif data['action'] == 2:
                action = 'kick'
                kicks += 1
            elif data['action'] == 3:
                action = 'softban'
                softbans += 1
            elif data['action'] == 4:
                action = 'mute'
                mutes += 1
            elif data['action'] == 5:
                action = 'warn'
                warns += 1
            elif data['action'] == 6:
                action = 'unban'
            elif data['action'] == 7:
                action = 'unmute'
            elif data['action'] == 8:
                action = 'voice mute'
            elif data['action'] == 9:
                action = 'voice unmute'
            try:
                mod = await self.bot.try_user(data['mod_id'])
            except Exception:
                mod = _("Not Found. ID: {0}").format(data['mod_id'])
            history.append(_("**Case ID:** {0}\n**Action:** {1}\n**Moderator:** {2} ({3})\n**Reason:** {4}\n\n").format(
                data['case_num'], action, mod, mod.id, data['reason'][:150] + '...' if len(data['reason']) > 150 else data['reason']
            ))

        if not history:
            return await ctx.send(no_msg)

        paginator = Pages(ctx,
                          title=_("{0} Punishments History").format(user),
                          entries=history,
                          thumbnail=None,
                          per_page=8,
                          embed_color=self.bot.settings['colors']['embed_color'],
                          footertext=_("Muted: {0}; Banned: {1}; Kicked: {2}; Softbanned: {3}; Warned: {4}").format(mutes, bans, kicks, softbans, warns),
                          author=ctx.author)
        await paginator.paginate()

    @commands.group(brief='Shows the duration of tempmute left.', name='temp-duration', invoke_without_command=True, aliases=['temp-dur'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def temp_duration(self, ctx, user: discord.Member, guild_id: int = None):
        """ Check the duration of member's tempmute.

        If you're the user, you can run this command in DMs """

        if ctx.guild and ctx.author.guild_permissions.manage_messages and not await self.bot.is_owner(ctx.author):
            guild_id = ctx.guild.id
            temp_mute = cm.get(self.bot, 'temp_mutes', f'{user.id}, {guild_id}')

            if not temp_mute or temp_mute and not temp_mute['time']:
                raise commands.BadArgument(_("User is not temp muted."))

            time = btime.human_timedelta(temp_mute['time'], source=ctx.message.created_at, suffix=None)
            await ctx.send(_("**{0}** will be unmuted in: `{1}`").format(user, time))

        elif ctx.guild and not ctx.author.guild_permissions.manage_messages:
            raise commands.MissingPermissions(['manage_messages'])

        elif not ctx.guild and guild_id:
            check_duration = cm.get(self.bot, 'check_duration', guild_id)
            if not check_duration:
                raise commands.BadArgument(_("Server administrators have disabled this feature in that server, unfortunately I cannot tell you the duration until you get unmuted."))

            user = ctx.author
            temp_mute = cm.get(self.bot, 'temp_mutes', f'{user.id}, {guild_id}')
            if not temp_mute or temp_mute and not temp_mute['time']:
                raise commands.BadArgument(_("You're not temp muted?"))

            time = btime.human_timedelta(temp_mute['time'], source=ctx.message.created_at, suffix=None)
            await ctx.send(_("You will be unmuted in: `{0}`").format(time))

        elif not ctx.guild and not guild_id:
            raise commands.BadArgument(_("Please give the ID of the server too."))

        elif await self.bot.is_owner(ctx.author):
            temp_mute = cm.get(self.bot, 'temp_mutes', f'{user.id}, {guild_id}')
            if not temp_mute or temp_mute and not temp_mute['time']:
                raise commands.BadArgument(_("User is not temp muted in that server."))

            time = btime.human_timedelta(temp_mute['time'], source=ctx.message.created_at, suffix=None)
            guild = self.bot.get_guild(guild_id)
            await ctx.send(f"**{user}** will be unmuted in {guild} in: `{time}`")

    @temp_duration.command(brief="Toggle if users should see their temp mute duration", name='toggle')
    @admin(manage_guild=True)
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def temp_duration_toggle(self, ctx):
        """ Toggle if users should be able to see when they're getting unmuted.

        They'll be able to run the command in DMs if it's toggled on. """
        check_duration = cm.get(self.bot, 'check_duration', ctx.guild.id)

        if not check_duration:
            await self.bot.db.execute("INSERT INTO temp_duration(guild_id, check_dur) VALUES($1, $2)", ctx.guild.id, True)
            self.bot.check_duration[ctx.guild.id] = True
            await ctx.send(_("{0} Users will now be able to check their temp-mute duration in their DMs").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif check_duration:
            await self.bot.db.execute("DELETE FROM temp_duration WHERE guild_id = $1", ctx.guild.id)
            self.bot.check_duration.pop(ctx.guild.id)
            await ctx.send(_("{0} Users won't be able to check their temp-mute duration in their DMs anymore.").format(self.bot.settings['emojis']['misc']['white-mark']))

    @commands.command(brief='Create an emoji', aliases=['cemoji', 'createemoji'], name='create-emoji')
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.member)
    @moderator(manage_emojis=True)
    @commands.bot_has_permissions(manage_emojis=True)
    async def createemoji(self, ctx, emoji_url: str, *, emoji_name: str):
        """ Create an emoji in the server """

        if len(emoji_name) > 32:
            raise commands.BadArgument(_("Emoji name can't be longer than 32 characters, you're {0} characters over").format(len(emoji_name) - 32))

        if len(ctx.guild.emojis) >= ctx.guild.emoji_limit:
            raise commands.BadArgument(_("This guild has reached the max amount of emojis added."))

        try:
            async with aiohttp.ClientSession() as c:
                async with c.get(emoji_url) as f:
                    bio = await f.read()

            emoji = await ctx.guild.create_custom_emoji(name=emoji_name, image=bio)
            await ctx.send(_("{0} Successfully created {1} emoji in this server.").format(self.bot.settings['emojis']['misc']['white-mark'], emoji))
        except aiohttp.InvalidURL:
            await ctx.send(_("Emoji URL is invalid"))
        except discord.InvalidArgument:
            await ctx.send(_("The URL doesn't contain any image"))
        except discord.HTTPException as err:
            await ctx.send(err)
        except TypeError:
            await ctx.send(_("You need to either provide an image URL or upload one with the command"))


def setup(bot):
    bot.add_cog(moderation(bot))
