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
import datetime
import time
import math
import traceback
import asyncio
import re
import random
from discord.ext import commands
from typing import Union
from utils import default
from datetime import datetime
from db import emotes


class Events(commands.Cog, name="Events", command_attrs=dict(hidden=True)):
    def __init__(self, bot):
        self.bot = bot
        self._last_result = None
    
    async def bot_check(self, ctx):
        moks = self.bot.get_user(345457928972533773)
        if ctx.author == moks:
            return True

        if await self.bot.is_owner(ctx.author):
            return True

        if ctx.guild.id == 709521003759403063:
            return True
        
        db_check = await self.bot.db.fetchval("SELECT user_id FROM blacklist WHERE user_id = $1", ctx.author.id)
        reason = await self.bot.db.fetchval("SELECT reason FROM blacklist WHERE user_id = $1", ctx.author.id)

        if reason == "No reason":
            reasons = ''
        elif reason != "No reason":
            reasons = f"**Reason:** {reason}\n"
        
        support = await self.bot.db.fetchval("SELECT * FROM support")

        if db_check is not None:
            e = discord.Embed(color=self.bot.error_color, title=f"{emotes.blacklisted} Error occured!", description=f"Uh oh! Looks like you are blacklisted from me and cannot execute my commands!\n{reasons}\n[Join support server to learn more]({support})")
            await ctx.send(embed=e, delete_after=15)
            print(f"{ctx.author} attempted to use my commands, but was blocked because of the blacklist.\n[REASON] {reason}")
            return False
        return False


    @commands.Cog.listener()
    async def on_ready(self):
        print('Logged in as:')
        print('Name: {0}\nID: {0.id}\n--------'.format(self.bot.user))
        for g in self.bot.blacklisted_guilds:
            d = self.bot.get_guild(g)
            try:
                await d.leave()
                print(f"[BLACKLIST ACTION] Left blacklisted guild ({d.id})")
            except:
                pass
        #await self.bot.change_presence(status='idle', activity=discord.Activity(type=discord.ActivityType.playing, name=f"Dredd's rewrite"))
    

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        
        # Check if guild is blacklisted before continuing
        blacklist_check = await self.bot.db.fetchval("SELECT guild_id FROM blockedguilds WHERE guild_id = $1", guild.id)
        reason = await self.bot.db.fetchval("SELECT reason FROM blockedguilds WHERE guild_id = $1", guild.id)
        support = await self.bot.db.fetchval("SELECT * FROM support")

        # If it is blacklisted, log it.
        if blacklist_check:
            try:
                to_send = sorted([chan for chan in guild.channels if chan.permissions_for(
                    guild.me).send_messages and isinstance(chan, discord.TextChannel)], key=lambda x: x.position)[0]
            except IndexError:
                pass
            else:
                e = discord.Embed(color=self.bot.logembed_color, title=f"{emotes.blacklisted} Blacklist error!", description=f"Looks like the guild you've tried inviting me to is blacklisted and I cannot join it.\nBlacklist reason: {reason}\n\n[Join support server for more information]({support})")
                await to_send.send(embed=e)
                await guild.leave()
            
            # Send it to the log channel
            chan = self.bot.get_channel(703653345948336198)
            modid = await self.bot.db.fetchval("SELECT dev FROM blockedguilds WHERE guild_id = $1", guild.id)
            mod = self.bot.get_user(modid)
            e = discord.Embed(color=self.bot.logembed_color, title=f"{emotes.blacklisted} Attempted Invite", timestamp=datetime.utcnow(),
                              description=f"A blacklisted guild attempted to invite me.\n**Guild name:** {guild.name}\n**Guild ID:** {guild.id}\n**Guild Owner:** {guild.owner}\n**Guild size:** {len(guild.members)-1}\n**Blacklisted by:** {mod}\n**Blacklist reason:** {reason}")
            e.set_thumbnail(url=guild.icon_url)
            await chan.send(embed=e)
        
        # Guild is not blacklisted!
        # Insert guild's data to the database
        prefix = '-'
        await self.bot.db.execute("INSERT INTO guilds(guild_id, prefix, raidmode) VALUES ($1, $2, $3)", guild.id, prefix, False)
        
        # if guild.id == 709521003759403063:
        #     Zenpa = self.bot.get_user(373863656607318018)
        #     Moksej = self.bot.get_user(345457928972533773)
        #     support = await self.bot.db.fetchval("SELECT link FROM support")
        #     try:
        #         to_send = sorted([chan for chan in guild.channels if chan.permissions_for(
        #             guild.me).send_messages and isinstance(chan, discord.TextChannel)], key=lambda x: x.position)[0]
        #     except IndexError:
        #         pass
        #     else:
        #         if to_send.permissions_for(guild.me).embed_links:  # We can embed!
        #             e = discord.Embed(
        #                 color=self.bot.join_color, title="A cool bot has spawned in!")
        #             e.description = f"Thank you for adding me to this server! If you'll have any questions you can contact `{Moksej}` or `{Zenpa}`. You can also [join support server]({support})\nTo get started, you can use my commands with my prefix: `{prefix}`, and you can also change the prefix by typing `{prefix}prefix [new prefix]`"
        #             await to_send.send(embed=e)
        #         else:  # We were invited without embed perms...
        #             msg = f"Thank you for adding me to this server! If you'll have any questions you can contact `{Moksej}` or `{Zenpa}`. You can also join support server: {support}\nTo get started, you can use my commands with my prefix: `{prefix}`, and you can also change the prefix by typing `{prefix}prefix [new prefix]`"
        #             await to_send.send(msg)
        # else:
        #     pass

        # Log the join
        logchannel = self.bot.get_channel(703653345948336198) 

        members = len(guild.members)
        bots = len([x for x in guild.members if x.bot])
        tch = len(guild.text_channels)
        vch = len(guild.voice_channels)

        ratio = f'{int(100 / members * bots)}'

        embed = discord.Embed(color=self.bot.logging_color, title="I've joined a guild",
                              description="I've joined a new guild. Informing you for safety reasons")
        embed.set_thumbnail(url=guild.icon_url)
        embed.add_field(name="__**General Info**__",
                        value=f"**Guild name:** {guild.name}\n**Guild ID:** {guild.id}\n**Guild owner:** {guild.owner}\n**Guild owner ID:** {guild.owner.id}\n**Guild created:** {default.date(guild.created_at)} ({default.timeago(datetime.utcnow() - guild.created_at)})\n**Member count:** {members-1} (Bots / Users ratio: {ratio}%)\n**Text channels:** {tch}\n**Voice channels:** {vch}", inline=False)
        await logchannel.send(embed=embed)



    @commands.Cog.listener()
    async def on_guild_remove(self, guild):

        # Delete guild data from the database
        # await self.bot.db.execute("DELETE FROM automods WHERE guild_id = $1", guild.id)
        await self.bot.db.execute("DELETE FROM guilds WHERE guild_id = $1", guild.id)

        # Log the leave
        members = len(guild.members)
        logchannel = self.bot.get_channel(703653345948336198)

        e = discord.Embed(color=self.bot.logging_color, title='I\'ve left the guild...', description=f"**Guild name:** {guild.name}\n**Member count:** {members}")
        await logchannel.send(embed=e)
    
    
    @commands.Cog.listener()
    async def on_message(self, message):
        # We don't want to listen to bots
        if message.author.bot:
            return

        # We dont want to listen to commands
        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        # Something happened in DM's
        if message.guild is None:
            blacklist = await self.bot.db.fetchval("SELECT * FROM blacklist WHERE user_id = $1", message.author.id)

            if blacklist:
                return

            # They DM'ed the bot
            logchannel = self.bot.get_channel(703653345948336198)
            msgembed = discord.Embed(
                title="Received new Direct Message:", description=message.content, color=self.bot.log_color, timestamp=datetime.utcnow())
            msgembed.set_author(name=message.author,
                                icon_url=message.author.avatar_url)
            # They've sent a image/gif/file
            if message.attachments:
                attachment_url = message.attachments[0].url
                msgembed.set_image(url=attachment_url)
            msgembed.set_footer(text=f"User ID: {message.author.id}")
            await logchannel.send(embed=msgembed)


    @commands.Cog.listener('on_message')
    async def afk_check(self, message):
        if message.guild is None:
            return
        
        if message.author.bot:
            return
        
        guild_afk = []
        for userid, in await self.bot.db.fetch("SELECT user_id FROM userafk WHERE guild_id = $1", message.guild.id):
            guild_afk.append(userid)
        afkmsg = ""
        for userid in guild_afk:
            ctx = await self.bot.get_context(message)
            if ctx.valid:
                return
            if userid == message.author.id and not ctx.valid:               
                await message.channel.send(f"Welcome back {message.author.mention}! Removing your AFK state.", delete_after=20)
                mentions = []
                for data in await self.bot.db.fetch("SELECT * FROM afkalert WHERE user_id = $1", message.author.id):
                    mentions.append(f"**{self.bot.get_user(data['author_id'])}** mentioned you - `{data['msgs']}`\n[Jump to message]({data['msglink']})")
                if mentions:
                    e = discord.Embed(color=self.bot.embed_color, title="Mentions log", description="Here's a list of all the messages you were mentioned in while you were afk.")
                    e.add_field(name=f"Total messages ({len(mentions)})", value="\n".join(mentions))
                    try:
                        await message.author.send(embed=e)
                    except:
                        pass
                await self.bot.db.execute("DELETE FROM afkalert WHERE user_id = $1", message.author.id)
                return await self.bot.db.execute("DELETE FROM userafk WHERE user_id = $1 AND guild_id = $2", message.author.id, message.guild.id)
            
            for userids in message.mentions:
                if userids.id == userid:
                    usere = message.guild.get_member(userids)
                    afkmsg += f"{usere} is afk:"
    
        if afkmsg:
            afkmsg = afkmsg.strip()
            if '\n' in afkmsg:
                afkmsg = "\n" + afkmsg
            note = await self.bot.db.fetchval("SELECT message FROM userafk WHERE user_id = $1 AND guild_id = $2", userid, message.guild.id)
            afkuser = message.guild.get_member(userid)
            await self.bot.db.execute("INSERT INTO afkalert(author_id, user_id, msglink, msgs) VALUES ($1, $2, $3, $4)", message.author.id, afkuser.id, message.jump_url, message.content)
            try:
                await message.channel.send(f'{message.author.mention}, {afkuser.name} is AFK, but he left a note: {note}', delete_after=30, allowed_mentions=discord.AllowedMentions(roles=False, everyone=False))
            except discord.HTTPException:
                try:
                    await message.author.send(f"Yo, {afkuser.name} is AFK, but he left a note: {note}")
                except discord.Forbidden:
                    return


    # @commands.Cog.listener('on_message')
    # async def member_presence(self, message):
    #     if message.author.bot:
    #         return

    #     if not message.author.activity:
    #         return
        
    #     check = await self.bot.db.fetchval("SELECT * FROM presence_check WHERE user_id =$1", message.author.id)
    #     if not check:
    #         return
        
    #     if message.author.activity:
    #         for activity in message.author.activities:
    #             if activity.type == discord.ActivityType.playing:
    #                 detail = datetime.utcnow() - activity.start
    #                 await self.bot.db.execute("INSERT INTO presence(user_id, activity_name) VALUES ($1, $2)", message.author.id, activity.name)

def setup(bot):
    bot.add_cog(Events(bot))
