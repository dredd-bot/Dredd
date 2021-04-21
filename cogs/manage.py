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
import json
import typing
import asyncio

from discord.ext import commands
from discord.utils import escape_markdown

from utils import default, i18n
from utils.checks import admin, moderator, is_guild_disabled
from utils.paginator import Pages
from contextlib import suppress
# from datetime import datetime


class Manage(commands.Cog, name='Management', aliases=['Manage']):
    def __init__(self, bot):
        self.bot = bot
        self.help_icon = "<:settingss:695707235833085982>"
        self.big_icon = "https://cdn.discordapp.com/emojis/695707235833085982.png?v=1"

    @commands.group(brief='Manage bot\'s prefix in the server',
                    invoke_without_command=True)
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def prefix(self, ctx):
        """ View your server's prefix """
        prefix = self.bot.cache.get(self.bot, 'prefix', ctx.guild.id)

        if prefix:
            text = _('If you want to change my prefix you can do so by invoking `{0}prefix set <new prefix>`').format(ctx.prefix)
            return await ctx.send(_("My prefix in this server is `{0}`\n"
                                    "{1}").format(escape_markdown(prefix, as_needed=True), text if ctx.author.guild_permissions.manage_guild else ''))
        elif not prefix:
            self.bot.prefix[ctx.guild.id] = self.bot.settings['default']['prefix']
            try:
                await self.bot.db.execute("INSERT INTO guilds VALUES($1, $2)", ctx.guild.id, self.bot.settings['default']['prefix'])
            except Exception:
                pass
            return await ctx.send(_("I don't have a custom prefix in this server! The default prefix is `{0}`").format(self.bot.settings['default']['prefix']))

    @prefix.command(name='set',
                    aliases=['change'],
                    brief='Change my prefix in the server')
    @commands.guild_only()
    @admin(manage_guild=True)
    async def prefix_set(self, ctx, prefix: str):
        """ Change my prefix in the server """

        if len(prefix) > 7:
            return await ctx.send(_("{0} A prefix can only be 7 characters long! You're {1} characters over.").format(self.bot.settings['emojis']['misc']['warn'], len(prefix) - 7))
        query = """UPDATE guilds
                    SET prefix = $1
                    WHERE guild_id = $2"""
        await self.bot.db.execute(query, prefix, ctx.guild.id)
        self.bot.prefix[ctx.guild.id] = prefix
        await ctx.send(_("{0} Changed my prefix in this server to `{1}`").format(self.bot.settings['emojis']['misc']['white-mark'], prefix))

    @commands.command(name='set-language', brief="Change bot's language in the server", aliases=['setlanguage', 'setlang'])
    @admin(manage_guild=True)
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.member)
    async def setlanguage(self, ctx, language: str):
        """ Change the bot's language in the current server to your prefered one (if available) """
        if language not in i18n.locales:
            return await ctx.send(_("{0} Looks like that language doesn't exist, available languages are: {1}").format(
                self.bot.settings['emojis']['misc']['warn'], '`' + '`, `'.join([x for x in i18n.locales]) + '`'
            ))
        else:
            await self.bot.db.execute("UPDATE guilds SET language = $1 WHERE guild_id = $2", language, ctx.guild.id)
            self.bot.translations[ctx.guild.id] = language
            await ctx.send(_("{0} Changed the bot language to `{1}`").format(self.bot.settings['emojis']['misc']['white-mark'], language))

    @commands.group(brief='A rough overview on server settings',
                    aliases=['settings', 'guildsettings'],
                    invoke_without_command=True)
    @commands.guild_only()
    async def serversettings(self, ctx):
        """ Rough overview on server settings, such as logging and more. """
        logs = default.server_logs(ctx, ctx.guild, simple=False)
        muterole = await default.get_muterole(ctx, ctx.guild)
        prefix = self.bot.cache.get(self.bot, 'prefix', ctx.guild.id)
        language = self.bot.cache.get(self.bot, 'translations', ctx.guild.id)
        mod_role = ctx.guild.get_role(self.bot.cache.get(self.bot, 'mod_role', ctx.guild.id))
        admin_role = ctx.guild.get_role(self.bot.cache.get(self.bot, 'admin_role', ctx.guild.id))
        modrole = mod_role.mention if mod_role else _('Default')
        adminrole = admin_role.mention if admin_role else _('Default')

        embed = discord.Embed(color=self.bot.settings['colors']['embed_color'],
                              title=_("{0} {1} Server Settings").format(self.bot.settings['emojis']['logs']['settings'], ctx.guild.name))
        embed.add_field(name=_('**Logs:**'), value=logs['logs'])
        embed.add_field(name=_('**Settings:**'), value=logs['settings'])
        embed.add_field(name=_('**More:**'), value=_("**Mute role:** {0}\n"
                                                     "**Prefix:** `{1}`\n"
                                                     "**Language:** {2}\n"
                                                     "**Mod role:** {3}\n"
                                                     "**Admin role:** {4}").format(
                                                         muterole.mention if muterole else _('Not found'), prefix, language,
                                                         modrole, adminrole))

        joinmessage = self.bot.cache.get(self.bot, 'joinmessage', ctx.guild.id)
        leavemessage = self.bot.cache.get(self.bot, 'leavemessage', ctx.guild.id)
        if joinmessage:
            if joinmessage['embedded']:
                message = _('Run `{0}serversettings joinembed` to view the welcome embed').format(ctx.prefix)
            else:
                message = joinmessage['message'] or self.bot.settings['default']['join_message_text']
            embed.add_field(name=_('Welcome Message'), value=message, inline=False)

        if leavemessage:
            if leavemessage['embedded']:
                message = _('Run `{0}serversettings leaveembed` to view the leave embed').format(ctx.prefix)
            else:
                message = leavemessage['message'] or self.bot.settings['default']['leave_message_text']
            embed.add_field(name=_('Leave Message'), value=message, inline=False)
        await ctx.send(embed=embed)

    @serversettings.command(name='joinembed', brief='View welcoming embed')
    @commands.guild_only()
    async def serversettings_joinembed(self, ctx):
        """ View welcoming messages embed """
        joinmessage = self.bot.cache.get(self.bot, 'joinmessage', ctx.guild.id)

        if not joinmessage:
            return await ctx.send(_("{0} Welcome messages are disabled in this server.").format(self.bot.settings['emojis']['misc']['warn']))

        elif joinmessage:
            if not joinmessage['embedded']:
                return await ctx.send(_("{0} Welcome messages do not use embeds in this server.").format(self.bot.settings['emojis']['misc']['warn']))
            else:
                if joinmessage['message']:
                    message = json.loads(joinmessage['message'])
                else:
                    message = self.bot.settings['default']['join_message_embed']
                embed = discord.Embed.from_dict(message)
                if not embed:
                    return await ctx.send(_("{0} Embed code is invalid, or only plain text is visible. "
                                            "Please make sure you're using the correct format by visiting this website <https://embedbuilder.nadekobot.me/>").format(self.bot.settings['emojis']['misc']['warn']))
                await ctx.send(content=_("Your welcome embed looks like this: *plain text is not displayed*"), embed=embed)

    @serversettings.command(name='leaveembed', brief='View leaving embed')
    @commands.guild_only()
    async def serversettings_leaveembed(self, ctx):
        """ View leaving messages embed """
        leavemessage = self.bot.cache.get(self.bot, 'leavemessage', ctx.guild.id)

        if not leavemessage:
            return await ctx.send(_("{0} Leave messages are disabled in this server.").format(self.bot.settings['emojis']['misc']['warn']))

        elif leavemessage:
            if not leavemessage['embedded']:
                return await ctx.send(_("{0} Leave messages do not use embeds in this server.").format(self.bot.settings['emojis']['misc']['warn']))
            else:
                if leavemessage['message']:
                    message = leavemessage['message']
                else:
                    message = self.bot.settings['default']['leave_message_embed']
                embed = discord.Embed.from_dict(message)
                if not embed:
                    return await ctx.send(_("{0} Embed code is invalid, or only plain text is visible. "
                                            "Please make sure you're using the correct format by visiting this website <https://embedbuilder.nadekobot.me/>").format(self.bot.settings['emojis']['misc']['warn']))
                await ctx.send(content=_("Your leave embed looks like this: *plain text is not displayed*"), embed=embed)

    @commands.group(brief='Toggle logging on or off',
                    aliases=['logging'],
                    invoke_without_command=True)
    @admin(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def togglelog(self, ctx):
        """ Enable or disable logging in the server

        To enable logging you need to provide channel after option, and to disable, you leave the channel argument empty. """
        await ctx.send_help(ctx.command)

    @togglelog.command(aliases=['memberlogging', 'memberlog'], brief="Toggle member logging in the server")
    @admin(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def memberlogs(self, ctx, channel: discord.TextChannel = None):
        """ This enabled or disabled member logging

        Member logging includes: avatar changes, nickname changes, username changes. """

        if channel and not channel.can_send or channel and not channel.permissions_for(ctx.guild.me).embed_links:
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        memberlogs = self.bot.cache.get(self.bot, 'memberlog', ctx.guild.id)

        if memberlogs and not channel:
            await self.bot.db.execute("DELETE from memberlog WHERE guild_id = $1", ctx.guild.id)
            self.bot.memberlog.pop(ctx.guild.id)
            return await ctx.send(_("{0} Successfully disabled member logs.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif memberlogs and channel:
            await self.bot.db.execute("UPDATE memberlog SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
            self.bot.memberlog[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Successfully changed the member logging channel. I will now send member updates in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                                          channel.mention))
        elif not memberlogs and not channel:
            return await ctx.send(_("{0} You don't have member logs enabled in this server."
                                    "\n*Hint: If you want to enable logging, you need to provide a channel where logging should be sent to*").format(self.bot.settings['emojis']['misc']['warn']))
        elif not memberlogs and channel:
            await self.bot.db.execute("INSERT INTO memberlog VALUES($1, $2)", ctx.guild.id, channel.id)
            self.bot.memberlog[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Successfully enabled member logs. I will now send member updates in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                           channel.mention))

    @togglelog.command(aliases=['joinlogging', 'joinlog', 'newmembers', 'memberjoins'], name='joinlogs', brief="Toggle join logs in the server")
    @admin(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def togglelog_joinlogs(self, ctx, channel: discord.TextChannel = None):
        """ This enabled or disabled new members logging

        New member logging includes: join logging. """

        if channel and not channel.can_send or channel and not channel.permissions_for(ctx.guild.me).embed_links:
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        joinlogs = self.bot.cache.get(self.bot, 'joinlog', ctx.guild.id)

        if joinlogs and not channel:
            await self.bot.db.execute("DELETE from joinlog WHERE guild_id = $1", ctx.guild.id)
            self.bot.joinlog.pop(ctx.guild.id)
            return await ctx.send(_("{0} New members logging was successfully disabled.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif joinlogs and channel:
            await self.bot.db.execute("UPDATE joinlog SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
            self.bot.joinlog[ctx.guild.id] = channel.id
            self.bot.dispatch('member_joinlog', ctx.author)
            return await ctx.send(_("{0} Successfully changed the new member logging channel. I will now send member updates in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                                              channel.mention))
        elif not joinlogs and not channel:
            return await ctx.send(_("{0} You don't have new member logs enabled in this server."
                                    "\n*Hint: If you want to enable logging, you need to provide a channel where logging should be sent to*").format(self.bot.settings['emojis']['misc']['warn']))
        elif not joinlogs and channel:
            await self.bot.db.execute("INSERT INTO joinlog VALUES($1, $2)", ctx.guild.id, channel.id)
            self.bot.joinlog[ctx.guild.id] = channel.id
            self.bot.dispatch('member_joinlog', ctx.author)
            return await ctx.send(_("{0} Successfully enabled new member logging. I will now send member updates in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                                  channel.mention))

    @togglelog.command(aliases=['leavelogging', 'leavelog', 'memberleaves'], name='leavelogs', brief="Toggle leave logs in the server")
    @admin(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def togglelog_leavelogs(self, ctx, channel: discord.TextChannel = None):
        """ This enables or disables member leave logging

        Member leave logging includes: leave logging. """

        if channel and not channel.can_send or channel and not channel.permissions_for(ctx.guild.me).embed_links:
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        leavelogs = self.bot.cache.get(self.bot, 'leavelog', ctx.guild.id)

        if leavelogs and not channel:
            await self.bot.db.execute("DELETE from leavelog WHERE guild_id = $1", ctx.guild.id)
            self.bot.leavelog.pop(ctx.guild.id)
            return await ctx.send(_("{0} Successfully disabled leave member logs.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif leavelogs and channel:
            await self.bot.db.execute("UPDATE leavelog SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
            self.bot.leavelog[ctx.guild.id] = channel.id
            self.bot.dispatch('member_leavelog', ctx.author)
            return await ctx.send(_("{0} Successfully changed the leave member logging channel. I will now send member updates in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                                                channel.mention))
        elif not leavelogs and not channel:
            return await ctx.send(_("{0} You don't have leave member logs enabled in this server."
                                    "\n*Hint: If you want to enable logging, you need to provide a channel where logging should be sent to*").format(self.bot.settings['emojis']['misc']['warn']))
        elif not leavelogs and channel:
            await self.bot.db.execute("INSERT INTO leavelog VALUES($1, $2)", ctx.guild.id, channel.id)
            self.bot.leavelog[ctx.guild.id] = channel.id
            self.bot.dispatch('member_leavelog', ctx.author)
            return await ctx.send(_("{0} Successfully changed the leave member logging channel. I will now send member leaves in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                                               channel.mention))

    @togglelog.command(aliases=['serverlogs'], name='guildlogs', brief="Toggle guild logs in the server")
    @admin(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def togglelog_guildlogs(self, ctx, channel: discord.TextChannel = None):
        """ This enables or disables guild changes logging

        Guild changes logging includes: name, region, icon, afk channel, mfa level, verification level, default notifications. """

        if channel and not channel.can_send or channel and not channel.permissions_for(ctx.guild.me).embed_links:
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        guildlogs = self.bot.cache.get(self.bot, 'guildlog', ctx.guild.id)

        if guildlogs and not channel:
            await self.bot.db.execute("DELETE from guildlog WHERE guild_id = $1", ctx.guild.id)
            self.bot.guildlog.pop(ctx.guild.id)
            return await ctx.send(_("{0} Successfully disabled guild log updates.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif guildlogs and channel:
            await self.bot.db.execute("UPDATE guildlog SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
            self.bot.guildlog[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Successfully changed the guild log updates channel. I will now send guild updates in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                                            channel.mention))
        elif not guildlogs and not channel:
            return await ctx.send(_("{0} You don't have guild update logging enabled in this server."
                                    "\n*Hint: If you want to enable logging, you need to provide a channel where logging should be sent to*").format(self.bot.settings['emojis']['misc']['warn']))
        elif not guildlogs and channel:
            await self.bot.db.execute("INSERT INTO guildlog VALUES($1, $2)", ctx.guild.id, channel.id)
            self.bot.guildlog[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Successfully enabled guild updates logging. I will now send guild updates in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                                    channel.mention))

    @togglelog.command(aliases=['msgedits', 'msgedit', 'editmessages'], name='messageedits', brief="Toggle edit message logs in the server")
    @admin(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def togglelog_messageedits(self, ctx, channel: discord.TextChannel = None):
        """ This enables or disables messages edit logging """

        if channel and not channel.can_send or channel and not channel.permissions_for(ctx.guild.me).embed_links:
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        messageedit = self.bot.cache.get(self.bot, 'messageedits', ctx.guild.id)

        if messageedit and not channel:
            await self.bot.db.execute("DELETE from messageedits WHERE guild_id = $1", ctx.guild.id)
            self.bot.messageedits.pop(ctx.guild.id)
            return await ctx.send(_("{0} Successfully disabled edit message logs.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif messageedit and channel:
            await self.bot.db.execute("UPDATE messageedits SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
            self.bot.messageedits[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Successfully updated the logging channel for edited messages to {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                       channel.mention))
        elif not messageedit and not channel:
            return await ctx.send(_("{0} You don't have edit message logs enabled in this server."
                                    "\n*Hint: If you want to enable logging, you need to provide a channel where logging should be sent to*").format(self.bot.settings['emojis']['misc']['warn']))
        elif not messageedit and channel:
            await self.bot.db.execute("INSERT INTO messageedits VALUES($1, $2)", ctx.guild.id, channel.id)
            self.bot.messageedits[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Enabled edit message logging in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                       channel.mention))

    @togglelog.command(aliases=['msgdeletes', 'msgdelete', 'deletemessages'], name='messagedeletes', brief="Toggle delete message logs in the server.")
    @admin(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def togglelog_messagedeletes(self, ctx, channel: discord.TextChannel = None):
        """ This enables or disables messages deleting logging """

        if channel and not channel.can_send or channel and not channel.permissions_for(ctx.guild.me).embed_links:
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        messagedelete = self.bot.cache.get(self.bot, 'messagedeletes', ctx.guild.id)

        if messagedelete and not channel:
            await self.bot.db.execute("DELETE from messagedeletes WHERE guild_id = $1", ctx.guild.id)
            self.bot.messagedeletes.pop(ctx.guild.id)
            return await ctx.send(_("{0} Successfully disabled deleted message logs.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif messagedelete and channel:
            await self.bot.db.execute("UPDATE messagedeletes SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
            self.bot.messagedeletes[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Successfully updated the logging channel for deleted messages to {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                        channel.mention))
        elif not messagedelete and not channel:
            return await ctx.send(_("{0} Deleted message logs are currently disabled in this server."
                                    "\n*Hint: If you want to enable logging, you need to provide a channel where logging should be sent to*").format(self.bot.settings['emojis']['misc']['warn']))
        elif not messagedelete and channel:
            await self.bot.db.execute("INSERT INTO messagedeletes VALUES($1, $2)", ctx.guild.id, channel.id)
            self.bot.messagedeletes[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Enabled deleted message logging in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                          channel.mention))

    @togglelog.command(aliases=['modlogs'], name='moderation', brief="Toggle moderation logs")
    @admin(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def togglelog_moderation(self, ctx, channel: discord.TextChannel = None):
        """ This enables or disables moderation logging

        Moderation logging includes: bans, kicks, mutes, unbans, unmutes. """

        if channel and not channel.can_send or channel and not channel.permissions_for(ctx.guild.me).embed_links:
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        moderation = self.bot.cache.get(self.bot, 'moderation', ctx.guild.id)

        if moderation and not channel:
            await self.bot.db.execute("DELETE from moderation WHERE guild_id = $1", ctx.guild.id)
            self.bot.moderation.pop(ctx.guild.id)
            return await ctx.send(_("{0} Moderation logging was successfully disabled.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif moderation and channel:
            await self.bot.db.execute("UPDATE moderation SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
            self.bot.moderation[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Successfully updated the moderation logging channel to {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                              channel.mention))
        elif not moderation and not channel:
            return await ctx.send(_("{0} Moderation logs are currently disabled in this server."
                                    "\n*Hint: If you want to enable logging, you need to provide a channel where logging should be sent to*").format(self.bot.settings['emojis']['misc']['warn']))
        elif not moderation and channel:
            await self.bot.db.execute("INSERT INTO moderation VALUES($1, $2)", ctx.guild.id, channel.id)
            self.bot.moderation[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Enabled moderation logging in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                     channel.mention))

    @togglelog.command(name='all', brief="Toggle all the logs in the server")
    @admin(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True)
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def togglelog_all(self, ctx, channel: discord.TextChannel = None):
        """ This enables all the logging """

        if channel and not channel.can_send or channel and not channel.permissions_for(ctx.guild.me).embed_links:
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        options = ['moderation', 'memberlog', 'joinlog', 'leavelog', 'guildlog', 'messageedits', 'messagedeletes']
        if not channel:
            count = 0
            for option in options:
                await self.bot.db.execute("DELETE from {0} WHERE guild_id = $1".format(option), ctx.guild.id)
                data = hasattr(self.bot, option)
                if data:
                    attr = getattr(self.bot, option)
                    try:
                        attr.pop(ctx.guild.id)
                    except Exception:
                        count += 1
                        pass
            if count == 7:
                return await ctx.send(_("{0} Logs are currently disabled in this server."
                                        "\n*Hint: If you want to enable logging, you need to provide a channel where logging should be sent to*").format(self.bot.settings['emojis']['misc']['warn']))
            return await ctx.send(_("{0} Successfully disabled logging.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif channel:
            query = """INSERT INTO {0}(guild_id, channel_id) VALUES($1, $2) ON CONFLICT (guild_id) DO UPDATE SET channel_id = $2 WHERE {0}.guild_id = $1"""
            for option in options:
                await self.bot.db.execute(query.format(option), ctx.guild.id, channel.id)
                data = hasattr(self.bot, option)
                if data:
                    attr = getattr(self.bot, option)
                    attr[ctx.guild.id] = channel.id
            return await ctx.send(_("{0} Enabled logging in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                          channel.mention))

    @commands.command(name='anti-hoist', brief='Toggle anti hoist')
    @moderator(manage_nicknames=True)
    @commands.bot_has_permissions(manage_nicknames=True)
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def antihoist(self, ctx, channel: discord.TextChannel = None, new_nickname: str = None):
        """ Toggle anti hoist (non-alphabetic characters infront of the name, i.e. `! I'm a hoister`)

        When toggled on it will dehoist members that have just joined the server or have just edited their nickname """

        check = self.bot.cache.get(self.bot, 'antihoist', ctx.guild.id)

        if new_nickname and len(new_nickname) > 32:
            return await ctx.send(_("{0} Nickname can't be longer than 32 characters over, you're {1} characters over.").format(self.bot.settings['emojis']['misc']['warn'], len(new_nickname) - 32))

        if channel and not channel.can_send or channel and not channel.permissions_for(ctx.guild.me).embed_links:
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        if check and not channel:
            await self.bot.db.execute("DELETE from antihoist WHERE guild_id = $1", ctx.guild.id)
            self.bot.antihoist.pop(ctx.guild.id)
            return await ctx.send(_("{0} Anti hoist was successfully disabled.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif check and channel:
            await self.bot.db.execute("UPDATE antihoist SET channel_id = $1, new_nick = $2 WHERE guild_id = $3", channel.id, new_nickname, ctx.guild.id)
            self.bot.antihoist[ctx.guild.id] = {'channel': channel.id, 'nickname': new_nickname}
            return await ctx.send(_("{0} Successfully updated the anti hoist logging channel to {1} and nickname to {2}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                                  channel.mention, new_nickname))
        elif not check and not channel:
            return await ctx.send(_("{0} Anti hoisting is currently disabled in this server."
                                    "\n*Hint: If you want to enable it, you need to provide a channel where logging should be sent to and a new nickname*").format(self.bot.settings['emojis']['misc']['warn']))
        elif not check and channel:
            await self.bot.db.execute("INSERT INTO antihoist VALUES($1, $2)", ctx.guild.id, channel.id)
            self.bot.antihoist[ctx.guild.id] = {'channel': channel.id, 'nickname': new_nickname}
            return await ctx.send(_("{0} Enabled anti hoist logging in {1} and set the new nickname to {2}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                     channel.mention, new_nickname))

    @commands.group(brief='Edit the welcoming messages', invoke_without_command=True)
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @admin(manage_guild=True)
    async def welcoming(self, ctx):
        """ Setup the welcoming messages with this command subcommands """
        await ctx.send_help(ctx.command)

    @welcoming.command(name='channel', brief='Set the channel for welcoming messages')
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @admin(manage_channels=True)
    async def welcoming_channel(self, ctx, *, channel: discord.TextChannel = None):
        """
        Set a channel where welcoming messages should be sent to.

        Make sure bot has permissions to send messages in that channel.
        """

        if channel and (not channel.can_send or not channel.permissions_for(ctx.guild.me).embed_links):
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        joinmessages = self.bot.cache.get(self.bot, 'joinmessage', ctx.guild.id)

        if joinmessages and not channel:
            await self.bot.db.execute("DELETE from joinmessage WHERE guild_id = $1", ctx.guild.id)
            self.bot.joinmessage.pop(ctx.guild.id)
            return await ctx.send(_("{0} Disabled welcome messages.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif joinmessages and channel:
            await self.bot.db.execute("UPDATE joinmessage SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
            self.bot.joinmessage[ctx.guild.id]['channel'] = channel.id
            return await ctx.send(_("{0} Enabled welcome messages in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                   channel.mention))
        elif not joinmessages and not channel:
            return await ctx.send(_("{0} Welcome messages are currently disabled in this server."
                                    "\n*Hint: If you want to enable them you need to provide a channel where they should be sent to*").format(self.bot.settings['emojis']['misc']['warn']))
        elif not joinmessages and channel:
            query = "INSERT INTO joinmessage(guild_id, embedded, log_bots, channel_id, message) VALUES($1, $2, $3, $4, $5)"
            await self.bot.db.execute(query, ctx.guild.id, False, True, channel.id, None)
            self.bot.joinmessage[ctx.guild.id] = {'message': None, 'embedded': False, 'log_bots': True, 'channel': channel.id}
            return await ctx.send(_("{0} Enabled welcome messages in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                   channel.mention))

    @welcoming.command(name='message',
                       brief="Set the welcoming message",
                       aliases=['msg', 'm'])
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @admin(manage_guild=True)
    async def welcoming_message(self, ctx, *, message: str = None):
        """ Set the welcoming messages in the server

        Passing no message will reset your welcoming message to the default one """

        joinmessage = self.bot.cache.get(self.bot, 'joinmessage', ctx.guild.id)

        if not joinmessage:
            return await ctx.send(_("{0} You cannot set up welcome messages because they are not enabled!"
                                    "To enable them run `{1}welcoming channel [#channel]`").format(self.bot.settings['emojis']['misc']['warn'],
                                                                                                   ctx.prefix))

        elif joinmessage:
            if not joinmessage['embedded']:
                if not message:
                    message = str(self.bot.settings['default']['join_message_text'])

                if joinmessage['message'] == message:
                    return await ctx.send(_("{0} Your current welcome message is the same as the new one.").format(self.bot.settings['emojis']['misc']['warn']))
                if len(message) > 1000:
                    return await ctx.send(_("{0} Welcome messages can't be longer than 1000 characters. You're {1} character(s) over the limit.").format(self.bot.settings['emojis']['misc']['warn'],
                                                                                                                                                         len(message) - 1000))
                await self.bot.db.execute("UPDATE joinmessage SET message = $1 WHERE guild_id = $2", message, ctx.guild.id)
                self.bot.joinmessage[ctx.guild.id]['message'] = message
                await ctx.send(_("{0} **Successfully set your welcome message to:**\n{1}").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                  message))

            elif joinmessage['embedded']:
                if message:
                    try:
                        jsonify = json.loads(message)
                    except Exception as e:
                        print(e)
                        return await ctx.send(_("{0} Your sent dict is invalid. Please "
                                                "use <https://embedbuilder.nadekobot.me/> to create an embed dict, then paste the code here.").format(self.bot.settings['emojis']['misc']['warn']))
                elif not message:
                    jsonify = self.bot.settings['default']['join_message_embed']

                if joinmessage['message'] == message:
                    return await ctx.send(_("{0} Your current welcome message is the same as the new one.").format(self.bot.settings['emojis']['misc']['warn']))

                welcoming_embed = discord.Embed.from_dict(jsonify)
                if not welcoming_embed:
                    return await ctx.send(_("{0} Your embed seems to be empty. Please "
                                            "use <https://embedbuilder.nadekobot.me/> to create an embed dict, then paste the code here.").format(self.bot.settings['emojis']['misc']['warn']))
                await self.bot.db.execute("UPDATE joinmessage SET message = $1 WHERE guild_id = $2", message, ctx.guild.id)
                self.bot.joinmessage[ctx.guild.id]['message'] = message
                plainText = '' if 'plainText' not in jsonify else _("\n**Plain Text:** {0}").format(jsonify['plainText'])
                await ctx.send(content=_("**Here is your new welcome embed:**{0}").format(plainText), embed=welcoming_embed)

    @welcoming.command(name='toggle',
                       brief='Toggle welcoming messages type')
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @admin(manage_guild=True)
    async def welcoming_toggle(self, ctx):
        """ Toggle welcoming messages between embedded and plain text. """

        joinmessage = self.bot.cache.get(self.bot, 'joinmessage', ctx.guild.id)

        if not joinmessage:
            return await ctx.send(_("{0} You cannot set up welcome messages because they are not enabled!"
                                    "To enable them run `{1}welcoming channel [#channel]`").format(self.bot.settings['emojis']['misc']['warn'],
                                                                                                   ctx.prefix))

        elif joinmessage:
            if joinmessage['embedded']:
                await self.bot.db.execute("UPDATE joinmessage SET embedded = $1, message = $2 WHERE guild_id = $3", False, None, ctx.guild.id)
                self.bot.joinmessage[ctx.guild.id]['embedded'] = False
                self.bot.joinmessage[ctx.guild.id]['message'] = None
                await ctx.send(_("{0} Welcome messages will not be sent in embeds anymore.").format(self.bot.settings['emojis']['misc']['white-mark']))
            elif not joinmessage['embedded']:
                await self.bot.db.execute("UPDATE joinmessage SET embedded = $1, message = $2 WHERE guild_id = $3", True, None, ctx.guild.id)
                self.bot.joinmessage[ctx.guild.id]['embedded'] = True
                self.bot.joinmessage[ctx.guild.id]['message'] = None
                await ctx.send(_("{0} Welcome messages will now be sent in embeds.").format(self.bot.settings['emojis']['misc']['white-mark']))

    @welcoming.command(name='bots',
                       brief="Toggle bot welcoming messages",
                       aliases=['robots', 'bot'])
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @admin(manage_guild=True)
    async def welcoming_bots(self, ctx):
        """ Toggle whether or not bot joins should be logged. """

        joinmessage = self.bot.cache.get(self.bot, 'joinmessage', ctx.guild.id)

        if not joinmessage:
            return await ctx.send(_("{0} You cannot set up welcome messages because they are not enabled!"
                                    "To enable them run `{1}welcoming channel [#channel]`").format(self.bot.settings['emojis']['misc']['warn'],
                                                                                                   ctx.prefix))

        elif joinmessage:
            if joinmessage['log_bots']:
                await self.bot.db.execute("UPDATE joinmessage SET log_bots = $1 WHERE guild_id = $2", False, ctx.guild.id)
                self.bot.joinmessage[ctx.guild.id]['log_bots'] = False
                await ctx.send(_("{0} I will no longer welcome bots.").format(self.bot.settings['emojis']['misc']['white-mark']))
            elif not joinmessage['log_bots']:
                await self.bot.db.execute("UPDATE joinmessage SET log_bots = $1 WHERE guild_id = $2", True, ctx.guild.id)
                self.bot.joinmessage[ctx.guild.id]['log_bots'] = True
                await ctx.send(_("{0} I will now longer welcome bots.").format(self.bot.settings['emojis']['misc']['white-mark']))

    @commands.group(brief='Edit the leaving messages', invoke_without_command=True)
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @admin(manage_guild=True)
    async def leaving(self, ctx):
        """ Setup the leaving messages with this command subcommands """
        await ctx.send_help(ctx.command)

    @leaving.command(name='channel', brief='Set the channel for leaving messages')
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @admin(manage_channels=True)
    async def leaving_channel(self, ctx, *, channel: discord.TextChannel = None):
        """
        Set a channel where leaving messages should be sent to.

        Make sure bot has permissions to send messages in that channel.
        """

        if channel and (not channel.can_send or not channel.permissions_for(ctx.guild.me).embed_links):
            return await ctx.send(_("{0} I'm missing permissions in that channel. Make sure you have given me the correct permissions!").format(self.bot.settings['emojis']['misc']['warn']))

        leavemessages = self.bot.cache.get(self.bot, 'leavemessage', ctx.guild.id)

        if leavemessages and not channel:
            await self.bot.db.execute("DELETE from leavemessage WHERE guild_id = $1", ctx.guild.id)
            self.bot.leavemessage.pop(ctx.guild.id)
            return await ctx.send(_("{0} Leave messages are now disabled.").format(self.bot.settings['emojis']['misc']['white-mark']))
        elif leavemessages and channel:
            await self.bot.db.execute("UPDATE leavemessage SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
            self.bot.leavemessage[ctx.guild.id]['channel'] = channel.id
            return await ctx.send(_("{0} I will now send leave messages in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                         channel.mention))
        elif not leavemessages and not channel:
            return await ctx.send(_("{0} You don't have leave messages enabled in this server."
                                    "\n*Hint: If you want to enable them, you need to provide a channel where they should be sent to*").format(self.bot.settings['emojis']['misc']['warn']))
        elif not leavemessages and channel:
            query = "INSERT INTO leavemessage(guild_id, embedded, log_bots, channel_id, message) VALUES($1, $2, $3, $4, $5)"
            await self.bot.db.execute(query, ctx.guild.id, False, True, channel.id, None)
            self.bot.leavemessage[ctx.guild.id] = {'message': None, 'embedded': False, 'log_bots': True, 'channel': channel.id}
            return await ctx.send(_("{0} Successfully enabled leave messages. I will now send leave messages in {1}.").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                                              channel.mention))

    @leaving.command(name='message',
                     brief="Set the leaving message",
                     aliases=['msg', 'm'])
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @admin(manage_guild=True)
    async def leaving_message(self, ctx, *, message: str = None):
        """ Set the leaving messages in the server

        Passing no message will reset your leaving message to the default one """

        leavemessage = self.bot.cache.get(self.bot, 'leavemessage', ctx.guild.id)

        if not leavemessage:
            return await ctx.send(_("{0} Why are you trying to set up leave messages without having them toggled on? "
                                    "To enable them run `{1}leaving channel [#channel]`").format(self.bot.settings['emojis']['misc']['warn'],
                                                                                                 ctx.prefix))

        elif leavemessage:
            if not leavemessage['embedded']:
                if not message:
                    message = str(self.bot.settings['default']['leave_message_text'])

                if leavemessage['message'] == message:
                    return await ctx.send(_("{0} Your current leave message is the same as the new one.").format(self.bot.settings['emojis']['misc']['warn']))
                if len(message) > 1000:
                    return await ctx.send(_("{0} Leave messages can't be longer than 1000 characters. You're {1} character(s) over the limit.").format(self.bot.settings['emojis']['misc']['warn'],
                                                                                                                                                       len(message) - 1000))
                await self.bot.db.execute("UPDATE leavemessage SET message = $1 WHERE guild_id = $2", message, ctx.guild.id)
                self.bot.leavemessage[ctx.guild.id]['message'] = message
                await ctx.send(_("{0} **Successfully set your leave message to:**\n{1}").format(self.bot.settings['emojis']['misc']['white-mark'],
                                                                                                message))

            elif leavemessage['embedded']:
                if message:
                    try:
                        jsonify = json.loads(message)
                    except Exception as e:
                        print(e)
                        return await ctx.send(_("{0} Your sent dict is invalid. Please "
                                                "use <https://embedbuilder.nadekobot.me/> to create an embed dict and then paste that code.").format(self.bot.settings['emojis']['misc']['warn']))
                elif not message:
                    jsonify = self.bot.settings['default']['leave_message_embed']

                if leavemessage['message'] == message:
                    return await ctx.send(_("{0} Your current leave message is the same as the new one.").format(self.bot.settings['emojis']['misc']['warn']))

                leaving_embed = discord.Embed.from_dict(jsonify)
                if not leaving_embed:
                    return await ctx.send(_("{0} Your embed seems to be empty. Please "
                                            "use <https://embedbuilder.nadekobot.me/> to create an embed dict and then paste that code.").format(self.bot.settings['emojis']['misc']['warn']))
                await self.bot.db.execute("UPDATE leavemessage SET message = $1 WHERE guild_id = $2", message, ctx.guild.id)
                self.bot.leavemessage[ctx.guild.id]['message'] = message
                plainText = '' if 'plainText' not in jsonify else _("\n**Plain Text:** {0}").format(jsonify['plainText'])
                await ctx.send(content=_("**Here is your new leave member embed message:**{0}").format(plainText), embed=leaving_embed)

    @leaving.command(name='toggle',
                     brief='Toggle leaving messages type')
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @admin(manage_guild=True)
    async def leaving_toggle(self, ctx):
        """ Toggle leaving messages between embedded and plain text. """

        leavemessage = self.bot.cache.get(self.bot, 'leavemessage', ctx.guild.id)

        if not leavemessage:
            return await ctx.send(_("{0} Why are you trying to setup leaving messages "
                                    "without having them toggled on? To enable them run `{1}leaving channel [#channel]`").format(self.bot.settings['emojis']['misc']['warn'],
                                                                                                                                 ctx.prefix))

        elif leavemessage:
            if leavemessage['embedded']:
                await self.bot.db.execute("UPDATE leavemessage SET embedded = $1, message = $2 WHERE guild_id = $3", False, None, ctx.guild.id)
                self.bot.leavemessage[ctx.guild.id]['embedded'] = False
                self.bot.leavemessage[ctx.guild.id]['message'] = None
                await ctx.send(_("{0} Leave messages will no longer be sent in embeds.").format(self.bot.settings['emojis']['misc']['white-mark']))
            elif not leavemessage['embedded']:
                await self.bot.db.execute("UPDATE leavemessage SET embedded = $1, message = $2 WHERE guild_id = $3", True, None, ctx.guild.id)
                self.bot.leavemessage[ctx.guild.id]['embedded'] = True
                self.bot.leavemessage[ctx.guild.id]['message'] = None
                await ctx.send(_("{0} Leave messages will now be sent in embeds.").format(self.bot.settings['emojis']['misc']['white-mark']))

    @leaving.command(name='bots',
                     brief="Toggle bot leaving",
                     aliases=['robots', 'bot'])
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    @admin(manage_guild=True)
    async def leaving_bots(self, ctx):
        """ Toggle whether or not bot leaves should be logged. """

        leavemessage = self.bot.cache.get(self.bot, 'leavemessage', ctx.guild.id)

        if not leavemessage:
            return await ctx.send(_("{0} Why are you trying to setup leaving messages "
                                    "without having them toggled on? To enable them run `{1}leaving channel [#channel]`").format(self.bot.settings['emojis']['misc']['warn'],
                                                                                                                                 ctx.prefix))

        elif leavemessage:
            if leavemessage['log_bots']:
                await self.bot.db.execute("UPDATE leavemessage SET log_bots = $1 WHERE guild_id = $2", False, ctx.guild.id)
                self.bot.leavemessage[ctx.guild.id]['log_bots'] = False
                await ctx.send(_("{0} Bot leave messages have been turned off.").format(self.bot.settings['emojis']['misc']['white-mark']))
            elif not leavemessage['log_bots']:
                await self.bot.db.execute("UPDATE leavemessage SET log_bots = $1 WHERE guild_id = $2", True, ctx.guild.id)
                self.bot.leavemessage[ctx.guild.id]['log_bots'] = True
                await ctx.send(_("{0} Bot leave messages have been turned on.").format(self.bot.settings['emojis']['misc']['white-mark']))

    @commands.group(name='joinrole',
                    brief="Toggle role on join",
                    invoke_without_command=True)
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def joinrole(self, ctx):
        """ Setup role on join in your server """
        await ctx.send_help(ctx.command)

    @joinrole.group(name='people',
                    brief='Set role on join for users',
                    aliases=['humans'],
                    invoke_without_command=True)
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def joinrole_people(self, ctx, role: discord.Role = None):
        """ Choose what role will be given to new users """

        await ctx.send_help(ctx.command)

    @joinrole_people.command(name='add',
                             brief='Add a role on join for people',
                             aliases=['a'])
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def joinrole_people_add(self, ctx, *, role: discord.Role):
        """ Add a role to role on join for people """

        joinrole = self.bot.cache.get(self.bot, 'joinrole', ctx.guild.id)
        mod_role = self.bot.cache.get(self.bot, 'mod_role', ctx.guild.id)
        admin_role = self.bot.cache.get(self.bot, 'admin_role', ctx.guild.id)

        if not joinrole:
            return await ctx.send(_("{0} Role on is not enabled in this server, please use "
                                    "`{1}joinrole toggle` to enable it.").format(self.bot.settings['emojis']['misc']['warn'], ctx.prefix))
        elif joinrole:
            if role and role.id in (mod_role, admin_role):
                return await ctx.send(_("{0} You cannot set that role as it is configured as mod or admin role").format(self.bot.settings['emojis']['misc']['warn']))
            if role.position >= ctx.guild.me.top_role.position:
                return await ctx.send(_("{0} The role you're trying to setup is higher in role hierarchy and I cannot access it.").format(
                    self.bot.settings['emojis']['misc']['warn']
                ))
            if role.id in joinrole['people']:
                return await ctx.send(_("{0} That role is already added to role on join list.").format(self.bot.settings['emojis']['misc']['warn']))
            await self.bot.db.execute("INSERT INTO joinrole(guild_id, role) VALUES($1, $2)", ctx.guild.id, role.id)
            if joinrole['people']:
                joinrole['people'].append(role.id)
            elif not joinrole['people']:
                joinrole['people'] = [role.id]

            await ctx.send(_("{0} Added {1} to join role for people.").format(self.bot.settings['emojis']['misc']['white-mark'], role.mention))

    @joinrole_people.command(name='remove',
                             brief='Remove a role on join for people',
                             aliases=['r'])
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def joinrole_people_remove(self, ctx, *, role: discord.Role):
        """ Remove a role from role on join for people """

        joinrole = self.bot.cache.get(self.bot, 'joinrole', ctx.guild.id)
        mod_role = self.bot.cache.get(self.bot, 'mod_role', ctx.guild.id)
        admin_role = self.bot.cache.get(self.bot, 'admin_role', ctx.guild.id)

        if not joinrole:
            return await ctx.send(_("{0} Role on is not enabled in this server, please use "
                                    "`{1}joinrole toggle` to enable it.").format(self.bot.settings['emojis']['misc']['warn'], ctx.prefix))
        elif joinrole:
            if role.id not in joinrole['people']:
                return await ctx.send(_("{0} That role is not added to role on join list.").format(self.bot.settings['emojis']['misc']['warn']))
            await self.bot.db.execute("DELETE FROM joinrole WHERE guild_id = $1 AND role = $2", ctx.guild.id, role.id)
            joinrole['people'].remove(role.id)

            await ctx.send(_("{0} Removed {1} from join role for people.").format(self.bot.settings['emojis']['misc']['white-mark'], role.mention))

    @joinrole_people.command(name='list',
                             brief='See all the roles on join for people',
                             aliases=['l'])
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def joinrole_people_list(self, ctx):
        """ See all the roles for role on join for people """

        joinrole = self.bot.cache.get(self.bot, 'joinrole', ctx.guild.id)

        if not joinrole:
            return await ctx.send(_("{0} Role on is not enabled in this server, please use "
                                    "`{1}joinrole toggle` to enable it.").format(self.bot.settings['emojis']['misc']['warn'], ctx.prefix))
        elif joinrole and joinrole['people']:
            list_of_roles = []
            for num, role in enumerate(joinrole['people'], start=1):
                the_role = ctx.guild.get_role(role)

                list_of_roles.append(_("`[{0}]` {1} ({2})\n").format(num, the_role.mention if the_role else _('Role not found'), role))

            paginator = Pages(ctx,
                              title=_("Role on join for people"),
                              entries=list_of_roles,
                              thumbnail=None,
                              per_page=15,
                              embed_color=self.bot.settings['colors']['embed_color'],
                              show_entry_count=True,
                              author=ctx.author)
            await paginator.paginate()

        elif joinrole and not joinrole['people']:
            return await ctx.send(_("{0} There are no role on join roles for people set.").format(self.bot.settings['emojis']['misc']['warn']))

    @joinrole.group(name='bots',
                    brief='Set role on join for bots',
                    aliases=['robots'],
                    invoke_without_command=True)
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def joinrole_bots(self, ctx):
        """ Manage role on join for bots """

        await ctx.send_help(ctx.command)

    @joinrole_bots.command(name='add',
                           brief='Add a role on join for bots',
                           aliases=['a'])
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def joinrole_bots_add(self, ctx, *, role: discord.Role):
        """ Add a role to role on join for bots """

        joinrole = self.bot.cache.get(self.bot, 'joinrole', ctx.guild.id)
        mod_role = self.bot.cache.get(self.bot, 'mod_role', ctx.guild.id)
        admin_role = self.bot.cache.get(self.bot, 'admin_role', ctx.guild.id)

        if not joinrole:
            return await ctx.send(_("{0} Role on is not enabled in this server, please use "
                                    "`{1}joinrole toggle` to enable it.").format(self.bot.settings['emojis']['misc']['warn'], ctx.prefix))
        elif joinrole:
            if role and role.id in (mod_role, admin_role):
                return await ctx.send(_("{0} You cannot set that role as it is configured as mod or admin role").format(self.bot.settings['emojis']['misc']['warn']))
            if role.position >= ctx.guild.me.top_role.position:
                return await ctx.send(_("{0} The role you're trying to setup is higher in role hierarchy and I cannot access it.").format(
                    self.bot.settings['emojis']['misc']['warn']
                ))
            if role.id in joinrole['bots']:
                return await ctx.send(_("{0} That role is already added to role on join list.").format(self.bot.settings['emojis']['misc']['warn']))
            await self.bot.db.execute("INSERT INTO joinrole(guild_id, botrole) VALUES($1, $2)", ctx.guild.id, role.id)
            if joinrole['bots']:
                joinrole['bots'].append(role.id)
            elif not joinrole['bots']:
                joinrole['bots'] = [role.id]

            await ctx.send(_("{0} Added {1} to join role for bots.").format(self.bot.settings['emojis']['misc']['white-mark'], role.mention))

    @joinrole_bots.command(name='remove',
                           brief='Remove a role on join for bots',
                           aliases=['r'])
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def joinrole_bots_remove(self, ctx, *, role: discord.Role):
        """ Remove a role from role on join for bots """

        joinrole = self.bot.cache.get(self.bot, 'joinrole', ctx.guild.id)
        mod_role = self.bot.cache.get(self.bot, 'mod_role', ctx.guild.id)
        admin_role = self.bot.cache.get(self.bot, 'admin_role', ctx.guild.id)

        if not joinrole:
            return await ctx.send(_("{0} Role on is not enabled in this server, please use "
                                    "`{1}joinrole toggle` to enable it.").format(self.bot.settings['emojis']['misc']['warn'], ctx.prefix))
        elif joinrole:
            if role.id not in joinrole['bots']:
                return await ctx.send(_("{0} That role is not added to role on join list.").format(self.bot.settings['emojis']['misc']['warn']))
            await self.bot.db.execute("DELETE FROM joinrole WHERE guild_id = $1 AND botrole = $2", ctx.guild.id, role.id)
            joinrole['bots'].remove(role.id)

            await ctx.send(_("{0} Removed {1} from join role for bots.").format(self.bot.settings['emojis']['misc']['white-mark'], role.mention))

    @joinrole_bots.command(name='list',
                           brief='See all the roles on join for bots',
                           aliases=['l'])
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def joinrole_bots_list(self, ctx):
        """ See all the roles for role on join for bots """

        joinrole = self.bot.cache.get(self.bot, 'joinrole', ctx.guild.id)

        if not joinrole:
            return await ctx.send(_("{0} Role on is not enabled in this server, please use "
                                    "`{1}joinrole toggle` to enable it.").format(self.bot.settings['emojis']['misc']['warn'], ctx.prefix))
        elif joinrole and joinrole['bots']:
            list_of_roles = []
            for num, role in enumerate(joinrole['bots'], start=1):
                the_role = ctx.guild.get_role(role)

                list_of_roles.append(_("`[{0}]` {1} ({2})\n").format(num, the_role.mention if the_role else _('Role not found'), role))

            paginator = Pages(ctx,
                              title=_("Role on join for bots"),
                              entries=list_of_roles,
                              thumbnail=None,
                              per_page=15,
                              embed_color=self.bot.settings['colors']['embed_color'],
                              show_entry_count=True,
                              author=ctx.author)
            await paginator.paginate()

        elif joinrole and not joinrole['bots']:
            return await ctx.send(_("{0} There are no role on join roles for bots set.").format(self.bot.settings['emojis']['misc']['warn']))

    @joinrole.command(name='toggle',
                      brief='Toggle role on join',
                      aliases=['tog'])
    @admin(manage_roles=True)
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def joinrole_toggle(self, ctx):
        """ Toggle role on join on and off """

        joinrole = self.bot.cache.get(self.bot, 'joinrole', ctx.guild.id)

        if not joinrole:
            await self.bot.db.execute("INSERT INTO joinrole(guild_id) VALUES($1)", ctx.guild.id)
            self.bot.joinrole[ctx.guild.id] = {'people': [], 'bots': []}
            await ctx.send(_("{0} Role on join was toggled on, you can now set the roles using "
                             "`{1}joinrole [people|bots] [add|remove] <role>`").format(self.bot.settings['emojis']['misc']['white-mark'], ctx.prefix))
        else:
            await self.bot.db.execute("DELETE FROM joinrole WHERE guild_id = $1", ctx.guild.id)
            self.bot.joinrole.pop(ctx.guild.id)
            await ctx.send(_("{0} I've successfuly disabled role on join.").format(self.bot.settings['emojis']['misc']['white-mark']))

    @commands.command(name='muterole',
                      brief='Set a custom mute role',
                      aliases=['silentrole'])
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def muterole(self, ctx, arg: typing.Union[discord.Role, str]):
        """ Setup a custom mute role in your server

        You can also reset the mute role by using argument `reset`"""

        mute_role = self.bot.cache.get(self.bot, 'mute_role', ctx.guild.id)

        if isinstance(arg, str):
            if arg == "reset" and mute_role:
                await self.bot.db.execute("DELETE FROM muterole WHERE guild_id = $1", ctx.guild.id)
                self.bot.mute_role.pop(ctx.guild.id)
                await ctx.send(_("{0} The mute role has been reset.").format(self.bot.settings['emojis']['misc']['white-mark']))
            elif arg == "reset" and not mute_role:
                await ctx.send(_("{0} You do not have a mute role set up.").format(self.bot.settings['emojis']['misc']['warn']))
            else:
                return await ctx.send(_("{0} That role was not found! If you're trying to reset the mute role, you can use `reset` as the argument.").format(self.bot.settings['emojis']['misc']['warn']))
        if isinstance(arg, discord.Role):
            if arg.position >= ctx.guild.me.top_role.position:
                return await ctx.send(_("{0} The role you're trying to set as the mute role is higher than me in the role hierarchy!\n"
                                        "Please move the role lower in the hierarchy or choose a role in the hierarchy.").format(self.bot.settings['emojis']['misc']['warn']))
            if arg.permissions.send_messages:
                return await ctx.send(_("{0} The role you're trying to set as the mute role has the send messages permission.\n"
                                        "You can only set up roles without the send messages permission.").format(self.bot.settings['emojis']['misc']['warn']))
            if not mute_role:
                await self.bot.db.execute("INSERT INTO muterole(guild_id, role_id) VALUES($1, $2)", ctx.guild.id, arg.id)
                self.bot.mute_role[ctx.guild.id] = arg.id
                await ctx.send(_("{0} Set the muted role to {1}").format(self.bot.settings['emojis']['misc']['white-mark'], arg.mention))
            elif mute_role:
                await self.bot.db.execute("UPDATE muterole SET role_id = $1 WHERE guild_id = $2", arg.id, ctx.guild.id)
                self.bot.mute_role[ctx.guild.id] = arg.id
                await ctx.send(_("{0} Updated the muted role to {1}").format(self.bot.settings['emojis']['misc']['white-mark'], arg.mention))

    @commands.command(name='modrole',
                      brief='Set a custom mod role',
                      aliases=['moderatorrole'])
    @admin(administrator=True)
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def modrole(self, ctx, arg: typing.Union[discord.Role, str]):
        """ Setup a custom mod role in your server

        You can also reset the mod role by using argument `reset`"""

        mod_role = self.bot.cache.get(self.bot, 'mod_role', ctx.guild.id)
        joinrole = self.bot.cache.get(self.bot, 'joinrole', ctx.guild.id)

        if isinstance(arg, str):
            if arg == "reset" and mod_role:
                await self.bot.db.execute("DELETE FROM modrole WHERE guild_id = $1", ctx.guild.id)
                self.bot.mod_role.pop(ctx.guild.id)
                await ctx.send(_("{0} Successfully reset the moderator role.").format(self.bot.settings['emojis']['misc']['white-mark']))
            elif arg == "reset" and not mod_role:
                await ctx.send(_("{0} You don't have a custom moderator role setup.").format(self.bot.settings['emojis']['misc']['warn']))
            else:
                return await ctx.send(_("{0} Role was not found, if you're trying to reset the "
                                        "custom moderator role, you can use `reset` arg.").format(self.bot.settings['emojis']['misc']['warn']))
        if isinstance(arg, discord.Role):
            if not arg.permissions.manage_messages:
                return await ctx.send(_("{0} Due to safety reasons, moderator role must at least have manage messages permissions").format(
                    self.bot.settings['emojis']['misc']['warn']
                ))
            if joinrole and arg.id in (joinrole['people'] or joinrole['bots']):
                return await ctx.send(_("{0} You cannot set that role as it is given to new members").format(self.bot.settings['emojis']['misc']['warn']))
            if not mod_role:
                await self.bot.db.execute("INSERT INTO modrole(guild_id, role) VALUES($1, $2)", ctx.guild.id, arg.id)
                self.bot.mod_role[ctx.guild.id] = arg.id
                await ctx.send(_("{0} Set a custom moderator role to {1}").format(self.bot.settings['emojis']['misc']['white-mark'], arg.mention))
            elif mod_role:
                await self.bot.db.execute("UPDATE modrole SET role = $1 WHERE guild_id = $2", arg.id, ctx.guild.id)
                self.bot.mod_role[ctx.guild.id] = arg.id
                await ctx.send(_("{0} Changed a custom moderator role to {1}").format(self.bot.settings['emojis']['misc']['white-mark'], arg.mention))

    @commands.command(name='adminrole',
                      brief='Set a custom admin role',
                      aliases=['administratorrole'])
    @admin(administrator=True)
    @commands.guild_only()
    @commands.cooldown(1, 10, commands.BucketType.member)
    async def adminrole(self, ctx, arg: typing.Union[discord.Role, str]):
        """ Setup a custom admin role in your server

        You can also reset the admin role by using argument `reset`"""

        admin_role = self.bot.cache.get(self.bot, 'admin_role', ctx.guild.id)
        joinrole = self.bot.cache.get(self.bot, 'joinrole', ctx.guild.id)

        if isinstance(arg, str):
            if arg == "reset" and admin_role:
                await self.bot.db.execute("DELETE FROM adminrole WHERE guild_id = $1", ctx.guild.id)
                self.bot.admin_role.pop(ctx.guild.id)
                await ctx.send(_("{0} I've reset your admin role.").format(self.bot.settings['emojis']['misc']['white-mark']))
            elif arg == "reset" and not admin_role:
                await ctx.send(_("{0} You don't have a custom admin role setup.").format(self.bot.settings['emojis']['misc']['warn']))
            else:
                return await ctx.send(_("{0} Role was not found, if you're trying to reset the "
                                        "custom admin role, you can use `reset` arg.").format(self.bot.settings['emojis']['misc']['warn']))
        if isinstance(arg, discord.Role):
            if not arg.permissions.ban_members:
                return await ctx.send(_("{0} Due to safety reasons, admin role must at least have ban members permissions").format(
                    self.bot.settings['emojis']['misc']['warn']
                ))
            if joinrole and arg.id in (joinrole['people'] or joinrole['bots']):
                return await ctx.send(_("{0} You cannot set that role as it is given to new members").format(self.bot.settings['emojis']['misc']['warn']))
            if not admin_role:
                await self.bot.db.execute("INSERT INTO adminrole(guild_id, role) VALUES($1, $2)", ctx.guild.id, arg.id)
                self.bot.admin_role[ctx.guild.id] = arg.id
                await ctx.send(_("{0} Set a custom admin role to {1}").format(self.bot.settings['emojis']['misc']['white-mark'], arg.mention))
            elif admin_role:
                await self.bot.db.execute("UPDATE adminrole SET role = $1 WHERE guild_id = $2", arg.id, ctx.guild.id)
                self.bot.admin_role[ctx.guild.id] = arg.id
                await ctx.send(_("{0} Changed a custom admin role to {1}").format(self.bot.settings['emojis']['misc']['white-mark'], arg.mention))

    @commands.command(name='disable-command',
                      brief='Disable a command in the server',
                      aliases=['disablecommand', 'discmd'])
    @admin(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def disable_command(self, ctx, *, command: str):
        """ Disable commands in the server """

        cmd = self.bot.get_command(command)

        if not cmd:
            return await ctx.send(_("{0} {1} command was not found.").format(
                self.bot.settings['emojis']['misc']['warn'], command
            ))

        if await is_guild_disabled(ctx, cmd):
            return await ctx.send(_("{0} That command is already disabled.").format(self.bot.settings['emojis']['misc']['warn']))

        command = cmd

        if command.parent:
            if not command.name:
                self.bot.guild_disabled[f"{str(command.parent)}, {ctx.guild.id}"] = str(command.parent)
                await self.bot.db.execute("INSERT INTO guild_disabled(guild_id, command) VALUES($1, $2)", ctx.guild.id, str(command.parent))
                await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command.parent}` and its corresponding subcommands were successfully disabled")
            elif command.name:
                self.bot.guild_disabled[f"{str(f'{command.parent} {command.name}')}, {ctx.guild.id}"] = str(commands.parent)
                await self.bot.db.execute("INSERT INTO guild_disabled(guild_id, command) VALUES($1, $2)", ctx.guild.id, str(f"{command.parent} {command.name}"))
                await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command.parent} {command.name}` and its corresponding subcommands were successfully disabled")
        elif not command.parent:
            self.bot.guild_disabled[f"{str(command)}, {ctx.guild.id}"] = str(command.name)
            await self.bot.db.execute("INSERT INTO guild_disabled(guild_id, command) VALUES($1, $2)", ctx.guild.id, str(command.name))
            await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command}` was successfully disabled")

    @commands.command(name='enable-command',
                      brief='Enable a command in the server',
                      aliases=['enablecommand', 'enbcmd'])
    @admin(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def enable_command(self, ctx, *, command: str):
        """ Enable commands in the server """

        cmd = self.bot.get_command(command)

        if not cmd:
            return await ctx.send(_("{0} {1} command was not found.").format(
                self.bot.settings['emojis']['misc']['warn'], command
            ))

        if not await is_guild_disabled(ctx, cmd):
            return await ctx.send(_("{0} That command is not disabled.").format(self.bot.settings['emojis']['misc']['warn']))

        command = cmd

        if command.parent:
            if not command.name:
                self.bot.guild_disabled.pop(f"{str(command.parent)}, {ctx.guild.id}")
                await self.bot.db.execute("DELETE FROM guild_disabled WHERE command = $1 AND guild_id = $2", str(command.parent), ctx.guild.id)
                await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command.parent}` and its corresponding subcommands were successfully re-enabled")
            elif command.name:
                self.bot.guild_disabled.pop(f"{str(f'{command.parent} {command.name}')}, {ctx.guild.id}")
                await self.bot.db.execute("DELETE FROM guild_disabled WHERE command = $1 AND guild_id = $2", str(f"{command.parent} {command.name}"), ctx.guild.id)
                await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command.parent} {command.name}` and its corresponding subcommands were successfully re-enabled")
        elif not command.parent:
            self.bot.guild_disabled.pop(f"{str(command)}, {ctx.guild.id}")
            await self.bot.db.execute("DELETE FROM guild_disabled WHERE command = $1 AND guild_id = $2", str(command), ctx.guild.id)
            await ctx.send(f"{self.bot.settings['emojis']['misc']['white-mark']} | `{command}` was successfully re-enabled")

    @commands.command(name='disable-category',
                      brief='Disable category in the server',
                      aliases=['disable-cog', 'disablecog'])
    @admin(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def disable_category(self, ctx, *, category: str):
        """ Disable category you don't want people to use in the server """

        cog = self.bot.get_cog(category.title())

        if not cog:
            return await ctx.send(_("{0} {1} category was not found.").format(
                self.bot.settings['emojis']['misc']['warn'], category.title()
            ))

        cant_disable = ["Help", "Events", "CommandError", "Logging", 'Tasks', "AutomodEvents", 'Management', 'Owner', 'Staff']
        if cog.qualified_name in cant_disable:
            return await ctx.send(_("{0} You can't disable that category!").format(self.bot.settings['emojis']['misc']['warn']))

        if self.bot.cache.get(self.bot, 'cog_disabled', f"{str(ctx.guild.id)}, {str(cog.qualified_name)}"):
            return await ctx.send(_("{0} That category is already disabled.").format(self.bot.settings['emojis']['misc']['warn']))

        self.bot.cog_disabled[f"{str(ctx.guild.id)}, {str(cog.qualified_name)}"] = str(cog.qualified_name)
        await self.bot.db.execute("INSERT INTO cog_disabled(guild_id, cog) VALUES($1, $2)", ctx.guild.id, cog.qualified_name)
        await ctx.send(_("{0} Category {1} was successfully disabled").format(
            self.bot.settings['emojis']['misc']['white-mark'], cog.qualified_name
        ))

    @commands.command(name='enable-category',
                      brief='Enable category in the server',
                      aliases=['enable-cog', 'enablecog'])
    @admin(administrator=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def enable_category(self, ctx, *, category: str):
        """ Enable category which you've previously disbled """

        cog = self.bot.get_cog(category.title())

        if not cog:
            return await ctx.send(_("{0} {1} category was not found.").format(
                self.bot.settings['emojis']['misc']['warn'], category.title()
            ))

        if not self.bot.cache.get(self.bot, 'cog_disabled', f"{str(ctx.guild.id)}, {str(cog.qualified_name)}"):
            return await ctx.send(_("{0} That category is not disabled.").format(self.bot.settings['emojis']['misc']['warn']))

        self.bot.cog_disabled.pop(f"{str(ctx.guild.id)}, {str(cog.qualified_name)}")
        await self.bot.db.execute("DELETE FROM cog_disabled WHERE cog = $1 AND guild_id = $2", cog.qualified_name, ctx.guild.id)
        await ctx.send(_("{0} Category {1} was successfully re-enabled").format(
            self.bot.settings['emojis']['misc']['white-mark'], cog.qualified_name
        ))

    @commands.group(name='reaction-roles',
                    brief="Setup reaction roles in the server",
                    aliases=['rr', 'rroles', 'reactroles', 'reactionroles'],
                    invoke_without_command=True)
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True, manage_messages=True)
    @commands.guild_only()
    async def reaction_roles(self, ctx):
        await ctx.send_help(ctx.command)

    @reaction_roles.command(name='new',
                            brief="Create a new reaction role",
                            aliases=['add'])
    @admin(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True, manage_messages=True)
    @commands.max_concurrency(1, commands.cooldowns.BucketType.guild, wait=False)
    @commands.guild_only()
    async def reaction_roles_add(self, ctx):
        try:
            def check(m):
                return m.author == ctx.author and m.channel.id == ctx.channel.id

            first_loop, first_part, role_dict, channel = True, 0, {}, None
            while first_loop:
                msg = await ctx.channel.send(_("Do you want me to use an existing message or a new one? `new` | `existing` | `n` | `e` | `old` | `cancel` *You have 60 seconds*"))
                first_response = await self.bot.wait_for('message', check=check, timeout=60.0)

                if first_response.content.lower() in ['new', 'n']:
                    first_part = 1
                    first_loop = False
                elif first_response.content.lower() in ['existing', 'e', 'old']:
                    first_part = 2
                    first_loop = False
                elif first_response.content.lower() == 'cancel':
                    first_loop = False
                    return await msg.edit(content=_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                else:
                    first_loop = True
                    await msg.edit(content=_("Invalid answer, try again."))

            await msg.delete()
            if first_part == 1:
                embed_loop, embed_part, embed, second_part = True, 0, False, 0
                while embed_loop:
                    msg1 = await ctx.channel.send(_("Should the message be an embed? `yes` | `y` | `no` | `n` | `cancel`"))
                    second_response = await self.bot.wait_for('message', check=check, timeout=60.0)
                    if second_response.content.lower() in ['yes', 'y']:
                        embed_loop, embed = False, True
                        embed_part = 1
                    elif second_response.content.lower() in ['no', 'n']:
                        embed_loop = False
                        embed_part = 2
                    elif second_response.content.lower() == 'cancel':
                        embed_loop = False
                        return await msg1.edit(content=_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                    else:
                        embed_loop = True
                        await msg1.edit(content=_("Invalid answer, try again."))
                channel_loop = True
                await msg1.delete()
                while channel_loop:
                    msg2 = await ctx.channel.send(_("What channel should I send the message to?"))
                    channel_response = await self.bot.wait_for('message', check=check, timeout=60.0)
                    if channel_response.content.lower() == 'cancel':
                        channel_loop = False
                        return await msg1.edit(content=_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                    try:
                        channel = await commands.TextChannelConverter().convert(ctx, channel_response.content)
                        if not channel.can_send:
                            await msg2.edit(content=_("I can't send messages in that channel, please give me permissions to send messages in that channel or choose another channel."))
                        elif embed and not channel.permissions_for(ctx.guild.me).embed_links:
                            await msg2.edit(content=_("I can't embed links in that channel, please give me permissions to embed links there or choose another channel in which I can embed links."))
                        else:
                            channel_loop = False
                            second_part = 1
                    except Exception:
                        await msg2.edit(content=_("Can't find that channel, if that's even a channel."))
            elif first_part == 2:
                embed, message_loop, second_part = False, True, 0
                while message_loop:
                    msg1 = await ctx.channel.send(_("Send the link of the message you want to use for reaction roles."))
                    second_response = await self.bot.wait_for('message', check=check, timeout=60.0)
                    if second_response.content.lower() == 'cancel':
                        message_loop = False
                        return await msg1.edit(content=_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                    elif second_response.content.lower().startswith('https://'):
                        url = second_response.content.split('/')
                        try:
                            channel = ctx.guild.get_channel(int(url[5]))
                            message = await channel.fetch_message(int(url[6]))
                            second_part, message_loop = 1, False
                        except Exception as e:
                            await msg1.edit(content=_("Can't find that message, please make sure the link is valid and I can see the channel, message history."))
                    else:
                        embed_loop = True
                        await msg1.edit(content=_("Invalid answer, try again."))
                await msg1.delete()
            if second_part == 1:
                reactions_loop = True
                while reactions_loop:
                    third_loop, third_part, emoji = True, 0, None
                    while third_loop:
                        msg2 = await ctx.channel.send(_("Please send a **single** emoji that you'd like to use."))
                        third_response = await self.bot.wait_for('message', check=check, timeout=60.0)

                        if third_response.content.lower() == 'cancel':
                            third_loop, reactions_loop = False, False
                            return await msg1.edit(content=_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                        else:
                            if third_response.content in role_dict:
                                third_loop = True
                                await msg2.edit(content=_("That emoji is already being used for reaction roles"))
                            else:
                                try:
                                    await msg2.add_reaction(third_response.content)
                                    emoji, third_part, third_loop = third_response.content, 1, False
                                    await msg2.delete()
                                except Exception:
                                    third_loop = True
                                    await msg2.edit(content=_("Invalid emoji, try again."))

                    if third_part == 1:
                        role_loop, role_part, role = True, 0, None
                        msg3 = await ctx.channel.send(_("Please send a role that you'd like to assign to emoji - {0}").format(emoji))
                        role_response = await self.bot.wait_for('message', check=check, timeout=60.0)
                        if role_response.content.lower() == 'cancel':
                            role_loop, reactions_loop = False, False
                            return await msg3.edit(content=_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                        else:
                            try:
                                role = await commands.RoleConverter().convert(ctx, role_response.content)
                                if role == ctx.guild.default_role:
                                    raise Exception()
                                if str(role.id) in str(role_dict):
                                    await msg3.edit(content=_("That role is already used in the reaction role, please choose another role."), delete_after=15)
                                elif not str(role.id) in str(role_dict):
                                    if role.position < ctx.guild.me.top_role.position:
                                        role_loop, role_part = False, 1
                                        role_dict[emoji] = role.id
                                        await msg3.delete()
                                    else:
                                        await msg3.edit(content=_("The role you've provided is higher in the role hierarchy, please make sure I can access the role."))
                            except Exception as e:
                                await msg3.edit(content=_("Invalid role, try again."))

                    if role_part == 1:
                        continue_roles, continue_part = True, 0

                        if len(role_dict) >= 20:
                            continue_part, continue_roles, reactions_loop = 1, False, False

                        while continue_roles:
                            msg4 = await ctx.channel.send(_("Do you wish to add more reaction roles? `yes` | `y` | `n` | `no` | `cancel` to cancel the command"))
                            is_continue = await self.bot.wait_for('message', check=check, timeout=60.0)
                            if is_continue.content.lower() in ['yes', 'y']:
                                continue_roles = False
                            elif is_continue.content.lower() in ['no', 'n']:
                                continue_roles, reactions_loop, continue_part = False, False, 1
                                await msg4.delete()
                            elif is_continue.content.lower() == 'cancel':
                                continue_roles, reactions_loop = False, False
                                return await msg4.edit(content=_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                            else:
                                continue_roles = True
                                await msg4.edit(content=_("Invalid answer, try again."))
                if continue_part == 1:
                    check_required_role, the_role = True, None
                    while check_required_role:
                        required_role, required_part = None, 0
                        msg5 = await ctx.channel.send(_("Do you only want users with certain roles to access the reaction roles? `yes` | `y` | `n` | `no` | `cancel` to cancel the command"))
                        is_continue = await self.bot.wait_for('message', check=check, timeout=60.0)
                        if is_continue.content.lower() in ['yes', 'y']:
                            check_required_role, required_part = False, 1
                        elif is_continue.content.lower() in ['no', 'n']:
                            check_required_role, required_part = False, 0
                            await msg5.delete()
                        elif is_continue.content.lower() == 'cancel':
                            check_required_role = False
                            return await msg5.edit(content=_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                        else:
                            continue_roles = True
                            await msg5.edit(content=_("Invalid answer, try again."))
                    if required_part == 1:
                        the_role_loop, the_role_part = True, None
                        while the_role_loop:
                            msg6 = await ctx.channel.send(_("What role do users need in order to access the reaction roles?"))
                            is_continue = await self.bot.wait_for('message', check=check, timeout=60.0)

                            if is_continue.content.lower() == 'cancel':
                                check_required_role = False
                                return await msg6.edit(content=_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                            try:
                                role = await commands.RoleConverter().convert(ctx, is_continue.content)
                                if str(role.id) in str(role_dict):
                                    await msg6.edit(content=_("That role is already used in the reaction role, please choose another role."), delete_after=15)
                                else:
                                    the_role, the_role_loop, the_role_part = role.id, False, 1
                                    await msg6.delete()
                            except Exception as e:
                                print(e)
                                await msg6.edit(content=_("Invalid role, try again."))
                    else:
                        pass
                    if len(role_dict) > 1:
                        max_roles_loop, max_roles = True, 0
                        while max_roles_loop:
                            msg7 = await ctx.channel.send(_("How many roles should users be able to get from the reaction role? Send {0} if all.").format(len(role_dict)))
                            is_continue = await self.bot.wait_for('message', check=check, timeout=60.0)

                            if is_continue.content.lower() == 'cancel':
                                check_required_role = False
                                return await msg7.edit(content=_("Cancelling the command. Deleting this message in 15 seconds"), delete_after=15)
                            try:
                                num = int(is_continue.content)
                                max_roles, max_roles_loop = num, False
                                await msg7.edit(content=_("Set the max number of roles to **{0}**").format(num))
                            except Exception as e:
                                print(e)
                                await msg7.edit(content=_("Answer must be a number or `cancel` to cancel."))
                    if first_part == 1:
                        if embed_part == 1:
                            embed = discord.Embed(color=self.bot.settings['colors']['embed_color'], title='Reaction Roles')
                            embed.description = _("**Available Roles:**")
                            for item in role_dict:
                                role = ctx.guild.get_role(role_dict[item])
                                embed.description += f"\n{item} - {role.mention}"
                            embed.description += _("\n\n*React to the reactions below to get the corresponding roles.*")
                            message = await channel.send(embed=embed)
                        elif embed_part == 2:
                            message = _("**Available Roles:**")
                            for item in role_dict:
                                role = ctx.guild.get_role(role_dict[item])
                                message += f"\n{item} - {role.mention}"
                            message += _("\n\n*React to the reactions below to get the corresponding roles.*")
                            message = await channel.send(message)

                    try:
                        roles_list = []
                        for reaction in role_dict:
                            await message.add_reaction(reaction)
                            roles_list.append(ctx.guild.get_role(role_dict[reaction]))
                    except Exception as e:
                        self.bot.dispatch('silent_error', ctx, e)
                        return await ctx.send(_("{0} Something failed while adding the reactions, did you deleted the message?"))
                    q = "INSERT INTO reactionroles(guild_id, channel_id, message_id, the_dict, required_role_id, max_roles) VALUES($1, $2, $3, $4, $5, $6)"
                    await self.bot.db.execute(q, ctx.guild.id, channel.id, message.id, str(role_dict), the_role, max_roles if len(role_dict) > 1 else None)
                    self.bot.rr[message.id] = {'guild': ctx.guild.id, 'channel': channel.id, 'dict': role_dict, 'required_role': the_role, 'max_roles': max_roles if len(role_dict) > 1 else None}

                    embed = discord.Embed(color=self.bot.settings['colors']['embed_color'], title=_("Reaction Roles Setup Completed"))
                    embed.description = _("Reaction roles setup for [**message**]({0}) was successfully completed.\n\n"
                                          "**Reactions:** {1}\n**Roles:** {2}\n**Roles limit:** {3}\n**Required Role:** {4}").format(
                                              message.jump_url, ', '.join([x for x in role_dict]), ', '.join([x.mention for x in roles_list]),
                                              max_roles if len(role_dict) > 1 else len(role_dict), ctx.guild.get_role(the_role)
                                          )

                    await ctx.channel.send(embed=embed)

        except asyncio.TimeoutError:
            return await ctx.channel.send(_("Timed out, please re-run the command."))

    @reaction_roles.command(name='list', aliases=['l'], brief="Get a list of reaction roles in the server")
    @admin(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def reaction_roles_list(self, ctx):
        """ Get a list of reaction roles in the server """

        check = await self.bot.db.fetch("SELECT * FROM reactionroles WHERE guild_id = $1", ctx.guild.id)

        if not check:
            raise commands.BadArgument(_("No reaction roles are setup in this server."))

        list_of_messageids = []
        for data in check:
            list_of_messageids.append(data['message_id'])

        list_of_reactionroles = []
        for messageid in list_of_messageids:
            cache = self.bot.cache.get(self.bot, 'rr', messageid)

            if not cache:
                await self.bot.db.execute("DELETE FROM reactionroles WHERE message_id = $1", messageid)
                continue

            roles = []
            for role in cache['dict']:
                roles.append(ctx.guild.get_role(cache['dict'][role]))

            channel = ctx.guild.get_channel(cache['channel'])
            message = messageid
            with suppress(Exception):
                msg = await channel.fetch_message(messageid)
                message = _("[Jump URL]({0})").format(msg.jump_url)

            list_of_reactionroles.append(_("**Message:** {0}\n**Channel:** {1}\n**Reactions:** {2}\n**Roles:** {3}\n**Roles limit:** {4}\n**Required role:** {5}\n\n").format(
                message, channel.mention if channel else _('Deleted'), ', '.join([x for x in cache['dict']][:10]) + f" (+{len(cache['dict']) - 10})" if len(cache['dict']) > 10 else ', '.join([x for x in cache['dict']]),
                ', '.join([x.mention for x in roles][:10]) + f" (+{len(roles) - 10})" if len(roles) > 10 else ', '.join([x.mention for x in roles]), cache['max_roles'],
                ctx.guild.get_role(cache['required_role']).mention if ctx.guild.get_role(cache['required_role']) else None
            ))

        paginator = Pages(ctx,
                          title=_("Reaction roles in {0}").format(ctx.guild.name),
                          entries=list_of_reactionroles,
                          thumbnail=None,
                          per_page=2,
                          embed_color=self.bot.settings['colors']['embed_color'],
                          show_entry_count=True,
                          author=ctx.author)
        await paginator.paginate()

    @reaction_roles.command(name='delete', aliases=['del'], brief="Delete reaction roles in the server")
    @admin(manage_roles=True)
    @commands.cooldown(1, 10, commands.BucketType.member)
    @commands.guild_only()
    async def reaction_roles_delete(self, ctx, message_id: str):
        """ Delete reaction roles in the server """
        if not message_id.isdigit():
            raise commands.BadArgument(_("Message ID must not include letters, only numbers"))

        get_menu = self.bot.cache.get(self.bot, 'rr', int(message_id))

        if not get_menu:
            raise commands.BadArgument(_("Reaction role for that message doesn't exist. Please use `{0}reaction-roles list` to get a list of all the reaction roles").format(ctx.prefix))

        await self.bot.db.execute("DELETE FROM reactionroles WHERE message_id = $1 AND guild_id = $2", int(message_id), ctx.guild.id)
        self.bot.rr.pop(int(message_id))
        channel = ctx.guild.get_channel(get_menu['channel'])
        message = message_id
        if channel:
            try:
                message = await channel.fetch_message(int(message_id))
                await message.clear_reactions()
                message = f"<{message.jump_url}>"
            except Exception:
                pass

        await ctx.send(_("{0} Successfully deleted reaction roles for message {1}").format(self.bot.settings['emojis']['misc']['white-mark'], message))


def setup(bot):
    bot.add_cog(Manage(bot))
