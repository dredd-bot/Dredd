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
import json
import asyncio

from discord.ext import commands
from datetime import datetime

from utils import btime, default, publicflags
from db.cache import CacheManager as CM


class Logging(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.help_icon = ''
        self.big_icon = ''

    def placeholder_replacer(self, emb_dict, member):
        for thing in emb_dict:
            if isinstance(emb_dict[thing], str):
                emb_dict[thing] = emb_dict[thing].replace("{{member.name}}", member.name)
                emb_dict[thing] = emb_dict[thing].replace("{{member.id}}", str(member.id))
                emb_dict[thing] = emb_dict[thing].replace("{{member.tag}}", str(member))
                emb_dict[thing] = emb_dict[thing].replace("{{member.mention}}", member.mention)
                emb_dict[thing] = emb_dict[thing].replace("{{server.name}}", member.guild.name)
                emb_dict[thing] = emb_dict[thing].replace("{{server.members}}", str(member.guild.member_count))
        return emb_dict

    async def insert_new_case(self, mod_id, channel, case_num, user_id, guild_id, action, reason):
        query1 = 'INSERT INTO modlog(mod_id, channel_id, case_num, message_id, user_id, guild_id, action, reason) VALUES($1, $2, $3, $4, $5, $6, $7, $8)'
        await self.bot.db.execute(query1, mod_id, channel, case_num if case_num else 1, None,
                                  user_id, guild_id, action, reason)

    async def update_old_case(self, message_id, guild_id, case_num):
        await self.bot.db.execute("UPDATE modlog SET message_id = $1 WHERE guild_id = $2 AND case_num = $3", message_id, guild_id, case_num if case_num else 1)
        await self.bot.db.execute("UPDATE modlog SET case_num = $1 WHERE guild_id = $2 AND message_id = $3", case_num if case_num else 1, guild_id, message_id)
        await self.bot.db.execute("UPDATE cases SET case_num = $1 + 1 WHERE guild_id = $2", case_num if case_num else 1, guild_id)
        self.bot.case_num[guild_id] += 1

    @commands.Cog.listener()
    async def on_member_join(self, member):
        self.bot.dispatch('member_joinlog', member)
        self.bot.dispatch('join_message', member)
        self.bot.dispatch('joinrole', member)

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        self.bot.dispatch('member_leavelog', member)
        self.bot.dispatch('leave_message', member)
        self.bot.dispatch('member_kick', member.guild, member)

    @commands.Cog.listener()
    async def on_message_edit(self, before, after):
        if not before.guild:
            return

        message_edits = CM.get(self.bot, 'messageedits', before.guild.id)

        if not message_edits:
            return

        if before.author.bot:
            return

        if before.content != after.content:
            ctx = await self.bot.get_context(before)
            ctx2 = await self.bot.get_context(after)
            if ctx.valid and ctx2.valid:
                return

            editlog_channel = before.guild.get_channel(message_edits)
            editlog_embed = discord.Embed(color=self.bot.settings['colors']['update_color'], timestamp=datetime.utcnow())
            editlog_embed.title = _("{0} Message Edited").format(self.bot.settings['emojis']['logs']['msgedit'])
            editlog_embed.description = _("**User:** {0} `{1}`\n**Channel:** {2} `#{3}`\n[Jump to message]({4})").format(before.author.mention, before.author,
                                                                                                                         before.channel.mention, before.channel.name,
                                                                                                                         before.jump_url)

            editlog_embed.add_field(name=_("**Before:**"),
                                    value=before.content[:1000] + '...' if len(before.content) > 1000 else before.content,
                                    inline=False)
            editlog_embed.add_field(name=_("**After:**"),
                                    value=after.content[:1000] + '...' if len(after.content) > 1000 else after.content)
            editlog_embed.set_footer(text=_("User ID: {0}").format(after.author.id))

            try:
                await editlog_channel.send(embed=editlog_embed)
            except Exception as e:
                await default.background_error(self, '`message edit`', e, before.guild, editlog_channel)

    @commands.Cog.listener()
    async def on_message_delete(self, message):
        if not message.guild:
            return

        message_deletes = CM.get(self.bot, 'messagedeletes', message.guild.id)

        if not message_deletes:
            return

        if message.author.bot or message.author not in message.guild.members:
            return

        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        deletelog_channel = message.guild.get_channel(message_deletes)
        deletelog_embed = discord.Embed(color=self.bot.settings['colors']['deny_color'], timestamp=datetime.utcnow())
        deletelog_embed.title = _("{0} Message Deleted").format(self.bot.settings['emojis']['logs']['msgdelete'])
        deletelog_embed.description = _("**User:** {0} `{1}`\n**Channel:** {2} `#{3}`").format(message.author.mention, message.author,
                                                                                               message.channel.mention, message.channel.name)
        if message.content:
            if message.stickers != []:
                message.content = message.content[:-len(_("\n*Sticker* - {0}").format(message.stickers[0].name))]

            if message.content:
                deletelog_embed.add_field(name=_("**Message:**"),
                                          value=message.content[:1000] + '...' if len(message.content) > 1000 else message.content,
                                          inline=False)
        if message.attachments != []:
            deletelog_embed.add_field(name=_("**Attachments:**"),
                                      value=message.attachments[0].url)
        if message.stickers != []:
            deletelog_embed.add_field(name=_("**Sticker:**"),
                                      value=f"{message.stickers[0].name} - `{message.stickers[0].description}`")
        deletelog_embed.set_footer(text=_("User ID: {0}").format(message.author.id))

        try:
            await deletelog_channel.send(embed=deletelog_embed)
        except Exception as e:
            await default.background_error(self, '`message delete`', e, message.guild, deletelog_channel)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        member_update = CM.get(self.bot, 'memberlog', before.guild.id)

        if not member_update:
            return
        if before.bot:
            return

        if before.nick != after.nick:
            nick_channel = before.guild.get_channel(member_update)
            nick_embed = discord.Embed(color=self.bot.settings['colors']['log_color'],
                                       timestamp=datetime.utcnow())
            nick_embed.set_author(name=_("{0} changed their nickname").format(before), icon_url=before.avatar_url)
            nick_embed.title = _("{0} Nickname Changed").format(self.bot.settings['emojis']['logs']['memberedit'])
            nick_embed.description = _("**Member:** {0} `{1}`\n\n**Before:** {2}\n**After:** {3}").format(before.mention, before,
                                                                                                          before.nick if before.nick else before.name,
                                                                                                          after.nick if after.nick else after.name)
            nick_embed.set_footer(text=_("User ID: {0}").format(before.id))

            try:
                await nick_channel.send(embed=nick_embed)
            except Exception as e:
                await default.background_error(self, '`member update`', e, before.guild, nick_channel)

    @commands.Cog.listener()
    async def on_user_update(self, before, after):
        for guild in self.bot.guilds:
            if guild.get_member(before.id):
                member_update = CM.get(self.bot, 'memberlog', guild.id)

                if not member_update:
                    continue
                if before.bot:
                    continue

                if before.avatar != after.avatar:
                    updateavatar_channel = guild.get_channel(member_update)
                    updateavatar_embed = discord.Embed(color=self.bot.settings['colors']['log_color'], timestamp=datetime.utcnow())
                    updateavatar_embed.set_author(name=_("{0} changed their avatar").format(before), icon_url=before.avatar_url)
                    updateavatar_embed.title = _("{0} Avatar Changed").format(self.bot.settings['emojis']['logs']['memberedit'])
                    updateavatar_embed.description = _("**Member:** {0} `{1}`\n[Avatar URL]({2})").format(before.mention, before, after.avatar_url)
                    updateavatar_embed.set_thumbnail(url=after.avatar_url)
                    updateavatar_embed.set_footer(text=_("User ID: {0}").format(before.id))
                    try:
                        await updateavatar_channel.send(embed=updateavatar_embed)
                        pass
                    except Exception as e:
                        await default.background_error(self, '`user update (avatar update)`', e, guild, updateavatar_channel)
                        pass

                if before.name != after.name:
                    updateuser_channel = guild.get_channel(member_update)
                    updateuser_embed = discord.Embed(color=self.bot.settings['colors']['log_color'], timestamp=datetime.utcnow())
                    updateuser_embed.set_author(name=_("{0} changed their username").format(after), icon_url=before.avatar_url)
                    updateuser_embed.title = _("{0} Username Changed").format(self.bot.settings['emojis']['logs']['memberedit'])
                    updateuser_embed.description = _("**Member:** {0} `{1}`\n**Before:** {2}\n**After:** {3}").format(after.mention, after, before.name, after.name)
                    updateuser_embed.set_footer(text=_("User ID: {0}").format(before.id))
                    try:
                        await updateuser_channel.send(embed=updateuser_embed)
                    except Exception as e:
                        await default.background_error(self, '`user update (username update)`', e, guild, updateuser_channel)

    @commands.Cog.listener()
    async def on_member_ban(self, guild, user):
        await asyncio.sleep(1)
        moderation = CM.get(self.bot, 'moderation', guild.id)
        case = CM.get(self.bot, 'case_num', guild.id)
        if not moderation:
            return
        if not guild.me.guild_permissions.view_audit_log:
            return
        mod, reason = None, ""
        async for entry in guild.audit_logs(action=discord.AuditLogAction.ban, limit=5):
            if entry.target == user:
                if (datetime.utcnow() - entry.created_at).total_seconds() < 3:
                    mod = entry.user
                    reason += f"{entry.reason}"

        if mod == self.bot.user:
            return
        reason = reason if reason != "None" else "No reason"

        log_channel = self.bot.get_channel(moderation)
        query = 'INSERT INTO cases(guild_id, case_num) VALUES($1, $2) ON CONFLICT (guild_id) DO NOTHING'
        await self.bot.db.execute(query, guild.id, case if case else 0)
        if not case:
            self.bot.case_num[guild.id] = 1
        await self.insert_new_case(mod.id, log_channel.id, case, user.id, guild.id, 1, reason)

        embed = discord.Embed(color=self.bot.settings['colors']['ban_color'], timestamp=datetime.utcnow())
        embed.set_author(name=mod, icon_url=mod.avatar_url, url=f'https://discord.com/users/{mod.id}')
        embed.title = _("{0} A member has been banned").format(self.bot.settings['emojis']['logs']['ban'])
        the_user = f"{user} ({user.id})"
        embed.description = _("**Member:** {0}\n**Moderator:** {1} ({2})\n**Reason:** {3}").format(the_user, mod, mod.id, reason)
        embed.set_footer(text=_("Case ID: #{0}").format(case if case else 1))

        try:
            message = await log_channel.send(embed=embed)
            await self.update_old_case(message.id, guild.id, case)
        except Exception as e:
            await default.background_error(self, '`ban members`', e, guild, log_channel)

    @commands.Cog.listener()
    async def on_member_unban(self, guild, user):
        await asyncio.sleep(1)
        moderation = CM.get(self.bot, 'moderation', guild.id)
        case = CM.get(self.bot, 'case_num', guild.id)
        if not moderation:
            return
        if not guild.me.guild_permissions.view_audit_log:
            return
        mod, reason = None, ""
        async for entry in guild.audit_logs(action=discord.AuditLogAction.unban, limit=50):
            if entry.target == user:
                if (datetime.utcnow() - entry.created_at).total_seconds() < 3:
                    mod = entry.user
                    reason += f"{entry.reason}"

        if mod == self.bot.user:
            return
        reason = reason if reason != "None" else "No reason"

        log_channel = self.bot.get_channel(moderation)
        query = 'INSERT INTO cases(guild_id, case_num) VALUES($1, $2) ON CONFLICT (guild_id) DO NOTHING'
        await self.bot.db.execute(query, guild.id, case if case else 0)
        if not case:
            self.bot.case_num[guild.id] = 1
        await self.insert_new_case(mod.id, log_channel.id, case, user.id, guild.id, 6, reason)

        embed = discord.Embed(color=self.bot.settings['colors']['approve_color'], timestamp=datetime.utcnow())
        embed.set_author(name=mod, icon_url=mod.avatar_url, url=f'https://discord.com/users/{mod.id}')
        embed.title = _("{0} A member was un-banned").format(self.bot.settings['emojis']['logs']['unban'])
        the_user = f"{user} ({user.id})"
        embed.description = _("**Member:** {0}\n**Moderator:** {1} ({2})\n**Reason:** {3}").format(the_user, mod, mod.id, reason)
        embed.set_footer(text=_("Case ID: #{0}").format(case if case else 1))

        try:
            message = await log_channel.send(embed=embed)
            await self.update_old_case(message.id, guild.id, case)
        except Exception as e:
            await default.background_error(self, '`unban members`', e, guild, log_channel)

    @commands.Cog.listener()
    async def on_guild_update(self, before, after):
        guild_logs = CM.get(self.bot, 'guildlog', before.id)

        if guild_logs is None:
            return

        channels = self.bot.get_channel(guild_logs)
        embed = discord.Embed(color=self.bot.settings['colors']['log_color'])
        embed.title = f"{self.bot.settings['emojis']['logs']['guildedit']}"

        if before.name != after.name:
            embed.title += _(" Guild name changed")
            embed.description = _("**Before:** {0}\n**After:** {1}").format(before.name, after.name)
            try:
                await channels.send(embed=embed)
            except Exception as e:
                await default.background_error(self, '`guild name update`', e, before, channels)
                return

        if before.region != after.region:
            embed.title += _(" Guild region changed")
            embed.description = _("**Before:** {0}\n**After:** {1}").format(before.region, after.region)
            try:
                await channels.send(embed=embed)
            except Exception as e:
                await default.background_error(self, '`guild region update`', e, before, channels)
                return

        if before.afk_channel != after.afk_channel:
            embed.title += _(" Guild afk channel changed")
            embed.description = _("**Before:** {0}\n**After:** {1}").format(before.afk_channel, after.afk_channel)
            try:
                await channels.send(embed=embed)
            except Exception as e:
                await default.background_error(self, '`guild afk channel update`', e, before, channels)
                return

        if before.icon_url != after.icon_url:
            embed.title += _(" Guild icon changed")
            embed.description = _("**Before:** [Click here]({0})\n**After:** [Click here]({1})").format(before.icon_url, after.icon_url)
            embed.set_thumbnail(url=after.icon_url)
            try:
                await channels.send(embed=embed)
            except Exception as e:
                await default.background_error(self, '`guild icon update`', e, before, channels)
                return

        if before.mfa_level != after.mfa_level:
            embed.title += _(" Guild multifactor authentication (MFA) changed")
            embed.description = _("**Before:** {0}\n**After:** {1}").format(before.mfa_level, after.mfa_lever)
            try:
                await channels.send(embed=embed)
            except Exception as e:
                await default.background_error(self, '`guild MFA update`', e, before, channels)
                return

        if before.verification_level != after.verification_level:
            embed.title += _(" Guild verification level changed")
            embed.description = _("**Before:** {0}\n**After:** {1}").format(before.verification_level, after.verification_level)
            try:
                await channels.send(embed=embed)
            except Exception as e:
                await default.background_error(self, '`guild verification update`', e, before, channels)
                return

        if before.default_notifications != after.default_notifications:
            embed.title += _(" Guild default notifications changed")
            embed.description = _("**Before:** {0}\n**After:** {1}").format(before.default_notifications, after.default_notifications)
            try:
                await channels.send(embed=embed)
            except Exception as e:
                await default.background_error(self, '`guild notifications update`', e, before, channels)
                return

# Custom Events Start Here

    @commands.Cog.listener()
    async def on_member_joinlog(self, member):
        joinlog = CM.get(self.bot, 'joinlog', member.guild.id)

        if joinlog:
            joinlog_channel = member.guild.get_channel(joinlog)
            joinlog_embed = discord.Embed(color=self.bot.settings['colors']['memberlog_color'], timestamp=datetime.utcnow())
            joinlog_embed.title = _("{0} A new member has joined").format(self.bot.settings['emojis']['logs']['memberjoin'])
            joinlog_embed.set_author(name=_('{0} joined the server').format(member), icon_url=member.avatar_url)
            joinlog_embed.description = _("**Member:** {0} ({1})\n"
                                          "**Account Created:** {2}").format(
                                              member.mention, member.id, btime.human_timedelta(member.created_at, source=datetime.utcnow())
                                          )
            joinlog_embed.set_footer(text=_("Member #{0}").format(member.guild.member_count))
            try:
                await joinlog_channel.send(embed=joinlog_embed)
            except Exception as e:
                await default.background_error(self, '`member joinlog`', e, member.guild, joinlog_channel)

    @commands.Cog.listener()
    async def on_member_leavelog(self, member):
        leavelog = CM.get(self.bot, 'leavelog', member.guild.id)

        if leavelog:
            joinlog_channel = member.guild.get_channel(leavelog)
            joinlog_embed = discord.Embed(color=self.bot.settings['colors']['deny_color'], timestamp=datetime.utcnow())
            joinlog_embed.title = _("{0} A member has left the server").format(self.bot.settings['emojis']['logs']['memberleave'])
            joinlog_embed.set_author(name=_('{0} left the server').format(member), icon_url=member.avatar_url)
            roles = [x.mention for x in member.roles if x.name != '@everyone']
            joinlog_embed.description = _("**Member:** {0} ({1})\n"
                                          "**Joined server:** {2}\n"
                                          "**Roles:** {3}").format(
                                              member.mention, member.id, btime.human_timedelta(member.joined_at, source=datetime.utcnow()),
                                              ', '.join(roles[:20]) + f' **(+{len(member.roles) - 20})**' if len(roles) > 20 else ', '.join(roles) if roles else _('No roles.')
                                          )
            joinlog_embed.set_footer(text=_("Members left: {0}").format(member.guild.member_count))
            try:
                await joinlog_channel.send(embed=joinlog_embed)
            except Exception as e:
                await default.background_error(self, '`member joinlog`', e, member.guild, joinlog_channel)

    @commands.Cog.listener()
    async def on_joinrole(self, member):
        joinrole = CM.get(self.bot, 'joinrole', member.guild.id)

        if not joinrole:
            return

        if member.bot and joinrole['bots']:
            for role in joinrole['bots']:
                role_for_bots = member.guild.get_role(role)
                if not role_for_bots:
                    continue
                try:
                    await member.add_roles(role_for_bots, reason='Join role')
                except Exception as e:
                    await default.background_error(self, '`join role (bots)`', e, member.guild, None)
        elif not member.bot and joinrole['people']:
            for role in joinrole['people']:
                role_for_people = member.guild.get_role(role)
                if not role_for_people:
                    continue
                try:
                    await member.add_roles(role_for_people, reason='Join role')
                except Exception as e:
                    await default.background_error(self, '`join role (people)`', e, member.guild, None)

    @commands.Cog.listener()
    async def on_join_message(self, member):
        db_check = CM.get(self.bot, 'temp_mutes', f'{member.id}, {member.guild.id}')
        if db_check:
            try:
                the_role = member.guild.get_role(db_check)
                await member.add_roles(the_role, reason="Member tried to evade the mute.")
            except Exception as e:
                await default.background_error(self, '`evading mute re-join`', e, member.guild, None)
                pass
        joinmessage = CM.get(self.bot, 'joinmessage', member.guild.id)
        if joinmessage:
            if member.bot and not joinmessage['log_bots']:
                return
            welcome_channel = member.guild.get_channel(joinmessage['channel'])
            is_embed = joinmessage['embedded']
            if is_embed:
                if joinmessage['message']:
                    msg = json.loads(joinmessage['message'])
                else:
                    msg = self.bot.settings['default']['join_message_embed']
                emb_dict = msg
                emb_dict = self.placeholder_replacer(emb_dict, member)
                if "author" in emb_dict:
                    emb_dict["author"] = self.placeholder_replacer(emb_dict["author"], member)
                if "footer" in emb_dict:
                    emb_dict["footer"] = self.placeholder_replacer(emb_dict["footer"], member)
                if "fields" in emb_dict:
                    for field in emb_dict["fields"]:
                        emb_dict["fields"] = self.placeholder_replacer(field["name"], member)
                        emb_dict["fields"] = self.placeholder_replacer(field["value"], member)
                joinmessage = emb_dict
            elif not is_embed:
                if joinmessage['message']:
                    joinmessage = str(joinmessage['message'])
                else:
                    joinmessage = self.bot.settings['default']['join_message_text'].format(member, str(member.guild.member_count))
                joinmessage = joinmessage.replace("{{member.mention}}", member.mention)
                joinmessage = joinmessage.replace("{{member.tag}}", str(member))
                joinmessage = joinmessage.replace("{{member.id}}", str(member.id))
                joinmessage = joinmessage.replace("{{member.name}}", discord.utils.escape_markdown(member.name, as_needed=True))
                joinmessage = joinmessage.replace("{{server.name}}", member.guild.name)
                joinmessage = joinmessage.replace("{{server.members}}", str(member.guild.member_count))
                joinmessage = joinmessage.replace("{0}", member.display_name)
                joinmessage = joinmessage.replace("{1}", str(member.guild.member_count))
            all_mentions = discord.AllowedMentions(users=True, roles=False, everyone=False)

            if is_embed:
                try:
                    try:
                        await welcome_channel.send(content=joinmessage['plainText'], embed=discord.Embed.from_dict(joinmessage), allowed_mentions=all_mentions)
                    except Exception:
                        await welcome_channel.send(embed=discord.Embed.from_dict(joinmessage), allowed_mentions=all_mentions)
                except Exception as e:
                    await default.background_error(self, '`welcoming message (embed)`', e, member.guild, welcome_channel)
            elif not is_embed:
                try:
                    await welcome_channel.send(content=joinmessage, allowed_mentions=all_mentions)
                except Exception as e:
                    await default.background_error(self, '`welcoming message (text)`', e, member.guild, welcome_channel)

    @commands.Cog.listener()
    async def on_leave_message(self, member):
        leavemessage = CM.get(self.bot, 'leavemessage', member.guild.id)
        if leavemessage:
            if member.bot and not leavemessage['log_bots']:
                return
            welcome_channel = member.guild.get_channel(leavemessage['channel'])
            is_embed = leavemessage['embedded']
            if is_embed:
                if leavemessage['message']:
                    msg = json.loads(leavemessage['message'])
                else:
                    msg = self.bot.settings['default']['leave_message_embed']
                emb_dict = msg
                emb_dict = self.placeholder_replacer(emb_dict, member)
                if "author" in emb_dict:
                    emb_dict["author"] = self.placeholder_replacer(emb_dict["author"], member)
                if "footer" in emb_dict:
                    emb_dict["footer"] = self.placeholder_replacer(emb_dict["footer"], member)
                if "fields" in emb_dict:
                    for field in emb_dict["fields"]:
                        emb_dict["fields"] = self.placeholder_replacer(field["name"], member)
                        emb_dict["fields"] = self.placeholder_replacer(field["value"], member)
                leavemessage = emb_dict
            elif not is_embed:
                if leavemessage['message']:
                    leavemessage = str(leavemessage['message'])
                else:
                    leavemessage = self.bot.settings['default']['leave_message_text'].format(member, str(member.guild.member_count))
                leavemessage = leavemessage.replace("{{member.mention}}", member.mention)
                leavemessage = leavemessage.replace("{{member.tag}}", str(member))
                leavemessage = leavemessage.replace("{{member.id}}", str(member.id))
                leavemessage = leavemessage.replace("{{member.name}}", discord.utils.escape_markdown(member.name, as_needed=True))
                leavemessage = leavemessage.replace("{{server.name}}", member.guild.name)
                leavemessage = leavemessage.replace("{{server.members}}", str(member.guild.member_count))
            all_mentions = discord.AllowedMentions(users=True, roles=False, everyone=False)

            if is_embed:
                try:
                    await welcome_channel.send(content=leavemessage['plainText'] if 'plainText' in leavemessage else None,
                                               embed=discord.Embed.from_dict(leavemessage), allowed_mentions=all_mentions)
                except Exception as e:
                    await default.background_error(self, '`leaving message (embed)`', e, member.guild, welcome_channel)
            elif not is_embed:
                try:
                    await welcome_channel.send(content=leavemessage, allowed_mentions=all_mentions)
                except Exception as e:
                    await default.background_error(self, '`leaving message (text)`', e, member.guild, welcome_channel)

    @commands.Cog.listener()
    async def on_ban(self, guild, mod, members, duration, reason, created_at):
        moderation = CM.get(self.bot, 'moderation', guild.id)
        case = CM.get(self.bot, 'case_num', guild.id)
        if not moderation:
            return
        log_channel = self.bot.get_channel(moderation)
        time = btime.human_timedelta(duration.dt, source=created_at, suffix=None) if duration else None
        reason = reason or "No reason"

        ban_list = []
        query = 'INSERT INTO cases(guild_id, case_num) VALUES($1, $2) ON CONFLICT (guild_id) DO NOTHING'
        await self.bot.db.execute(query, guild.id, case if case else 0)
        if not case:
            self.bot.case_num[guild.id] = 1
        for num, member in enumerate(members, start=0):
            ban_list.append(f"`[{num + 1}]` {member} ({member.id})")
            await self.insert_new_case(mod.id, log_channel.id, case, member.id, guild.id, 1, reason)

        embed = discord.Embed(color=self.bot.settings['colors']['ban_color'], timestamp=datetime.utcnow())
        embed.set_author(name=mod, icon_url=mod.avatar_url, url=f'https://discord.com/users/{mod.id}')
        embed.title = _("{0} {1} Member(s) banned").format(self.bot.settings['emojis']['logs']['ban'], len(members))
        embed.description = _("**Member(s):**\n{0}{1}\n**Moderator:** {2} ({3})\n**Reason:** {4}").format("\n".join(ban_list),
                                                                                                          _("\n**Duration:** {0}").format(time) if time else '',
                                                                                                          mod, mod.id, reason)
        embed.set_footer(text=_("Case ID: #{0}").format(case if case else 1))

        try:
            message = await log_channel.send(embed=embed)
            await self.update_old_case(message.id, guild.id, case)
        except Exception as e:
            await default.background_error(self, '`ban members (manual)`', e, guild, log_channel)

    @commands.Cog.listener()
    async def on_hackban(self, guild, mod, members, reason):
        moderation = CM.get(self.bot, 'moderation', guild.id)
        case = CM.get(self.bot, 'case_num', guild.id)
        if not moderation:
            return
        log_channel = self.bot.get_channel(moderation)
        reason = reason or "No reason"

        ban_list = []
        query = 'INSERT INTO cases(guild_id, case_num) VALUES($1, $2) ON CONFLICT (guild_id) DO NOTHING'
        await self.bot.db.execute(query, guild.id, case if case else 0)
        if not case:
            self.bot.case_num[guild.id] = 1
        for num, member in enumerate(members, start=0):
            ban_list.append(f"`[{num + 1}]` {member} ({member.id})")
            await self.insert_new_case(mod.id, log_channel.id, case, member.id, guild.id, 1, reason)

        embed = discord.Embed(color=self.bot.settings['colors']['ban_color'], timestamp=datetime.utcnow())
        embed.set_author(name=mod, icon_url=mod.avatar_url, url=f'https://discord.com/users/{mod.id}')
        embed.title = _("{0} {1} Member(s) hack-banned").format(self.bot.settings['emojis']['logs']['ban'], len(members))
        embed.description = _("**Member(s):**\n{0}{1}\n**Moderator:** {2} ({3})\n**Reason:** {4}").format("\n".join(ban_list[:10]), '' if len(ban_list) <= 10 else f"\n**(+{len(ban_list) - 10}**)",
                                                                                                          mod, mod.id, reason)
        embed.set_footer(text=_("Case ID: #{0}").format(case if case else 1))

        try:
            message = await log_channel.send(embed=embed)
            await self.update_old_case(message.id, guild.id, case)
        except Exception as e:
            await default.background_error(self, '`hackban members (manual)`', e, guild, log_channel)

    @commands.Cog.listener()
    async def on_kick(self, guild, mod, members, reason):
        moderation = CM.get(self.bot, 'moderation', guild.id)
        case = CM.get(self.bot, 'case_num', guild.id)
        if not moderation:
            return
        log_channel = self.bot.get_channel(moderation)
        reason = reason or "No reason"

        kick_list = []
        query = 'INSERT INTO cases(guild_id, case_num) VALUES($1, $2) ON CONFLICT (guild_id) DO NOTHING'
        await self.bot.db.execute(query, guild.id, case if case else 0)
        if not case:
            self.bot.case_num[guild.id] = 1
        for num, member in enumerate(members, start=0):
            kick_list.append(f"`[{num + 1}]` {member} ({member.id})")
            await self.insert_new_case(mod.id, log_channel.id, case, member.id, guild.id, 2, reason)

        embed = discord.Embed(color=self.bot.settings['colors']['kick_color'], timestamp=datetime.utcnow())
        embed.set_author(name=mod, icon_url=mod.avatar_url, url=f'https://discord.com/users/{mod.id}')
        embed.title = _("{0} {1} Member(s) kicked").format(self.bot.settings['emojis']['logs']['memberleave'], len(members))
        embed.description = _("**Member(s):**\n{0}\n**Moderator:** {1} ({2})\n**Reason:** {3}").format("\n".join(kick_list),
                                                                                                       mod, mod.id, reason)
        embed.set_footer(text=_("Case ID: #{0}").format(case if case else 1))

        try:
            message = await log_channel.send(embed=embed)
            await self.update_old_case(message.id, guild.id, case)
        except Exception as e:
            await default.background_error(self, '`kick members (manual)`', e, guild, log_channel)

    @commands.Cog.listener()
    async def on_softban(self, guild, mod, members, reason):
        moderation = CM.get(self.bot, 'moderation', guild.id)
        case = CM.get(self.bot, 'case_num', guild.id)
        if not moderation:
            return
        log_channel = self.bot.get_channel(moderation)
        reason = reason or "No reason"

        kick_list = []
        query = 'INSERT INTO cases(guild_id, case_num) VALUES($1, $2) ON CONFLICT (guild_id) DO NOTHING'
        await self.bot.db.execute(query, guild.id, case if case else 0)
        if not case:
            self.bot.case_num[guild.id] = 1
        for num, member in enumerate(members, start=0):
            kick_list.append(f"`[{num + 1}]` {member} ({member.id})")
            await self.insert_new_case(mod.id, log_channel.id, case, member.id, guild.id, 3, reason)

        embed = discord.Embed(color=self.bot.settings['colors']['kick_color'], timestamp=datetime.utcnow())
        embed.set_author(name=mod, icon_url=mod.avatar_url, url=f'https://discord.com/users/{mod.id}')
        embed.title = _("{0} {1} Member(s) softbanned").format(self.bot.settings['emojis']['logs']['memberleave'], len(members))
        embed.description = _("**Member(s):**\n{0}\n**Moderator:** {1} ({2})\n**Reason:** {3}").format("\n".join(kick_list),
                                                                                                       mod, mod.id, reason)
        embed.set_footer(text=_("Case ID: #{0}").format(case if case else 1))

        try:
            message = await log_channel.send(embed=embed)
            await self.update_old_case(message.id, guild.id, case)
        except Exception as e:
            await default.background_error(self, '`softban members (manual)`', e, guild, log_channel)

    @commands.Cog.listener()
    async def on_mute(self, guild, mod, members, duration, reason, created_at):
        moderation = CM.get(self.bot, 'moderation', guild.id)
        case = CM.get(self.bot, 'case_num', guild.id)
        if not moderation:
            return
        log_channel = self.bot.get_channel(moderation)
        time = btime.human_timedelta(duration.dt, source=created_at, suffix=None) if duration else None
        reason = reason or "No reason"

        ban_list = []
        query = 'INSERT INTO cases(guild_id, case_num) VALUES($1, $2) ON CONFLICT (guild_id) DO NOTHING'
        await self.bot.db.execute(query, guild.id, case if case else 0)
        if not case:
            self.bot.case_num[guild.id] = 1
        for num, member in enumerate(members, start=0):
            ban_list.append(f"`[{num + 1}]` {member} ({member.id})")
            await self.insert_new_case(mod.id, log_channel.id, case, member.id, guild.id, 4, reason)

        embed = discord.Embed(color=self.bot.settings['colors']['kick_color'], timestamp=datetime.utcnow())
        embed.set_author(name=mod, icon_url=mod.avatar_url, url=f'https://discord.com/users/{mod.id}')
        embed.title = _("{0} {1} Member(s) muted").format(self.bot.settings['emojis']['logs']['memberedit'], len(members))
        embed.description = _("**Member(s):**\n{0}{1}\n**Moderator:** {2} ({3})\n**Reason:** {4}").format("\n".join(ban_list),
                                                                                                          _("\n**Duration:** {0}").format(time) if time else '',
                                                                                                          mod, mod.id, reason)
        embed.set_footer(text=_("Case ID: #{0}").format(case if case else 1))

        try:
            message = await log_channel.send(embed=embed)
            await self.update_old_case(message.id, guild.id, case)
        except Exception as e:
            await default.background_error(self, '`mute members (manual)`', e, guild, log_channel)

    @commands.Cog.listener()
    async def on_warn(self, guild, mod, members, reason):
        moderation = CM.get(self.bot, 'moderation', guild.id)
        case = CM.get(self.bot, 'case_num', guild.id)
        if not moderation:
            return
        log_channel = self.bot.get_channel(moderation)
        reason = reason or "No reason"

        warn_list = []
        query = 'INSERT INTO cases(guild_id, case_num) VALUES($1, $2) ON CONFLICT (guild_id) DO NOTHING'
        await self.bot.db.execute(query, guild.id, case if case else 0)
        if not case:
            self.bot.case_num[guild.id] = 1
        for num, member in enumerate(members, start=0):
            warn_list.append(f"`[{num + 1}]` {member} ({member.id})")
            await self.insert_new_case(mod.id, log_channel.id, case, member.id, guild.id, 5, reason)

        embed = discord.Embed(color=self.bot.settings['colors']['warn_color'], timestamp=datetime.utcnow())
        embed.set_author(name=mod, icon_url=mod.avatar_url, url=f'https://discord.com/users/{mod.id}')
        embed.title = _("{0} {1} Member(s) warned").format(self.bot.settings['emojis']['logs']['memberedit'], len(members))
        embed.description = _("**Member(s):**\n{0}\n**Moderator:** {1} ({2})\n**Reason:** {3}").format("\n".join(warn_list),
                                                                                                       mod, mod.id, reason)
        embed.set_footer(text=_("Case ID: #{0}").format(case if case else 1))

        try:
            message = await log_channel.send(embed=embed)
            await self.update_old_case(message.id, guild.id, case)
        except Exception as e:
            await default.background_error(self, '`warn members (manual)`', e, guild, log_channel)

    @commands.Cog.listener()
    async def on_unban(self, guild, mod, members, reason):
        moderation = CM.get(self.bot, 'moderation', guild.id)
        case = CM.get(self.bot, 'case_num', guild.id)
        if not moderation:
            return
        log_channel = self.bot.get_channel(moderation)
        reason = reason or "No Reason"

        unban_list = []
        query = 'INSERT INTO cases(guild_id, case_num) VALUES($1, $2) ON CONFLICT (guild_id) DO NOTHING'
        await self.bot.db.execute(query, guild.id, case if case else 0)
        if not case:
            self.bot.case_num[guild.id] = 1
        for num, member in enumerate(members, start=0):
            unban_list.append(f"`[{num + 1}]` {member} ({member.id})")
            await self.insert_new_case(mod.id, log_channel.id, case, member.id, guild.id, 6, reason)

        unban_lists = unban_list if len(unban_list) <= 10 else unban_list[:10]

        embed = discord.Embed(color=self.bot.settings['colors']['approve_color'], timestamp=datetime.utcnow())
        embed.set_author(name=mod, icon_url=mod.avatar_url, url=f'https://discord.com/users/{mod.id}')
        embed.title = _("{0} {1} Member(s) un-banned").format(self.bot.settings['emojis']['logs']['unban'], len(members))
        embed.description = _("**Member(s):**\n{0}{1}\n**Moderator:** {2} ({3})\n**Reason:** {4}").format("\n".join(unban_lists), '' if len(unban_list) <= 10 else f"\n**(+{len(unban_list) - 10}**)",
                                                                                                          mod, mod.id, reason)
        embed.set_footer(text=_("Case ID: #{0}").format(case if case else 1))

        try:
            message = await log_channel.send(embed=embed)
            await self.update_old_case(message.id, guild.id, case)
        except Exception as e:
            await default.background_error(self, '`unban members (manual)`', e, guild, log_channel)

    @commands.Cog.listener()
    async def on_unmute(self, guild, mod, members, reason):
        moderation = CM.get(self.bot, 'moderation', guild.id)
        case = CM.get(self.bot, 'case_num', guild.id)
        if not moderation:
            return
        log_channel = self.bot.get_channel(moderation)
        reason = reason or "No Reason"

        unmute_list = []
        query = 'INSERT INTO cases(guild_id, case_num) VALUES($1, $2) ON CONFLICT (guild_id) DO NOTHING'
        await self.bot.db.execute(query, guild.id, case if case else 0)
        if not case:
            self.bot.case_num[guild.id] = 1
        for num, member in enumerate(members, start=0):
            unmute_list.append(f"`[{num + 1}]` {member} ({member.id})")
            await self.insert_new_case(mod.id, log_channel.id, case, member.id, guild.id, 7, reason)

        embed = discord.Embed(color=self.bot.settings['colors']['approve_color'], timestamp=datetime.utcnow())
        embed.set_author(name=mod, icon_url=mod.avatar_url, url=f'https://discord.com/users/{mod.id}')
        embed.title = _("{0} {1} Member(s) un-muted").format(self.bot.settings['emojis']['logs']['memberedit'], len(members))
        embed.description = _("**Member(s):**\n{0}\n**Moderator:** {1} ({2})\n**Reason:** {3}").format("\n".join(unmute_list),
                                                                                                       mod, mod.id, reason)
        embed.set_footer(text=_("Case ID: #{0}").format(case if case else 1))

        try:
            message = await log_channel.send(embed=embed)
            await self.update_old_case(message.id, guild.id, case)
        except Exception as e:
            await default.background_error(self, '`unmute members (manual)`', e, guild, log_channel)

    @commands.Cog.listener()
    async def on_member_kick(self, guild, user):
        await asyncio.sleep(1)
        moderation = CM.get(self.bot, 'moderation', guild.id)
        case = CM.get(self.bot, 'case_num', guild.id)
        if not moderation:
            return
        if not guild.me.guild_permissions.view_audit_log:
            return
        mod, reason = None, ""
        async for entry in guild.audit_logs(action=discord.AuditLogAction.kick, limit=5):
            if entry.target == user:
                if (datetime.utcnow() - entry.created_at).total_seconds() < 3:
                    mod = entry.user
                    reason += f"{entry.reason}"

        if mod is None:
            return

        if mod == self.bot.user:
            return
        reason = reason if reason != "None" else "No reason"

        log_channel = self.bot.get_channel(moderation)
        query = 'INSERT INTO cases(guild_id, case_num) VALUES($1, $2) ON CONFLICT (guild_id) DO NOTHING'
        await self.bot.db.execute(query, guild.id, case if case else 0)
        if not case:
            self.bot.case_num[guild.id] = 1
        await self.insert_new_case(mod.id, log_channel.id, case, user.id, guild.id, 2, reason)

        embed = discord.Embed(color=self.bot.settings['colors']['kick_color'], timestamp=datetime.utcnow())
        embed.set_author(name=mod, icon_url=mod.avatar_url, url=f'https://discord.com/users/{mod.id}')
        embed.title = _("{0} A member has been kicked").format(self.bot.settings['emojis']['logs']['memberleave'])
        the_user = f"{user} ({user.id})"
        embed.description = _("**Member:** {0}\n**Moderator:** {1} ({2})\n**Reason:** {3}").format(the_user, mod, mod.id, reason)
        embed.set_footer(text=_("Case ID: #{0}").format(case if case else 1))

        try:
            message = await log_channel.send(embed=embed)
            await self.update_old_case(message.id, guild.id, case)
        except Exception as e:
            await default.background_error(self, '`kick members`', e, guild, log_channel)

    @commands.Cog.listener()
    async def on_voice_mute(self, guild, mod, members, reason):
        moderation = CM.get(self.bot, 'moderation', guild.id)
        case = CM.get(self.bot, 'case_num', guild.id)
        if not moderation:
            return
        log_channel = self.bot.get_channel(moderation)
        reason = reason or "No reason"

        mute_list = []
        query = 'INSERT INTO cases(guild_id, case_num) VALUES($1, $2) ON CONFLICT (guild_id) DO NOTHING'
        await self.bot.db.execute(query, guild.id, case if case else 0)
        if not case:
            self.bot.case_num[guild.id] = 1
        for num, member in enumerate(members, start=0):
            mute_list.append(f"`[{num + 1}]` {member} ({member.id})")
            await self.insert_new_case(mod.id, log_channel.id, case, member.id, guild.id, 8, reason)

        embed = discord.Embed(color=self.bot.settings['colors']['update_color'], timestamp=datetime.utcnow())
        embed.set_author(name=mod, icon_url=mod.avatar_url, url=f'https://discord.com/users/{mod.id}')
        embed.title = _("{0} {1} Member(s) voice muted").format(self.bot.settings['emojis']['logs']['vmute'], len(members))
        embed.description = _("**Member(s):**\n{0}\n**Moderator:** {1} ({2})\n**Reason:** {3}").format("\n".join(mute_list),
                                                                                                       mod, mod.id, reason)
        embed.set_footer(text=_("Case ID: #{0}").format(case if case else 1))

        try:
            message = await log_channel.send(embed=embed)
            await self.update_old_case(message.id, guild.id, case)
        except Exception as e:
            await default.background_error(self, '`voice mute members (manual)`', e, guild, log_channel)

    @commands.Cog.listener()
    async def on_voice_unmute(self, guild, mod, members, reason):
        moderation = CM.get(self.bot, 'moderation', guild.id)
        case = CM.get(self.bot, 'case_num', guild.id)
        if not moderation:
            return
        log_channel = self.bot.get_channel(moderation)
        reason = reason or "No reason"

        mute_list = []
        query = 'INSERT INTO cases(guild_id, case_num) VALUES($1, $2) ON CONFLICT (guild_id) DO NOTHING'
        await self.bot.db.execute(query, guild.id, case if case else 0)
        if not case:
            self.bot.case_num[guild.id] = 1
        for num, member in enumerate(members, start=0):
            mute_list.append(f"`[{num + 1}]` {member} ({member.id})")
            await self.insert_new_case(mod.id, log_channel.id, case, member.id, guild.id, 9, reason)

        embed = discord.Embed(color=self.bot.settings['colors']['update_color'], timestamp=datetime.utcnow())
        embed.set_author(name=mod, icon_url=mod.avatar_url, url=f'https://discord.com/users/{mod.id}')
        embed.title = _("{0} {1} Member(s) voice unmuted").format(self.bot.settings['emojis']['logs']['vunmute'], len(members))
        embed.description = _("**Member(s):**\n{0}\n**Moderator:** {1} ({2})\n**Reason:** {3}").format("\n".join(mute_list),
                                                                                                       mod, mod.id, reason)
        embed.set_footer(text=_("Case ID: #{0}").format(case if case else 1))

        try:
            message = await log_channel.send(embed=embed)
            await self.update_old_case(message.id, guild.id, case)
        except Exception as e:
            await default.background_error(self, '`voice unmute members (manual)`', e, guild, log_channel)

    @commands.Cog.listener()
    async def on_dehoist(self, guild, mod, members):
        moderation = CM.get(self.bot, 'moderation', guild.id)
        case = CM.get(self.bot, 'case_num', guild.id)
        if not moderation:
            return
        log_channel = self.bot.get_channel(moderation)
        reason = None

        dehoist_list = []
        query = 'INSERT INTO cases(guild_id, case_num) VALUES($1, $2) ON CONFLICT (guild_id) DO NOTHING'
        await self.bot.db.execute(query, guild.id, case if case else 0)
        if not case:
            self.bot.case_num[guild.id] = 1
        for num, member in enumerate(members, start=0):
            dehoist_list.append(f"`[{num + 1}]` {member} ({member.id})")
            await self.insert_new_case(mod.id, log_channel.id, case, member.id, guild.id, 10, reason)

        dehoist_lists = dehoist_list if len(dehoist_list) <= 10 else dehoist_list[:10]

        embed = discord.Embed(color=self.bot.settings['colors']['update_color'], timestamp=datetime.utcnow())
        embed.set_author(name=mod, icon_url=mod.avatar_url, url=f'https://discord.com/users/{mod.id}')
        embed.title = _("{0} {1} Member(s) dehoisted").format(self.bot.settings['emojis']['logs']['memberedit'], len(members))
        embed.description = _("**Member(s):**\n{0}{1}\n**Moderator:** {2} ({3})\n").format("\n".join(dehoist_lists), '' if len(dehoist_list) <= 10 else f"\n**(+{len(dehoist_list) - 10}**)",
                                                                                           mod, mod.id)
        embed.set_footer(text=_("Case ID: #{0}").format(case if case else 1))

        try:
            message = await log_channel.send(embed=embed)
            await self.update_old_case(message.id, guild.id, case)
        except Exception as e:
            await default.background_error(self, '`unban members (manual)`', e, guild, log_channel)

# Support Server Events

    @commands.Cog.listener('on_member_update')
    async def on_booster_append(self, before, after):
        if before.guild.id != 671078170874740756:
            return

        booster_role = before.guild.get_role(745290115085107201)

        if booster_role not in before.roles and booster_role in after.roles:
            booster = CM.get(self.bot, 'boosters', before.id)
            if not booster:
                await self.bot.db.execute("INSERT INTO boosters(user_id, prefix) VALUES($1, $2)", after.id, self.bot.settings['default']['owner_prefix'])
                self.bot.boosters[after.id] = self.bot.settings['default']['owner_prefix']
                channel = self.bot.get_channel(self.bot.settings['channels']['boosters-chat'])
                perks = "`[1]` Cool badge\n`[2]` No cooldowns\n`[3]` No voting\n`[4]` Custom prefix (accessible everywhere, even in DMs)\n`[5]` Ability to link social media which will be displayed in `-userinfo`"
                await channel.send("{0} **{1}** Thank you for boosting this server, as a reward you now have these perks:\n{2}".format(
                    self.bot.settings['emojis']['ranks']['donator'], after.mention, perks
                ), allowed_mentions=discord.AllowedMentions(users=True))
                await before.add_roles(before.guild.get_role(self.bot.settings['roles']['boosters']))
                badges = CM.get(self.bot, 'badges', before.id)
                badge = 'donator'

                if getattr(publicflags.BotFlags(badges if badges else 0), badge):
                    return

                if badges:
                    await self.bot.db.execute("UPDATE badges SET flags = flags + 256 WHERE _id = $1", before.id)
                    self.bot.badges[before.id] += 256
                elif not badges:
                    await self.bot.db.execute("INSERT INTO badges(_id, flags) VALUES($1, $2)", before.id, 256)
                    self.bot.badges[before.id] = 256

    @commands.Cog.listener('on_member_join')
    async def anti_join_dehoist(self, member):
        check = CM.get(self.bot, 'antihoist', member.guild.id)

        if member.bot:
            return

        if not member.guild.me.guild_permissions.manage_nicknames:
            return

        if not check:
            return

        nick = member.display_name
        chosen_nick = check['nickname']
        logchannel = check['channel']
        chosen_nick = chosen_nick or 'z (hoister)'
        if logchannel:
            channel = member.guild.get_channel(logchannel)
        if not nick[0].isalnum():
            await asyncio.sleep(60)
            if not nick[0].isalnum():
                await member.edit(nick=chosen_nick, reason='Anti hoist')
                self.bot.dispatch('dehoist', member.guild, member.guild.me, [member])

    @commands.Cog.listener('on_member_update')
    async def anti_edit_dehoist(self, before, after):
        check = CM.get(self.bot, 'antihoist', before.guild.id)

        if before.bot:
            return

        if not before.guild.me.guild_permissions.manage_nicknames:
            return

        if not check:
            return

        nick = after.display_name
        chosen_nick = check['nickname']
        logchannel = check['channel']
        chosen_nick = chosen_nick or 'z (hoister)'
        if logchannel:
            channel = after.guild.get_channel(logchannel)
        if not nick[0].isalnum():
            await asyncio.sleep(60)
            if not nick[0].isalnum():
                await after.edit(nick=chosen_nick, reason='Anti hoist')
                self.bot.dispatch('dehoist', after.guild, after.guild.me, [after])


def setup(bot):
    bot.add_cog(Logging(bot))
