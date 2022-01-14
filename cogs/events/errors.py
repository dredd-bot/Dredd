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
import traceback
import mystbin
import logging as log

from discord.ext import commands
from datetime import datetime, timezone
from contextlib import suppress

from time import time
from utils import logger as logging
from utils.default import admin_tracker, permissions_converter, auto_guild_leave, global_cooldown, printRAW
from utils.checks import not_voted, admin_only, booster_only, CooldownByContent, invalid_permissions_flag, music_error, DisabledCommand

dredd_commands = log.getLogger("dredd_commands")


class CommandError(commands.Cog, name="CommandError",
                   command_attrs=dict(hidden=True)):
    def __init__(self, bot):
        self.bot = bot
        self._last_result = None
        self.help_icon = ''
        self.big_icon = ''
        self.anti_spam_commands = CooldownByContent.from_cooldown(17, 15.0, commands.BucketType.member)  # 17 commands per 15 seconds
        self.pre_anti_spam = CooldownByContent.from_cooldown(5, 10, commands.BucketType.member)  # 5 commands per 10 seconds
        self.global_cooldown = commands.CooldownMapping.from_cooldown(17, 15.0, commands.BucketType.user)
        self.mystbin_client = mystbin.Client()

    @commands.Cog.listener()
    async def on_command(self, ctx):
        blacklist = await self.bot.is_blacklisted(ctx.author)
        if blacklist and blacklist['type'] == 2:
            return

        if ctx.guild and not ctx.channel.can_send:  # ignore channels where I can send permissions in
            current = ctx.message.created_at.replace(tzinfo=timezone.utc).timestamp()
            content_bucket = self.anti_spam_commands.get_bucket(ctx.message)
            if content_bucket.update_rate_limit(current):
                content_bucket.reset()
                await auto_guild_leave(ctx, ctx.author, ctx.guild)
        elif ctx.guild and ctx.channel.can_send and not await ctx.bot.is_admin(ctx.author):
            current = ctx.message.created_at.replace(tzinfo=timezone.utc).timestamp()
            content_bucket = self.global_cooldown.get_bucket(ctx.message)
            if content_bucket.update_rate_limit(current):
                content_bucket.reset()
                await global_cooldown(ctx=ctx)

        if ctx.guild:
            if ctx.guild.chunked is False:
                await ctx.guild.chunk(cache=True)
            printRAW(f"{datetime.now().__format__('%a %d %b %y, %H:%M')} - {ctx.guild.name} | {ctx.author}"
                     f"> {ctx.message.clean_content}")
            dredd_commands.info(f"{datetime.now().__format__('%a %d %b %y, %H:%M')} - {ctx.guild.name} | {ctx.author}"
                                f"> {ctx.message.clean_content}")
        else:
            printRAW(f"{datetime.now().__format__('%a %d %b %y, %H:%M')} - DM channel | {ctx.author}"
                     f"> {ctx.message.content}")
            dredd_commands.info(f"{datetime.now().__format__('%a %d %b %y, %H:%M')} - DM channel | {ctx.author}"
                                f"> {ctx.message.content}")

        if not await ctx.bot.is_owner(ctx.author):
            await logging.new_log(self.bot, time(), 5, 1)

        if ctx.command.cog:
            if await ctx.bot.is_owner(ctx.author):
                return
            if ctx.command.cog.qualified_name == 'Staff' and await ctx.bot.is_admin(ctx.author):
                await admin_tracker(ctx)

    @commands.Cog.listener()
    async def on_command_completion(self, ctx):
        if ctx.command.parent:
            cmd = f'{ctx.command.parent} {ctx.command.name}'
        else:
            cmd = ctx.command.name

        query = """
                    INSERT INTO command_logs VALUES($1, $2, $3, $4)
                    ON CONFLICT (user_id, guild_id, command) DO UPDATE
                    SET usage = command_logs.usage + 1
                    WHERE command_logs.user_id = $5
                    AND command_logs.guild_id = $6
                    AND command_logs.command = $7
                """

        guild = ctx.guild.id if ctx.guild else ctx.channel.id
        await self.bot.db.execute(query, ctx.author.id, guild, str(cmd), 1, ctx.author.id, guild, str(cmd))

        if cmd not in self.bot.cmdUsage:
            self.bot.cmdUsage[cmd] = 1
        else:
            self.bot.cmdUsage[cmd] += 1

        if str(ctx.author.id) not in self.bot.cmdUsers:
            self.bot.cmdUsers[str(ctx.author.id)] = 1
        else:
            self.bot.cmdUsers[str(ctx.author.id)] += 1

        if ctx.guild:
            if str(ctx.guild.id) not in self.bot.guildUsage:
                self.bot.guildUsage[str(ctx.guild.id)] = 1
            else:
                self.bot.guildUsage[str(ctx.guild.id)] += 1

    @commands.Cog.listener()
    async def on_command_error(self, ctx, exc):  # sourcery no-metrics

        guild_id = '' if not ctx.guild else ctx.guild.id
        channel_id = ctx.channel.id

        if ctx.command.has_error_handler():
            return

        elif isinstance(exc, not_voted):
            botlist = self.bot.bot_lists
            e = discord.Embed(color=self.bot.settings['colors']['deny_color'], title=_('Vote required!'))
            e.set_author(name=_("Hey {0}!").format(ctx.author), icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.display_avatar.url)
            e.description = _("Thank you for using me! Unfortunately this command is vote locked and you'll need to vote for Dredd. You can vote in any of these lists:\n"
                              "{0}\nIf you've voted already, please wait cause the API might be slow."
                              "\n\n*After you vote, you'll be able to use this command, and you will help Dredd gain more servers :D*").format(
                                  "\n".join(f"`[{num}]` {bot_list}" for num, bot_list in enumerate(botlist.values(), start=1))
                              )
            return await ctx.send(embed=e)

        elif isinstance(exc, admin_only):
            return await ctx.send(_("{0} This command is staff-locked").format(self.bot.settings['emojis']['ranks']['bot_admin']))

        elif isinstance(exc, booster_only):
            return await ctx.send(_("{0} This command can only be used by boosters").format(ctx.bot.settings['emojis']['ranks']['donator']))

        elif isinstance(exc, DisabledCommand):
            return await ctx.send(exc)

        elif isinstance(exc, invalid_permissions_flag):
            return await ctx.send(_("{0} You've used invalid permissions flag, please make sure you're using the correct one.").format(
                self.bot.settings['emojis']['misc']['warn']
            ))

        elif isinstance(exc, music_error):
            return await ctx.send(exc)

        elif isinstance(exc, commands.MaxConcurrencyReached):
            return await ctx.send(_("{0} This command has already been used by someone in this guild or channel.").format(self.bot.settings['emojis']['misc']['warn']))

        elif isinstance(exc, commands.PrivateMessageOnly):
            if ctx.author.id == 345457928972533773:
                await ctx.reinvoke()
            else:
                return await ctx.send(_("{0}"
                                        " | This command can only be used in"
                                        " direct messages!").format(self.bot.settings['emojis']['misc']['warn']))

        elif isinstance(exc, commands.NoPrivateMessage):
            return await ctx.send(_("{0} | This command can't be used in direct messages!").format(
                self.bot.settings['emojis']['misc']['warn']
            ))

        elif isinstance(exc, commands.NSFWChannelRequired):
            if ctx.author.id == 345457928972533773:
                await ctx.reinvoke()
                return
            else:
                message = (_("{0}"
                             " This command is marked as NSFW that's why I cannot"
                             " let you use it in this channel.").format(self.bot.settings['emojis']['logs']['nsfw']))
                return await ctx.send(message)

        elif isinstance(exc, commands.CommandNotFound):
            return

        elif isinstance(exc, commands.NotOwner):
            emoji = self.bot.settings['emojis']['ranks']['bot_owner']
            return await ctx.send(_("{0} This command can only be used by the bot developers.").format(emoji))

        elif isinstance(exc, commands.CommandInvokeError):
            ctx.command.reset_cooldown(ctx)
            exc = exc.original

        elif isinstance(exc, commands.BadArgument):
            ctx.command.reset_cooldown(ctx)
            cleaned = discord.utils.escape_mentions(str(exc))
            emoji = self.bot.settings['emojis']['misc']['warn']
            return await ctx.send(f"{emoji} | {cleaned}")  # can't translate this since it's random.

        elif isinstance(exc, commands.MissingPermissions):
            if ctx.author.id == 345457928972533773:
                await ctx.reinvoke()
            else:
                perms = "`" + '`, `'.join(permissions_converter(ctx, exc.missing_permissions)) + "`"
                emoji = self.bot.settings['emojis']['misc']['warn']
                return await ctx.send(_("{0} You're missing the {1} permission.").format(emoji, perms))

        elif isinstance(exc, commands.BotMissingPermissions):
            perms = "`" + '`, `'.join(permissions_converter(ctx, exc.missing_permissions)) + "`"
            emoji = self.bot.settings['emojis']['misc']['warn']
            return await ctx.send(_("{0} I'm missing "
                                    "{1} permissions").format(emoji, perms))

        elif isinstance(exc, commands.CheckFailure):
            return

        elif isinstance(exc, commands.TooManyArguments):
            if isinstance(ctx.command, commands.Group):
                return

        elif isinstance(exc, commands.CommandOnCooldown):
            if await self.bot.is_owner(ctx.author):
                ctx.command.reset_cooldown(ctx)
                return await ctx.reinvoke()

            if await self.bot.is_booster(ctx.author):
                ctx.command.reset_cooldown(ctx)
                return await ctx.reinvoke()

            cooldowns = self.bot.settings['channels']['cooldowns']
            log = self.bot.get_channel(cooldowns)
            color = self.bot.settings['colors']['error_color']

            embed = discord.Embed(colour=color,
                                  title=f"Cooldown resets in "
                                        f"**{exc.retry_after:.0f}** seconds")
            embed.set_author(name="User is on cooldown",
                             icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.display_avatar.url)
            embed.description = (f"**User:** {ctx.author} ({ctx.author.id})\n"
                                 f"**Guild:** {ctx.guild} ({guild_id})\n"
                                 f"**Channel:** #{ctx.channel} ({channel_id})\n")
            await log.send(embed=embed)
            return await ctx.send(_("{0} | You're on cooldown, try again in **{1}** seconds.").format(self.bot.settings['emojis']['misc']['timer'], f"{exc.retry_after:.0f}"))

        elif isinstance(exc, commands.MissingRequiredArgument):
            return await ctx.send(_("{0} "
                                    "| You're missing an argument - **{1}**").format(self.bot.settings['emojis']['misc']['warn'], exc.param.name))

        elif isinstance(exc, commands.errors.ExpectedClosingQuoteError):
            return await ctx.send(_("{0} | Looks like you haven't closed the quote").format(self.bot.settings['emojis']['misc']['warn']))

        elif isinstance(exc, commands.errors.InvalidEndOfQuotedStringError):
            return await ctx.send(_("{0} | Expected space after the quote, but received another quote").format(self.bot.settings['emojis']['misc']['warn']))

        elif isinstance(exc, commands.errors.UnexpectedQuoteError):
            return await ctx.send(_("{0} | Unexpected quote in non-quoted string, please remove all quotes.").format(self.bot.settings['emojis']['misc']['warn']))

        elif isinstance(exc, AssertionError):
            if exc:
                await ctx.send(f"{self.bot.settings['emojis']['misc']['warn']} | {exc}")
            return

        if str(exc) == "'NoneType' object has no attribute 'add_reaction'":  # no other way to prevent this
            return await ctx.send(_("{0} | Failed to add the reactions, please reinvoke the command.").format(self.bot.settings['emojis']['misc']['warn']))

        current = ctx.message.created_at.replace(tzinfo=timezone.utc).timestamp()
        content_bucket = self.pre_anti_spam.get_bucket(ctx.message)
        if not await ctx.bot.is_admin(ctx.author) and ctx.guild:
            if ctx.channel.can_send and not ctx.channel.permissions_for(ctx.guild.me).embed_links:
                return await ctx.send(_("{0} I'm missing permissions to embed links.").format(self.bot.settings['emojis']['misc']['warn']))
            elif not ctx.channel.can_send:
                if content_bucket.update_rate_limit(current):
                    content_bucket.reset()
                elif not content_bucket.update_rate_limit(current):
                    return

        ctx.command.reset_cooldown(ctx)

        support = self.bot.support
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)) + ""

        if len(tb) > 2000:
            error_url = await self.mystbin_client.post(tb, syntax='python')
            tb = exc
            error_code = f"\n[View full error here](<{error_url}>)"
        else:
            tb = tb
            error_code = ''

        if await self.bot.is_owner(ctx.author):
            embed = discord.Embed(color=self.bot.settings['colors']['error_color'],
                                  title=f"{self.bot.settings['emojis']['misc']['error']} Owner error!",
                                  description=f"You've done messed up... ```py\n{tb}```{error_code}")
            try:
                return await ctx.send(embed=embed)
            except Exception as e:
                return await ctx.author.send(content=e, embed=embed)

        log = self.bot.get_channel(self.bot.settings['channels']['command-errors'])
        query = "SELECT DISTINCT error_command, error_occured, error_jump, error_id FROM errors WHERE error_short = $1 AND error_command = $2 AND error_status = $3"
        error = await self.bot.db.fetch(query, str(exc), str(ctx.command.qualified_name), 0)

        if len(error) == 0:
            error_id = await self.bot.db.fetchval("SELECT count(*) FROM errors")
            log_embed = discord.Embed(color=self.bot.settings['colors']['error_color'],
                                      title=f"Unknown error caught | #{error_id + 1}",
                                      description=f"```py\n{tb}```{error_code}")
            log_embed.set_author(name=ctx.author, icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.display_avatar.url)
            log_embed.add_field(name='Error information:', value=(f"`{ctx.message.clean_content}`\n"
                                                                  f"**Server:** {ctx.guild} **ID:** {guild_id};\n"
                                                                  f"**Channel:** {ctx.channel} **ID:** {channel_id};\n"
                                                                  f"**Author:** {ctx.author} **ID:** {ctx.author.id}"))
            msg = await log.send(embed=log_embed)
            await self.bot.db.execute("INSERT INTO errors VALUES($1, $2, $3, $4, $5, $6, $7)", str(tb), msg.jump_url, str(ctx.command), 0, datetime.now(), error_id + 1, str(exc))
            await logging.new_log(self.bot, time(), 6, 1)
            e = discord.Embed(color=self.bot.settings['colors']['error_color'], timestamp=datetime.now(timezone.utc),
                              title=_("{0} Unknown error | #{1}").format(self.bot.settings['emojis']['misc']['error'], error_id + 1),
                              description=_("Command `{0}` raised an error, which I reported to my developer(s).\n"
                                            "My developer(s) will be working to fixing this error ASAP. "
                                            "Meanwhile, you can [join the support server]({1}) for updates.").format(ctx.command, support))

        else:
            error_jump = f"[Click here]({error[0]['error_jump']})"
            log_embed = discord.Embed(color=self.bot.settings['colors']['error_color'],
                                      title=f"Known error | #{error[0]['error_id']}",
                                      description=f"```py\n{exc}```")
            log_embed.add_field(name='Error information:', value=(f"`{ctx.message.clean_content}`\n"
                                                                  f"**Server:** {ctx.guild} **ID:** {guild_id};\n"
                                                                  f"**Channel:** {ctx.channel} **ID:** {channel_id};\n"
                                                                  f"**Author:** {ctx.author} **ID:** {ctx.author.id}\n"
                                                                  f"**Original error:** {error_jump}"))
            log_embed.set_author(name=ctx.author, icon_url=ctx.author.avatar.url if ctx.author.avatar else ctx.author.display_avatar.url)
            await log.send(embed=log_embed)
            await logging.new_log(self.bot, time(), 6, 1)
            e = discord.Embed(color=self.bot.settings['colors']['error_color'], timestamp=datetime.now(timezone.utc),
                              title=_("{0} Known error | #{1}").format(self.bot.settings['emojis']['misc']['error'], error[0]['error_id']),
                              description=_("Command `{0}` raised an error that has already reported to my developer(s).\n"
                                            "They'll be looking into this issue and trying to fix it ASAP. "
                                            "Meanwhile, you can [join the support server]({1}) for updates.").format(ctx.command, support))

        e.add_field(name=_("Error info:"), value=f"""```py\n{exc}```""")
        with suppress(Exception):
            return await ctx.send(embed=e)

    @commands.Cog.listener()
    async def on_silent_error(self, ctx, error, trace_error=True):
        channel = self.bot.get_channel(self.bot.settings['channels']['silent-errors'])
        if trace_error:
            trace = traceback.format_exception(type(error), error, error.__traceback__)
        else:
            trace = error

        e = discord.Embed(color=self.bot.settings['colors']['error_color'],
                          title='Silent error occured on command',
                          description='```py\n' + ''.join(trace) + "" + "```")
        e.add_field(name='Error information:', value=(f"`{ctx.message.clean_content}`\n"
                                                      f"**Server:** {ctx.guild} **ID:** {ctx.guild.id};\n"
                                                      f"**Channel:** {ctx.channel} **ID:** {ctx.channel.id};\n"
                                                      f"**Author:** {ctx.author} **ID:** {ctx.author.id}"))
        await channel.send(embed=e)
        await logging.new_log(self.bot, time(), 5, 1)


def setup(bot):
    bot.add_cog(CommandError(bot))
