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
from discord.ext import commands, tasks
from utils.paginator import Pages
from db import emotes

class automod(commands.Cog, name="Automod"):

    def __init__(self, bot):
        self.bot = bot
        self.help_icon = "<:automod:701056320673153034>"
        self.big_icon = "https://cdn.discordapp.com/attachments/679643465407266817/701055848788787300/channeldeletee.png"
        self.bot.embed_color = 0x0058D6

    async def cog_check(self, ctx):         
        if not ctx.guild:
            return False
        return True

    @commands.command(brief="Automod log channel")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def logchannel(self, ctx, channel: discord.TextChannel = None):
        """ Choose where automod actions will be sent to. """
        
        db_check = await self.bot.db.fetchval("SELECT channel_id FROM automodaction WHERE guild_id = $1", ctx.guild.id)
        db_check1 = await self.bot.db.fetchval("SELECT * FROM automods WHERE guild_id = $1", ctx.guild.id)

        if db_check1 is None:
            return await ctx.send(f"{emotes.red_mark} Please toggle automod before continuing using `{ctx.prefix}toggleautomod`", delete_after=15)

        if channel is None and db_check is not None:
            await self.bot.db.execute(f"DELETE FROM automodaction WHERE guild_id = $1", ctx.guild.id)
            await ctx.send(f"{emotes.white_mark} Stopped logging automod actions.", delete_after=15)
        elif channel is None and db_check is None:
            await ctx.send(f"{emotes.red_mark} You aren't logging automod actions.")
        
        if channel is not None:
            if channel.permissions_for(ctx.guild.me).send_messages == False:
                return await ctx.send(f"{emotes.warning} I can't let you do that! I don't have permissions to talk in {channel.mention}")
            elif channel.permissions_for(ctx.guild.me).send_messages:
                if db_check is None:
                    await self.bot.db.execute(f"INSERT INTO automodaction(guild_id, channel_id) VALUES ($1, $2)", ctx.guild.id, channel.id)
                    await ctx.send(f"{emotes.white_mark} Automod actions will be sent to {channel.mention}", delete_after=15)
                elif db_check is not None:
                    await self.bot.db.execute(f"UPDATE automodaction SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
                    await ctx.send(f"{emotes.white_mark} Automod actions will be sent to {channel.mention} from now on!", delete_after=15)
        
    @commands.command(brief="Toggle automod", description="Enable automod in your server")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True, ban_members=True)
    @commands.bot_has_permissions(manage_guild=True, ban_members=True)
    async def toggleautomod(self, ctx):
        """ Enable or disable automod in your server """
        db_check = await self.bot.db.fetchval("SELECT * FROM automods WHERE guild_id = $1", ctx.guild.id)

        if db_check is None:
            await self.bot.db.execute("INSERT INTO automods(guild_id, punishment) VALUES ($1, $2)", ctx.guild.id, 1)
            self.bot.automod[ctx.guild.id] = 1
            return await ctx.send(f"{emotes.white_mark} Automod was enabled. `{ctx.prefix}punishment <type>` to make it work", delete_after=15)
        
        if db_check is not None:
            await self.bot.db.execute(f"DELETE FROM automods WHERE guild_id = $1", ctx.guild.id)
            self.bot.automod.pop(ctx.guild.id)
            return await ctx.send(f"{emotes.white_mark} Automod was disabled.", delete_after=15)
    
    @commands.group(brief="Toggle automod actions", invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_guild=True)
    async def punishment(self, ctx):
        """ Setup automod action for each category.
        When everything is setup, automod will:
        1st punish: delete the message
        2nd punish: warn the member
        3rd punish: ban the member """
        # ! caps, inv, link, massmention
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @punishment.command()
    @commands.bot_has_permissions(manage_guild=True)
    @commands.has_permissions(manage_guild=True)
    async def invites(self, ctx):
        """ Invites automod """
        check = await self.bot.db.fetchval("SELECT * FROM inv WHERE guild_id = $1", ctx.guild.id)
        db_check = await self.bot.db.fetchval("SELECT * FROM automods WHERE guild_id = $1", ctx.guild.id)

        if db_check is None:
            return await ctx.send(f"{emotes.red_mark} Please toggle automod before continuing using `{ctx.prefix}toggleautomod`", delete_after=15)

        elif db_check is not None and check is None:
            await self.bot.db.execute("INSERT INTO inv(guild_id, punishment) VALUES ($1, $2)", ctx.guild.id, 1)
            await ctx.send(f"{emotes.white_mark} People who will be sending invites will be punished now.")
        elif db_check is not None and check is not None:
            await self.bot.db.execute("DELETE FROM inv WHERE guild_id = $1", ctx.guild.id)
            await ctx.send(f"{emotes.white_mark} People who will be sending invites won't be punished anymore")

    @punishment.command()
    @commands.bot_has_permissions(manage_guild=True)
    @commands.has_permissions(manage_guild=True)
    async def links(self, ctx):
        """ Links automod """
        check = await self.bot.db.fetchval("SELECT * FROM link WHERE guild_id = $1", ctx.guild.id)
        db_check = await self.bot.db.fetchval("SELECT * FROM automods WHERE guild_id = $1", ctx.guild.id)

        if db_check is None:
            return await ctx.send(f"{emotes.red_mark} Please toggle automod before continuing using `{ctx.prefix}toggleautomod`", delete_after=15)

        elif db_check is not None and check is None:
            await self.bot.db.execute("INSERT INTO link(guild_id, punishment) VALUES ($1, $2)", ctx.guild.id, 1)
            await ctx.send(f"{emotes.white_mark} People who will be sending links will be punished now.")
        elif db_check is not None and check is not None:
            await self.bot.db.execute("DELETE FROM link WHERE guild_id = $1", ctx.guild.id)
            await ctx.send(f"{emotes.white_mark} People who will be sending links won't be punished anymore")
    
    @punishment.command(aliases=['mm', 'mentions'])
    @commands.bot_has_permissions(manage_guild=True)
    @commands.has_permissions(manage_guild=True)
    async def massmentions(self, ctx):
        """ Mass mentions automod """
        check = await self.bot.db.fetchval("SELECT * FROM massmention WHERE guild_id = $1", ctx.guild.id)
        db_check = await self.bot.db.fetchval("SELECT * FROM automods WHERE guild_id = $1", ctx.guild.id)

        if db_check is None:
            return await ctx.send(f"{emotes.red_mark} Please toggle automod before continuing using `{ctx.prefix}toggleautomod`", delete_after=15)

        elif db_check is not None and check is None:
            await self.bot.db.execute("INSERT INTO massmention(guild_id, punishment) VALUES ($1, $2)", ctx.guild.id, 1)
            await ctx.send(f"{emotes.white_mark} People who will be mass mentioning will be punished now.\nDefault number is set to `3` mentions per message, but you can change it with `{ctx.prefix}mentions <number>`")
        elif db_check is not None and check is not None:
            await self.bot.db.execute("DELETE FROM massmention WHERE guild_id = $1", ctx.guild.id)
            await ctx.send(f"{emotes.white_mark} People who will be mass mentioning won't be punished anymore")
        
    @punishment.command(aliases=['caps'])
    @commands.bot_has_permissions(manage_guild=True)
    @commands.has_permissions(manage_guild=True)
    async def masscaps(self, ctx):
        """ Mass caps automod """
        check = await self.bot.db.fetchval("SELECT * FROM caps WHERE guild_id = $1", ctx.guild.id)
        db_check = await self.bot.db.fetchval("SELECT * FROM automods WHERE guild_id = $1", ctx.guild.id)

        if db_check is None:
            return await ctx.send(f"{emotes.red_mark} Please toggle automod before continuing using `{ctx.prefix}toggleautomod`", delete_after=15)

        elif db_check is not None and check is None:
            await self.bot.db.execute("INSERT INTO caps(guild_id, punishment) VALUES ($1, $2)", ctx.guild.id, 1)
            await ctx.send(f"{emotes.white_mark} People who will be sending mass caps will be punished now.")
        elif db_check is not None and check is not None:
            await self.bot.db.execute("DELETE FROM caps WHERE guild_id = $1", ctx.guild.id)
            await ctx.send(f"{emotes.white_mark} People who will be sending mass caps won't be punished anymore")

    @commands.command(brief="Mass mentions limit")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_guild=True)
    async def mentions(self, ctx, limit: int):
        """ Choose how many mentions are allowed at once """

        #return await ctx.send("For performance issues this was disabled")

        db_check = await self.bot.db.fetchval("SELECT mentions FROM mentions WHERE guild_id = $1", ctx.guild.id)
        db_check1 = await self.bot.db.fetchval("SELECT punishment FROM massmention WHERE guild_id = $1", ctx.guild.id)
        db_check2 = await self.bot.db.fetchval("SELECT punishment FROM automods WHERE guild_id = $1", ctx.guild.id)

        if db_check2 is None:
            return await ctx.send(f"{emotes.red_mark} Please toggle the automod on before you set mass mentions limit using `{ctx.prefix}toggleautomod`", delete_after=15)
        
        if db_check1 is None:
            return await ctx.send(f"{emotes.red_mark} Please toggle mass mentions automod using `{ctx.prefix}punishment massmentions` before you set the mass mentions limiter")

        if limit is not None:
            if limit <= 0:
                return await ctx.send("You cannot setup that number!", delete_after=15)
            if db_check is None:
                await self.bot.db.execute(f"INSERT INTO mentions(guild_id, mentions) VALUES ($1, $2)", ctx.guild.id, limit)
                embed = discord.Embed(color=self.bot.embed_color, description=f"{emotes.white_mark} Mass mentions were set to `{limit}`.", delete_after=15)
                return await ctx.send(embed=embed)
            elif db_check is not None:
                await self.bot.db.execute("UPDATE mentions SET mentions = $1 WHERE guild_id  = $2", limit, ctx.guild.id)
                embed = discord.Embed(color=self.bot.embed_color, description=f"{emotes.white_mark} Mass mentions were set to `{limit}`.", delete_after=15)
                return await ctx.send(embed=embed)

    @commands.group(brief="Automod white channels", aliases=["wc"], invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def whitelist(self, ctx):

        """ Choose which channels and roles won't get affected by automod """
        return await ctx.send_help(ctx.command)

    @whitelist.group(brief='Add whitelisted channels', invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def channel(self, ctx):

        return await ctx.send_help(ctx.command)
    
    @channel.command(brief="Add a channel", name='add')
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def _add(self, ctx, channel: discord.TextChannel):
        """ Add channels that won't get moderated """
 
        db_check = await self.bot.db.fetch("SELECT channel_id FROM whitelist WHERE guild_id = $1", ctx.guild.id)

        if str(channel.id) in str(db_check):
            return await ctx.send(f"{emotes.red_mark} {channel.mention} is already whitelisted", delete_after=15)

        if str(channel.id) not in str(db_check):
            await self.bot.db.execute("INSERT INTO whitelist(guild_id, channel_id) VALUES ($1, $2)", ctx.guild.id, channel.id)
            await ctx.send(f"{emotes.white_mark} {channel.mention} was added to automod whitelist", delete_after=15)
    
    @channel.command(brief="Remove whitelisted channel")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def remove(self, ctx, channel: discord.TextChannel):
        """ Remove channels that aren't being moderated """

        db_check = await self.bot.db.fetch("SELECT channel_id FROM whitelist WHERE guild_id = $1", ctx.guild.id)

        if str(channel.id) in str(db_check):
            await self.bot.db.execute("DELETE FROM whitelist WHERE guild_id = $1 AND channel_id = $2", ctx.guild.id, channel.id)
            return await ctx.send(f"{emotes.white_mark} {channel.mention} was removed from the whitelist", delete_after=15)

        if str(channel.id) not in str(db_check):
            await ctx.send(f"{emotes.red_mark} {channel.mention} is not in the whitelist", delete_after=15)
    
    @channel.command(brief="Remove whitelisted channels")
    @commands.has_permissions(manage_guild=True)
    async def removeall(self, ctx):
        """ Remove all whitelisted channels """

        db_check = await self.bot.db.fetch("SELECT channel_id FROM whitelist WHERE guild_id = $1 AND role_id is null", ctx.guild.id)

        if db_check is None:
            return await ctx.send(f"{emotes.red_mark} You have 0 channels whitelisted from automod.", delete_after=15)

        if db_check is not None:

            def check(r, u):
                return u.id == ctx.author.id and r.message.id == checkmsg.id
            checkmsg = await ctx.send(f"Are you sure you want to remove all **{len(db_check)}** channels from the guild?")
            await checkmsg.add_reaction(f'{emotes.white_mark}')
            await checkmsg.add_reaction(f'{emotes.red_mark}')
            react, user = await self.bot.wait_for('reaction_add', check=check)

            if str(react) == f"{emotes.white_mark}":
                await checkmsg.delete()
                await self.bot.db.execute("DELETE FROM whitelist WHERE role_id is null AND guild_id = $1", ctx.guild.id)
                return await ctx.send(f"{emotes.white_mark} {len(db_check)} channel(s) were removed from the whitelist", delete_after=15)
            
            if str(react) == f"{emotes.red_mark}":
                await checkmsg.delete()
                return await ctx.send("Not removing channels.", delete_after=15)
        
    @channel.command(brief="List of whitelisted channels", name="list")
    @commands.has_permissions(manage_guild=True)
    async def _list(self, ctx):

        channelids = []
        for num, res in enumerate(await self.bot.db.fetch("SELECT * FROM whitelist WHERE guild_id = $1 AND role_id is null", ctx.guild.id), start=0):
            channelids.append(f"`[{num + 1}]`{ctx.guild.get_channel(res['channel_id']).mention}\n")

        if len(channelids) == 0:
            return await ctx.send(f"{emotes.red_mark} Server has no whitelisted channels.")

        paginator = Pages(ctx,
                          title=f"Whitelisted channels from automod:",
                          entries=channelids,
                          thumbnail=None,
                          per_page = 15,
                          embed_color=ctx.bot.embed_color,
                          show_entry_count=True,
                          author=ctx.author)
        await paginator.paginate()

    @whitelist.group(brief="Add whitelisted roles", invoke_without_command=True)
    @commands.has_permissions(manage_guild=True)
    async def role(self, ctx):
        return await ctx.send_help(ctx.command)

    @role.command(brief='Add a role')
    @commands.has_permissions(manage_guild=True)
    async def add(self, ctx, role: discord.Role):

        db_check = await self.bot.db.fetch("SELECT role_id FROM whitelist WHERE guild_id = $1 AND channel_id is null", ctx.guild.id)

        if role == ctx.guild.default_role:
            return await ctx.send(f"{emotes.red_mark} If you're adding {role.mention} to the whitelist, why do you even enable automod?", delete_after=15, allowed_mentions=discord.AllowedMentions(roles=False, everyone=False))

        if str(role.id) in str(db_check):
            return await ctx.send(f"{emotes.red_mark} {role.mention} is already whitelisted", delete_after=15, allowed_mentions=discord.AllowedMentions(roles=False, everyone=False))

        if str(role.id) not in str(db_check):
            await self.bot.db.execute("INSERT INTO whitelist(guild_id, role_id) VALUES ($1, $2)", ctx.guild.id, role.id)
            await ctx.send(f"{emotes.white_mark} {role.mention} was added to automod whitelist", delete_after=15, allowed_mentions=discord.AllowedMentions(roles=False, everyone=False))
    
    @role.command(brief="Remove whitelisted role")
    @commands.has_permissions(manage_guild=True)
    async def remove(self, ctx, role: discord.Role):
        """ Remove channels that aren't being moderated """

        db_check = await self.bot.db.fetch("SELECT role_id FROM whitelist WHERE guild_id = $1 AND channel_id is null", ctx.guild.id)

        if str(role.id) in str(db_check):
            await self.bot.db.execute("DELETE FROM whitelist WHERE guild_id = $1 AND role_id = $2", ctx.guild.id, role.id)
            return await ctx.send(f"{emotes.white_mark} {role.mention} was removed from the whitelist", delete_after=15, allowed_mentions=discord.AllowedMentions(roles=False, everyone=False))

        if str(role.id) not in str(db_check):
            await ctx.send(f"{emotes.red_mark} {role.mention} is not in the whitelist", delete_after=15, allowed_mentions=discord.AllowedMentions(roles=False, everyone=False))
    
    @role.command(brief="Remove whitelisted role(s)", name='removeall')
    @commands.has_permissions(manage_guild=True)
    async def role_removeall(self, ctx):
        """ Remove all whitelisted role(s) """

        db_check = await self.bot.db.fetch("SELECT role_id FROM whitelist WHERE guild_id = $1 AND channel_id is null", ctx.guild.id)

        if db_check is None:
            return await ctx.send(f"{emotes.red_mark} You have 0 roles whitelisted from automod.", delete_after=15)

        if db_check is not None:

            def check(r, u):
                return u.id == ctx.author.id and r.message.id == checkmsg.id
            checkmsg = await ctx.send(f"Are you sure you want to remove all **{len(db_check)}** channels from the guild?")
            await checkmsg.add_reaction(f'{emotes.white_mark}')
            await checkmsg.add_reaction(f'{emotes.red_mark}')
            react, user = await self.bot.wait_for('reaction_add', check=check)

            if str(react) == f"{emotes.white_mark}":
                await checkmsg.delete()
                await self.bot.db.execute("DELETE FROM whitelist WHERE channel_id is null AND guild_id = $1", ctx.guild.id)
                return await ctx.send(f"{emotes.white_mark} {len(db_check)} role(s) were removed from the whitelist", delete_after=15)
            
            if str(react) == f"{emotes.red_mark}":
                await checkmsg.delete()
                return await ctx.send("Not removing role(s).", delete_after=15)
    
    @role.command(brief="List of whitelisted role(s)", name="list")
    @commands.has_permissions(manage_guild=True)
    async def role_list(self, ctx):

        roleids = []
        for num, res in enumerate(await self.bot.db.fetch("SELECT * FROM whitelist WHERE guild_id = $1 AND channel_id is null", ctx.guild.id), start=0):
            roleids.append(f"`[{num + 1}]`{ctx.guild.get_role(res['role_id']).mention}\n")

        if len(roleids) == 0:
            return await ctx.send(f"{emotes.red_mark} Server has no whitelisted roles.")

        paginator = Pages(ctx,
                          title=f"Whitelisted roles from automod:",
                          entries=roleids,
                          thumbnail=None,
                          per_page = 15,
                          embed_color=ctx.bot.embed_color,
                          show_entry_count=True,
                          author=ctx.author)
        await paginator.paginate()

    @commands.command(brief='Automod warnings')
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.has_permissions(manage_guild=True)
    async def autowarns(self, ctx, member: discord.Member):
        """ Check how many times automod punished a member """

        ch = await self.bot.db.fetchval("SELECT * FROM autowarns WHERE guild_id = $1 AND user_id = $2", ctx.guild.id, member.id)

        if ch is None:
            return await ctx.send(f"{emotes.red_mark} {member.name} has no automod warnings")

        for res in await self.bot.db.fetch("SELECT * FROM autowarns WHERE guild_id = $1 AND user_id = $2", ctx.guild.id, member.id):
            links = f"{res['links']}"
            inv = f"{res['inv']}"
            mm = f"{res['mm']}"
            caps = f"{res['caps']}"

        e = discord.Embed(color=self.bot.embed_color, title=f"**{member}'s** automod warnings")
        e.description = f"""
**Links:** {links} time(s)
**Invites:** {inv} time(s)
**Mass mentions:** {mm} time(s)
**Caps:** {caps} time(s)"""

        return await ctx.send(embed=e)


    @commands.command(brief='Clear member\'s automod warnings')
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def clearautowarns(self, ctx, member: discord.Member):
        ch = await self.bot.db.fetchval("SELECT * FROM autowarns WHERE guild_id = $1 AND user_id = $2", ctx.guild.id, member.id)

        if ch is None:
            return await ctx.send(f"{emotes.red_mark} {member} has no automod warnings.")
        elif ch:
            try:
                def check(r, u):
                    return u.id == ctx.author.id and r.message.id == checkmsg.id
                    
                checkmsg = await ctx.send(f"Are you sure you want to clear all {member}'s autowarns from this guild? This cannot be undone.")
                await checkmsg.add_reaction(f'{emotes.white_mark}')
                await checkmsg.add_reaction(f'{emotes.red_mark}')
                react, user = await self.bot.wait_for('reaction_add', check=check, timeout=30.0)

                if str(react) == f"{emotes.white_mark}":
                    await self.bot.db.execute("DELETE FROM autowarns WHERE guild_id = $1 AND user_id = $2", ctx.guild.id, member.id)
                    await checkmsg.edit(content=f"{emotes.white_mark} Cleared {member}'s automod warnings.")
                    await checkmsg.clear_reactions()

                elif str(react) == f"{emotes.red_mark}":
                    await checkmsg.edit(content=f"Not clearing {member}'s autowarns.")
                    await checkmsg.clear_reactions()

                else:
                    await checkmsg.edit(content="Uh oh! Something failed")
                    await checkmsg.clear_reactions()


            except Exception as e:
                return
            
    @commands.command(brief="Automod settings in guild", aliases=['autosettings', 'autoinfo'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def automodsettings(self, ctx):
        """ Check automod settings in your server """

        db_check1 = await self.bot.db.fetchval("SELECT punishment FROM automods WHERE guild_id = $1", ctx.guild.id)
        db_check2 = await self.bot.db.fetchval('SELECT punishment FROM caps WHERE guild_id = $1', ctx.guild.id)
        db_check3 = await self.bot.db.fetchval('SELECT punishment FROM inv WHERE guild_id = $1', ctx.guild.id)
        db_check4 = await self.bot.db.fetchval('SELECT punishment FROM link WHERE guild_id = $1', ctx.guild.id)
        db_check5 = await self.bot.db.fetchval('SELECT punishment FROM massmention WHERE guild_id = $1', ctx.guild.id)
        db_check8 = await self.bot.db.fetchval("SELECT channel_id FROM automodaction WHERE guild_id = $1", ctx.guild.id)



        logs = f"{f'{emotes.setting_no}' if db_check1 is None else f'{emotes.setting_yes}'} Automod\n"
        logs += f"{f'{emotes.setting_no}' if db_check2 is None else f'{emotes.setting_yes}'} Caps monitoring\n"
        logs += f"{f'{emotes.setting_no}' if db_check3 is None else f'{emotes.setting_yes}'} Invites monitoring\n"
        logs += f"{f'{emotes.setting_no}' if db_check4 is None else f'{emotes.setting_yes}'} Links monitoring\n"
        logs += f"{f'{emotes.setting_no}' if db_check5 is None else f'{emotes.setting_yes}'} Mass mentions monitoring\n"
        # logs += f"{f'{emotes.setting_no}' if db_check7 is None else f'{emotes.setting_yes}'} Whitelisted channels/Roles\n"
        logs += f"{f'{emotes.setting_no}' if db_check8 is None else f'{emotes.setting_yes}'} Monitoring automod actions\n"

        e = discord.Embed(color=self.bot.embed_color, title=f"{emotes.log_settings} Automod settings", description=logs)
        await ctx.send(embed=e)



def setup(bot):
    bot.add_cog(automod(bot))