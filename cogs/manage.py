"""
Dredd.
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
import time
import datetime
import json
from discord.ext import commands, tasks
from datetime import datetime
from utils import default
from db import emotes

class Managment(commands.Cog, name="Management"):

    def __init__(self, bot):
        self.bot = bot
        self.help_icon = "<:settingss:695707235833085982>"
        self.big_icon = "https://cdn.discordapp.com/emojis/695707235833085982.png?v=1"

    
    async def bot_check(self, ctx):
        cmd = self.bot.get_command(ctx.command.name)
        data = await self.bot.db.fetchval("select * from guilddisabled where command = $1 and guild_id = $2", str(cmd), ctx.guild.id)

        if ctx.author is ctx.guild.owner:
            return True

        if data is not None:
            await ctx.send(f"{emotes.blacklisted} | `{cmd}` is disabled in this server", delete_after=20)
            return False
        
        if data is None:
            return True


    @commands.command(brief="Change prefix", description="Change my prefix in the server")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 20, commands.BucketType.guild)
    async def prefix(self, ctx, prefix: str = None):
        """ Change bot's prefix in the server """

        prefixs = await self.bot.db.fetchval("SELECT prefix FROM guilds WHERE guild_id = $1", ctx.guild.id)
        if prefix is None:
            return await ctx.send(f"Your server prefix is `{prefixs}`")

        elif prefix and len(prefix) < 6:
            await self.bot.db.execute("UPDATE guilds SET prefix = $1 WHERE guild_id = $2", prefix, ctx.guild.id)
            await ctx.send(f"Changed server prefix to `{prefix}`!")
        else:
            await ctx.send(f"{emotes.warning} Prefix is too long!")

    @commands.command(brief="Guild settings", aliases=['guildsettings', 'settings'])
    @commands.guild_only()
    @commands.cooldown(1, 20, commands.BucketType.guild)
    async def serversettings(self, ctx):
        """ Show all guild settings whether they're enabled or disabled """

        db_check1 = await self.bot.db.fetchval("SELECT guild_id FROM msgdelete WHERE guild_id = $1", ctx.guild.id)
        db_check2 = await self.bot.db.fetchval("SELECT guild_id FROM moderation WHERE guild_id = $1", ctx.guild.id)
        db_check3 = await self.bot.db.fetchval("SELECT guild_id FROM msgedit WHERE guild_id = $1", ctx.guild.id)
        db_check4 = await self.bot.db.fetchval("SELECT guild_id FROM joinlog WHERE guild_id = $1", ctx.guild.id)
        db_check6 = await self.bot.db.fetchval("SELECT guild_id FROM memberupdate WHERE guild_id = $1", ctx.guild.id)
        db_check7 = await self.bot.db.fetchval("SELECT guild_id FROM joinmsg WHERE guild_id = $1", ctx.guild.id)
        db_check8 = await self.bot.db.fetchval("SELECT guild_id FROM joinrole WHERE guild_id = $1", ctx.guild.id)
        db_check9 = await self.bot.db.fetchval("SELECT guild_id FROM leavemsg WHERE guild_id = $1", ctx.guild.id)
        db_check10 = await self.bot.db.fetchval("SELECT guild_id FROM automodaction WHERE guild_id = $1", ctx.guild.id)
        db_check11 = await self.bot.db.fetchval("SELECT punishment FROM automods WHERE guild_id = $1", ctx.guild.id)

        logs  = f"{f'{emotes.setting_no}' if db_check3 is None else f'{emotes.setting_yes}'} Edited messages\n"
        logs += f"{f'{emotes.setting_no}' if db_check1 is None else f'{emotes.setting_yes}'} Deleted messages\n"
        logs += f"{f'{emotes.setting_no}' if db_check2 is None else f'{emotes.setting_yes}'} Moderation\n"
        logs += f"{f'{emotes.setting_no}' if db_check4 is None else f'{emotes.setting_yes}'} Member Joins\n"
        logs += f"{f'{emotes.setting_no}' if db_check6 is None else f'{emotes.setting_yes}'} Member Updates\n"
        logs += f"{f'{emotes.setting_no}' if db_check10 is None else f'{emotes.setting_yes}'} Automod actions\n"

        settings = f"{f'{emotes.setting_no}' if db_check8 is None else f'{emotes.setting_yes}'} Role On Join\n"
        settings += f"{f'{emotes.setting_no}' if db_check7 is None else f'{emotes.setting_yes}'} Welcoming Messages\n"
        settings += f"{f'{emotes.setting_no}' if db_check9 is None else f'{emotes.setting_yes}'} Leaving Messages\n"
        #settings += f"{'<:off_switch:687015661901316405>' if db_check11 == 0 else '<:on_switch:687015662039859201>'} Automod\n"
        if db_check11 == 0 or db_check11 is None:
            mode = "Disabled"
        else:
            mode = "Enabled"


        embed = discord.Embed(color=self.bot.embed_color, description=f"{emotes.log_settings} **{ctx.guild}** server settings")
        embed.add_field(name="Logs:", value=logs, inline=False)
        embed.add_field(name="Settings:", value=settings, inline=False)
        check = await self.bot.db.fetchval("SELECT mentions FROM mentions WHERE guild_id = $1", ctx.guild.id)
        if check is not None:
            other = ''
            if check != 0:
                other += f"Mass mentions limit: **{check}**\n"
            other += f"Automod: **{mode}**"
            embed.add_field(name="Other:", value=other, inline=False)
        else:
            pass

        await ctx.send(embed=embed)
    
    @commands.command(brief="Log channels", description="Enable logging in your server.")
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(manage_messages=True, view_audit_log=True, manage_channels=True)
    async def togglelog(self, ctx, option = None, *, channel: discord.TextChannel = None):
        """ Toggle log for the given option.  
        Leaving channel empty will disable the log. """

        options = ["msgdelete", "msgedit", "moderation", "joinlog", "joinmsg", "leavemsg", "memberupdate"]
        optionsmsg = f'`joinlog`, `memberupdate`, `msgedit`, `msgdelete`, `moderation`, `joinmsg`, `leavemsg`'



        if option is None or option.lower() not in options:
            e = discord.Embed(color=self.bot.embed_color,
                              title=f"{emotes.blacklisted} Invalid option was given. Here are all the valid options:",
                              description=optionsmsg)
            #e.set_footer(text=f"© {self.bot.user}")
            return await ctx.send(embed=e)


        db_check = await self.bot.db.fetchval(f"SELECT guild_id FROM {option} WHERE guild_id = $1", ctx.guild.id)           

            
        
        if channel is None:
            await self.bot.db.execute(f"DELETE FROM {option} WHERE guild_id = $1", ctx.guild.id)
            if option.lower() == 'msgedit':
                if db_check is None:
                    return await ctx.send(f"{emotes.red_mark} Message edit logs aren't enabled in this server", delete_after=20)
                await ctx.send(f"{emotes.white_mark} Message edit logs have been disabled in this server", delete_after=20)
            elif option.lower() == 'msgdelete':
                if db_check is None:
                    return await ctx.send(f"{emotes.red_mark} Message delete logs aren't enabled in this server", delete_after=20)
                await ctx.send(f"{emotes.white_mark} Message delete logs have been disabled in this server", delete_after=20)
            elif option.lower() == 'moderation':
                if db_check is None:
                    return await ctx.send(f"{emotes.red_mark} Moderation logs aren't enabled in this server", delete_after=20)
                await ctx.send(f"{emotes.white_mark} Moderation have been disabled in this server", delete_after=20)
            elif option.lower() == 'joinlog':
                if db_check is None:
                    return await ctx.send(f"{emotes.red_mark} Join logs aren't enabled in this server", delete_after=20)
                await ctx.send(f"{emotes.white_mark} Join logs have been disabled in this server", delete_after=20)
            elif option.lower() == 'joinmsg':
                if db_check is None:
                    return await ctx.send(f"{emotes.red_mark} Join messages logs aren't enabled in this server", delete_after=20)
                await ctx.send(f"{emotes.white_mark} Join messages logs have been disabled in this server", delete_after=20)
            elif option.lower() == 'leavemsg':
                if db_check is None:
                    return await ctx.send(f"{emotes.red_mark} Leave messages logs aren't enabled in this server", delete_after=20)
                await ctx.send(f"{emotes.white_mark} Leave messages logs have been disabled in this server", delete_after=20)
            elif option.lower() == 'memberupdate':
                if db_check is None:
                    return await ctx.send(f"{emotes.red_mark} Member update logs aren't enabled in this server", delete_after=20)
                await ctx.send(f"{emotes.white_mark} Member update logs have been disabled in this server", delete_after=20)

        elif channel is not None:
            if db_check is None:
                await self.bot.db.execute(f"INSERT INTO {option}(guild_id, channel_id) VALUES ($1, $2)", ctx.guild.id, channel.id)
            if db_check is not None:
                await self.bot.db.execute(f"UPDATE {option} SET channel_id = $1 WHERE guild_id = $2", channel.id, ctx.guild.id)
            if option.lower() == 'msgedit':
                if db_check is not None:
                    return await ctx.send(f"{emotes.white_mark} Message edit logs will be sent to {channel.mention} from now on!", delete_after=20)
                await ctx.send(f"{emotes.white_mark} Message edit logs have been enabled in this server and will be sent to {channel.mention}!", delete_after=20)
            elif option.lower() == 'msgdelete':
                if db_check is not None:
                    return await ctx.send(f"{emotes.white_mark} Message delete logs will be sent to {channel.mention} from now on!", delete_after=20)
                await ctx.send(f"{emotes.white_mark} Message delete logs have been enabled in this server and will be sent to {channel.mention}!", delete_after=20)
            elif option.lower() == 'moderation':
                if db_check is not None:
                    return await ctx.send(f"{emotes.white_mark} Moderation logs will be sent to {channel.mention} from now on!", delete_after=20)
                await ctx.send(f"{emotes.white_mark} Moderation logs have been enabled in this server and will be sent to {channel.mention}!", delete_after=20)
            elif option.lower() == 'joinlog':
                if db_check is not None:
                    return await ctx.send(f"{emotes.white_mark} Join logs will be sent to {channel.mention} from now on!", delete_after=20)
                await ctx.send(f"{emotes.white_mark} Join logs have been enabled in this server and will be sent to {channel.mention}!", delete_after=20)
            elif option.lower() == 'joinmsg':
                if db_check is not None:
                    return await ctx.send(f"{emotes.white_mark} Welcoming messages will be sent to {channel.mention} from now on!", delete_after=20)
                await ctx.send(f"{emotes.white_mark} Welcoming messages have been enabled in this server and will be sent to {channel.mention}! You can change the welcoming message by typing `{ctx.prefix}togglemsg joinmsg [message]`", delete_after=20)
            elif option.lower() == 'leavemsg':
                if db_check is not None:
                    return await ctx.send(f"{emotes.white_mark} Leaving messages will be sent to {channel.mention} from now on!", delete_after=20)
                await ctx.send(f"{emotes.white_mark} Leaving messages have been enabled in this server and will be sent to {channel.mention}! You can change the leaving message by typing `{ctx.prefix}togglemsg leavemsg [message]`", delete_after=20)
            elif option.lower() == 'memberupdate':
                if db_check is not None:
                    return await ctx.send(f"{emotes.white_mark} Member update logs will be sent to {channel.mention} from now on!", delete_after=20)
                await ctx.send(f"{emotes.white_mark} Member update logs have been enabled in this server and will be sent to {channel.mention}!", delete_after=20)

    @commands.group(brief="Change the welcoming and leaving messages")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def togglemsg(self, ctx):
        """ Setup welcoming and leaving messages in your server. 
        `::member.mention::` - Mentions a member that joined/left
        `::member.name::` - Displays name of member that joined/left
        `::server.name::` - Displays server name
        `::server.members::` - Displays how many members server has """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @togglemsg.command()
    async def welcoming(self, ctx, *, message: str = None):

        db_check = await self.bot.db.fetchval("SELECT * FROM joinmsg WHERE guild_id = $1", ctx.guild.id)

        if db_check:
            if message is None:
                await self.bot.db.execute("UPDATE joinmsg SET msg = $1 WHERE guild_id = $2", None, ctx.guild.id)
                await ctx.send(f"{emotes.white_mark} Changed welcoming message to default one.")
            elif message:
                await self.bot.db.execute("UPDATE joinmsg SET msg = $1 WHERE guild_id = $2", message, ctx.guild.id)
                await ctx.send(f"{emotes.white_mark} Changed welcoming message to `{message}`")
        elif db_check is None:
            return await ctx.send(f"{emotes.red_mark} Please enable welcoming messages first by typing `{ctx.prefix}togglelog joinmsg [channel mention]`")

    @togglemsg.command()
    async def leaving(self, ctx, *, message: str = None):

        db_check = await self.bot.db.fetchval("SELECT * FROM leavemsg WHERE guild_id = $1", ctx.guild.id)

        if db_check:
            if message is None:
                await self.bot.db.execute("UPDATE leavemsg SET msg = $1 WHERE guild_id = $2", None, ctx.guild.id)
                await ctx.send(f"{emotes.white_mark} Changed leaving message to default one.")
            elif message:
                await self.bot.db.execute("UPDATE leavemsg SET msg = $1 WHERE guild_id = $2", message, ctx.guild.id)
                await ctx.send(f"{emotes.white_mark} Changed leaving message to `{message}`")
        elif db_check is None:
            return await ctx.send(f"{emotes.red_mark} Please enable leaving messages first by typing `{ctx.prefix}togglelog leavemsg [channel mention]`")

    @commands.group(brief="Role on join", description="Setup and toggle role on join")
    @commands.has_permissions(manage_roles=True)
    @commands.bot_has_permissions(manage_roles=True)
    async def joinrole(self, ctx):
        """ Toggle role that will be given to new members """

        if ctx.invoked_subcommand is None:
            db_check = await self.bot.db.fetchval("SELECT guild_id FROM joinrole WHERE guild_id = $1", ctx.guild.id)
            role = await self.bot.db.fetchval("SELECT role_id FROM joinrole WHERE guild_id = $1", ctx.guild.id)
            bots = await self.bot.db.fetchval("SELECT bots FROM joinrole WHERE guild_id = $1", ctx.guild.id)

            if db_check is None:
                return await ctx.send(f"Role on join is disabled in this server.")
            if role and bots:
                roled = ctx.guild.get_role(role)
                roledd = ctx.guild.get_role(bots)
                return await ctx.send(f"**{roled.mention}** ({roled.id}) is role that new members will get and **{roledd.mention}** ({roledd.id}) is role that bots will get!", delete_after=30)
            elif role and not bots:
                roled = ctx.guild.get_role(role)
                return await ctx.send(f"**{roled.mention}** ({roled.id}) is role that new members will get!", delete_after=30)
            elif bots and not role:
                roledd = ctx.guild.get_role(bots)
                return await ctx.send(f"**{roledd.mention}** ({roledd.id}) is role that bots will get!", delete_after=30)

    @joinrole.command(brief="Set role on join for people", description="Set role that new members will get when they join", name="people")
    async def joinrole_people(self, ctx, role: discord.Role):
        """ Choose what role will be given to new members"""

        if role.position == ctx.guild.me.top_role.position or role.position > ctx.guild.me.top_role.position:
            return await ctx.send(f"{emotes.red_mark} The role you've tried to setup is higher than my role. Please make sure I'm above the role you're trying to setup.")

        else:
            db_check = await self.bot.db.fetchval("SELECT guild_id FROM joinrole WHERE guild_id = $1", ctx.guild.id)

            user_role = await self.bot.db.fetchval("SELECT role_id FROM joinrole WHERE guild_id = $1", ctx.guild.id)

                
            if db_check is None:
                await self.bot.db.execute(f"INSERT INTO joinrole(guild_id, role_id) VALUES ($1, $2)", ctx.guild.id, role.id)
                await ctx.send(f"{emotes.white_mark} **{role.mention}** will be given to new members! Use `{ctx.prefix}joinrole toggle` to **disable** it or `{ctx.prefix}joinrole people` to change it", delete_after=30)
            if db_check is not None:
                if user_role is None:
                    await self.bot.db.execute(f"UPDATE joinrole SET role_id = $1 WHERE guild_id = $2", role.id, ctx.guild.id)
                    await ctx.send(f"{emotes.white_mark} **{role.mention}** will be given to members! Use `{ctx.prefix}joinrole toggle` to disable it or `{ctx.prefix}joinrole people` to change it", delete_after=30)
                elif user_role is not None:
                    await self.bot.db.execute(f"UPDATE joinrole SET role_id = $1 WHERE guild_id = $2", role.id, ctx.guild.id)
                    await ctx.send(f"{emotes.white_mark} **{role.mention}** will be given to members from now one! Use `{ctx.prefix}joinrole toggle` to disable it or `{ctx.prefix}joinrole people` to change it", delete_after=30)

    @joinrole.command(brief="Set role on join for bots", description="Set role that bots will get when they join", name="bots")
    async def joinrole_bots(self, ctx, role: discord.Role):
        """ Choose what role will be given to bots"""

        if role.position == ctx.guild.me.top_role.position or role.position > ctx.guild.me.top_role.position:
            return await ctx.send(f"{emotes.red_mark} The role you've tried to setup is higher than my role. Please make sure I'm above the role you're trying to setup.")

        else:
            db_check = await self.bot.db.fetchval("SELECT guild_id FROM joinrole WHERE guild_id = $1", ctx.guild.id)
            bot_role = await self.bot.db.fetchval("SELECT bots FROM joinrole WHERE guild_id = $1", ctx.guild.id)
                
            if db_check is None:
                await self.bot.db.execute(f"INSERT INTO joinrole(guild_id, bots) VALUES ($1, $2)", ctx.guild.id, role.id)
                await ctx.send(f"{emotes.white_mark} **{role.mention}** will be given to bots! Use `{ctx.prefix}joinrole toggle` to **disable** it or `{ctx.prefix}joinrole bots` to change it", delete_after=30)
            if db_check is not None:
                if bot_role is None:
                    await self.bot.db.execute(f"UPDATE joinrole SET bots = $1 WHERE guild_id = $2", role.id, ctx.guild.id)
                    await ctx.send(f"{emotes.white_mark} **{role.mention}** will be given to bots! Use `{ctx.prefix}joinrole toggle` to disable it or `{ctx.prefix}joinrole bots` to change it", delete_after=30)
                elif bot_role is not None:
                    await self.bot.db.execute(f"UPDATE joinrole SET bots = $1 WHERE guild_id = $2", role.id, ctx.guild.id)
                    await ctx.send(f"{emotes.white_mark} **{role.mention}** will be given to bots from now one! Use `{ctx.prefix}joinrole toggle` to disable it or `{ctx.prefix}joinrole bots` to change it", delete_after=30)
    
    @joinrole.command(brief="Disable role on join", description="Disable role on join so new members wouldn't be assigned to it when they join", name="toggle")
    async def joinrole_toggle(self, ctx):
        """ Toggle the join role. It is automatically set to `ON` """
        db_check = await self.bot.db.fetchval("SELECT guild_id FROM joinrole WHERE guild_id = $1", ctx.guild.id)

        if db_check is None:
            return await ctx.send(f"{emotes.red_mark} You don't have any role set yet. Use `{ctx.prefix}joinrole people/bots` to setup the role", delete_after=30)
        if db_check is not None:
            await self.bot.db.execute(f"DELETE FROM joinrole WHERE guild_id = $1", ctx.guild.id)
            await ctx.send(f"{emotes.white_mark} Role on join has been disabled. Use `{ctx.prefix}joinrole people/bots` to enable it back on", delete_after=30)

    @commands.command(brief='Disable command in your server', aliases=['disablecmd'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def disablecommand(self, ctx, command):
        """ Disable command in your server so others couldn't use it
        After you've disabled it, the command will be locked to guild owner only"""
        cant_disable = ["help", "jishaku", "disablecommand", "enablecommand"]
        cmd = self.bot.get_command(command)

        if cmd is None:
            return await ctx.send(f"{emotes.red_mark} Command **{command}** doesn't exist.")

        data = await self.bot.db.fetchval("SELECT * FROM guilddisabled WHERE command = $1 AND guild_id = $2", str(cmd.name), ctx.guild.id)

        if cmd.name in cant_disable and not ctx.author.id == 345457928972533773:
            return await ctx.send(f"{emotes.red_mark} Unfortunately you cannot disable **{cmd.name}**")

        if data is None:
            await self.bot.db.execute("INSERT INTO guilddisabled(guild_id, command) VALUES ($1, $2)", ctx.guild.id, str(cmd.name))
            return await ctx.send(f"{emotes.white_mark} **{cmd.name}** was disabled in this guild.")

        if data is not None:
            return await ctx.send(f"{emotes.red_mark} **{cmd.name}** is already disabled")

    @commands.command(brief='Enable command in your server', aliases=['enablecmd'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def enablecommand(self, ctx, command):
        """ Enable disabled command in your servers so others could use it """
        cmd = self.bot.get_command(command)

        if cmd is None:
            return await ctx.send(f"{emotes.red_mark} Command **{command}** doesn't exist.")

        data = await self.bot.db.fetchval("SELECT * FROM guilddisabled WHERE command = $1 AND guild_id = $2", str(cmd.name), ctx.guild.id)


        if data is not None:
            await self.bot.db.execute("DELETE FROM guilddisabled WHERE command = $1 AND guild_id = $2", str(cmd.name), ctx.guild.id)
            return await ctx.send(f"{emotes.white_mark} **{cmd.name}** was disabled in this guild.")

        if data is None:
            return await ctx.send(f"{emotes.red_mark} **{cmd.name}** is not disabled")
            
            

def setup(bot):
    bot.add_cog(Managment(bot))

        