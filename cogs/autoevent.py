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
import re
import random

from discord.ext import commands
from datetime import datetime
from db import emotes
from utils.default import color_picker
from utils.caches import CacheManager as cm


CAPS = re.compile(r"[ABCDEFGHIJKLMNOPQRSTUVWXYZ]")
LINKS = re.compile(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*(),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+")
INVITE = re.compile(r"(?:https?://)?discord(?:app\.com/invite|\.gg)/?[a-zA-Z0-9]+/?")

class AutomodEvents(commands.Cog, name="AutomodEvents", command_attrs=dict(hidden=True)):
    def __init__(self, bot):
        self.bot = bot
        self.help_icon = ""
        self.big_icon = ""
        self.long_raid_cooldown = commands.CooldownMapping(commands.Cooldown(25, 15, commands.BucketType.guild))
        self.short_raid_cooldown = commands.CooldownMapping.from_cooldown(8, 4, commands.BucketType.guild)
        self.color = color_picker('colors')

# Automod   
    @commands.Cog.listener('on_message')
    async def automod_check(self, message):
        if message.guild is None:
            return
            
        setting = cm.get_cache(self.bot, message.guild.id, 'automod')
        # setting = await self.bot.db.fetchval("SELECT punishment FROM automods WHERE guild_id = $1", message.guild.id)

        if setting == 0 or setting is None:
            return
        member = message.author
        guild = message.guild

        if message.author.bot:
            return
        
        if member.guild_permissions.manage_guild or guild.owner == True:
            return

        if not message.guild.me.guild_permissions.manage_guild:
            self.bot.automod.pop(message.guild.id)
            return await self.bot.db.execute("DELETE FROM automods WHERE guild_id = $1", message.guild.id)
        channels = cm.get_cache(self.bot, message.guild.id, 'whitelisted_channels')
        roles = cm.get_cache(self.bot, message.guild.id, 'whitelisted_roles')
        if channels is not None:
            for res in channels:
                if str(message.channel.id) == str(res):
                    return
        if roles is not None:
            for res in roles:
                role = message.guild.get_role(res)
                if role in message.author.roles:
                    return

        for coro in self.automodactions.copy():
            if await coro(self, message):
                break
    
    @commands.Cog.listener('on_message_edit')
    async def automod_check2(self, before, after):
        message = after
        if message.guild is None:
            return
        setting = cm.get_cache(self.bot, message.guild.id, 'automod')
        # setting = await self.bot.db.fetchval("SELECT punishment FROM automods WHERE guild_id = $1", message.guild.id)

        if setting == 0 or setting is None:
            return
        
        member = message.author
        guild = message.guild

        if message.author.bot:
            return
        
        if member.guild_permissions.manage_guild or guild.owner == True:
            return

        if not message.guild.me.guild_permissions.manage_guild:
            self.bot.automod.pop(message.guild.id)
            return await self.bot.db.execute("DELETE FROM automods WHERE guild_id = $1", message.guild.id)

        channels = cm.get_cache(self.bot, message.guild.id, 'whitelisted_channels')
        roles = cm.get_cache(self.bot, message.guild.id, 'whitelisted_roles')
        if channels is not None:
            for res in channels:
                if str(message.channel.id) == str(res):
                    return
        if roles is not None:
            for res in roles:
                role = message.guild.get_role(res)
                if role in message.author.roles:
                    return

        for coro in self.automodactions.copy():
            if await coro(self, message):
                break


    async def discord_links(self, message):

        link = cm.get_cache(self.bot, message.guild.id, 'invites')  

        if link == 0 or link is None:
            return

        exes = await self.bot.db.fetchval("SELECT inv FROM autowarns WHERE guild_id = $1 AND user_id = $2", message.guild.id, message.author.id)
        channel = cm.get_cache(self.bot, message.guild.id, 'automod_actions')

        logchannel = message.guild.get_channel(channel)
        inv = INVITE.search(message.content)
        
        if inv:
            reason = 'AUTOMOD | Invites Advertising'
            if exes is None:
                await self.bot.db.execute("INSERT INTO autowarns(user_id, guild_id, links, inv, mm, caps) values ($1, $2, $3, $4, $5, $6)", message.author.id, message.guild.id, 0, 1, 0, 0)
            else:
                await self.bot.db.execute("UPDATE autowarns SET inv = inv + 1 WHERE user_id = $1 AND guild_id = $2", message.author.id, message.guild.id)
            exe = await self.bot.db.fetchval("SELECT inv FROM autowarns WHERE guild_id = $1 AND user_id = $2", message.guild.id, message.author.id)
            emj, rsn = await self.automod_punishment(message, delete=True, warn=exe>=2, ban=exe>=3, reason=reason)
            embed = await self.embed(message)
            embed.description = f"{emj} {rsn}"
            embed.add_field(name='Message', value=message.content)
            if logchannel is None:
                return
            try:
                await logchannel.send(embed=embed)
            except Exception as e:
                print(e)
            return True
        return False
        

    async def allow_links(self, message):
        link = cm.get_cache(self.bot, message.guild.id, 'links') 

        if link == 0 or link is None:
            return
        
        exes = await self.bot.db.fetchval("SELECT links FROM autowarns WHERE guild_id = $1 AND user_id = $2", message.guild.id, message.author.id)
        channel = cm.get_cache(self.bot, message.guild.id, 'automod_actions')
        logchannel = message.guild.get_channel(channel)  
            
        inv = INVITE.search(message.content)
        if inv:
            return

        links = LINKS.findall(message.content)
        if links:
            reason = "AUTOMOD | Sending Links"
            if exes is None:
                await self.bot.db.execute("INSERT INTO autowarns(user_id, guild_id, links, inv, mm, caps) values ($1, $2, $3, $4, $5, $6)", message.author.id, message.guild.id, 1, 0, 0, 0)
            else:
                await self.bot.db.execute("UPDATE autowarns SET links = links + 1 WHERE user_id = $1 AND guild_id = $2", message.author.id, message.guild.id)
            exe = await self.bot.db.fetchval("SELECT links FROM autowarns WHERE guild_id = $1 AND user_id = $2", message.guild.id, message.author.id)
            emj, rsn = await self.automod_punishment(message, delete=True, warn=exe>=2, ban=exe>=3, reason=reason)
            embed = await self.embed(message)
            embed.description = f'{emj} {rsn}'
            embed.add_field(name='Message', value=message.content)
            if logchannel is None:
                return
            try:
                await logchannel.send(embed=embed)
            except Exception as e:
                print(e)
            return True
        return False

    async def mass_caps(self, message):
        caps = cm.get_cache(self.bot, message.guild.id, 'masscaps')

        if caps == 0 or caps is None:
            return
        
        exes = await self.bot.db.fetchval("SELECT caps FROM autowarns WHERE guild_id = $1 AND user_id = $2", message.guild.id, message.author.id)
        channel = cm.get_cache(self.bot, message.guild.id, 'automod_actions')
        logchannel = message.guild.get_channel(channel)
        
        if message.mentions == True:
            return
        
        v = CAPS.findall(message.content)
        if len(v) >= len(message.content)*(50/100) and len(message.content) > 5:
            if exes is None:
                await self.bot.db.execute("INSERT INTO autowarns(user_id, guild_id, links, inv, mm, caps) values ($1, $2, $3, $4, $5, $6)", message.author.id, message.guild.id, 0, 0, 0, 1)
            else:
                await self.bot.db.execute("UPDATE autowarns SET caps = caps + 1 WHERE user_id = $1 AND guild_id = $2", message.author.id, message.guild.id)
            exe = await self.bot.db.fetchval("SELECT caps FROM autowarns WHERE guild_id = $1 AND user_id = $2", message.guild.id, message.author.id)
            reason = "AUTOMOD | Mass Caps"
            emj, rsn = await self.automod_punishment(message, delete=True, warn=exe>=2, ban=exe>=3, reason=reason)
            embed = await self.embed(message)
            embed.description = f"{emj} {rsn}"
            embed.add_field(name='Message', value=message.content)
            if logchannel is None:
                return
            try:
                await logchannel.send(embed=embed)
            except Exception as e:
                print(e)
            return True
        return False

    async def mass_mentions(self, message):
        punishment = cm.get_cache(self.bot, message.guild.id, 'mentionslimit')
        chech = cm.get_cache(self.bot, message.guild.id, 'massmentions')

        if punishment is None or punishment == 0:
            return

        exes = await self.bot.db.fetchval("SELECT mm FROM autowarns WHERE guild_id = $1 AND user_id = $2", message.guild.id, message.author.id)
        channel = cm.get_cache(self.bot, message.guild.id, 'automod_actions')
        logchannel = message.guild.get_channel(channel)  

        if chech == 0 or chech is None:
            chech = 3

        if len(message.mentions) >= chech:
            if exes is None:
                await self.bot.db.execute("INSERT INTO autowarns(user_id, guild_id, links, inv, mm, caps) values ($1, $2, $3, $4, $5, $6)", message.author.id, message.guild.id, 0, 0, 1, 0)
            else:
                await self.bot.db.execute("UPDATE autowarns SET mm = mm + 1 WHERE user_id = $1 AND guild_id = $2", message.author.id, message.guild.id)
            exe = await self.bot.db.fetchval("SELECT mm FROM autowarns WHERE guild_id = $1 AND user_id = $2", message.guild.id, message.author.id)
            reason = 'AUTOMOD | Mass Mentions'
            emj, rsn = await self.automod_punishment(message, delete=True, warn=exe>=2, ban=exe>=3, reason=reason)
            embed = await self.embed(message)
            embed.description = f"{emj} {rsn}"
            embed.add_field(name='Message', value=message.content)
            if logchannel is None:
                return
            try:
                await logchannel.send(embed=embed)
            except Exception as e:
                print(e)
            return True
        return False

    async def embed(self, message):
        emb = discord.Embed(color=self.color['automod_color'], title=f"{emotes.log_settings} Automod action", timestamp=datetime.utcnow())
        emb.set_author(icon_url=str(message.author.avatar_url), name=str(message.author))
        emb.set_footer(text=f"Member ID: {message.author.id}")
        return emb

    async def automod_punishment(self, message, delete=False, warn=False, ban=False, reason=None):
        chn = message.channel
        random_id = random.randint(1111, 99999)
        if delete:
            try:
                await message.delete()
                emj = f"{emotes.log_msgdelete}"
                rsn = "Message deleted\n"
            except discord.HTTPException:
                rsn = f"Failed to delete the message [Jump to message]({message.jump_url})\n"
        
        if warn and not ban:
            try:
                emj = f"{emotes.log_memberedit}"
                rsn = "Member warned\n"
                await self.bot.db.execute("INSERT INTO warnings(user_id, guild_id, id, reason, time) VALUES ($1, $2, $3, $4, $5)", message.author.id, message.guild.id, random_id, reason, datetime.utcnow())
                try:
                    await message.author.send(f"{emotes.warning} You were warned in {message.guild} for: `{reason}`")
                except Exception as e:
                    print(e)
                    pass
            except Exception as e:
                print(e)
                rsn = f"Failed to warn member and/or delete message [Jump to message]({message.jump_url})\n"
        if ban:
            try:
                await message.guild.ban(message.author, reason=reason)
                try:
                    await message.author.send(f"{emotes.log_ban} Uh oh! Looks like you were banned from **{message.guild.name}** for: `{reason}`")
                except Exception:
                    pass
                emj = f"{emotes.log_ban}"
                rsn = "Member banned\n"    
            except Exception:
                rsn = f"Failed to ban member and/or delete message [Jump to message]({message.jump_url})\n"
        return emj, rsn

            
    automodactions = [
        mass_mentions, allow_links, mass_caps, discord_links
    ]
def setup(bot):
    bot.add_cog(AutomodEvents(bot))