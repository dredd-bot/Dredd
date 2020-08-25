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
from discord.ext import commands
from utils import default
from db import emotes

class Managment(commands.Cog, name="Management"):

    def __init__(self, bot):
        self.bot = bot
        self.help_icon = "<:settingss:695707235833085982>"
        self.big_icon = "https://cdn.discordapp.com/emojis/695707235833085982.png?v=1"

    
    async def bot_check(self, ctx):
        
        if await self.bot.is_admin(ctx.author):
            return True
        
        if not ctx.guild:
            return True

        if ctx.guild and ctx.author.guild_permissions.administrator:
            return True

        if ctx.command.parent:
            if await self.bot.db.fetchval("select * from guilddisabled where command = $1 AND guild_id = $2", str(ctx.command.parent), ctx.guild.id):
                await ctx.send(f"{emotes.warning} | `{ctx.command.parent}` and it's corresponding subcommands are disabled in this server")
                return False
            elif await self.bot.db.fetchval("select * from guilddisabled where command = $1 AND guild_id = $2", str(f"{ctx.command.parent} {ctx.command.name}"), ctx.guild.id):
                await ctx.send(f"{emotes.warning} | `{ctx.command.parent} {ctx.command.name}` is disabled in this server.")
                return False
        else:
            if await self.bot.db.fetchval("select * from guilddisabled where command = $1 AND guild_id = $2", str(ctx.command.name), ctx.guild.id):
                await ctx.send(f"{emotes.warning} | `{ctx.command.name}` is disabled in this server.")
                return False
        return True

    def cog_check(self, ctx):
        if not ctx.guild:
            return False
        return True


    @commands.command(brief="Change prefix", description="Change my prefix in the server")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.cooldown(1, 5, commands.BucketType.guild)
    async def prefix(self, ctx, prefix: str = None):
        """ Change bot's prefix in the server """

        prefixs = await self.bot.db.fetchval("SELECT prefix FROM guilds WHERE guild_id = $1", ctx.guild.id)
        if prefix is None:
            return await ctx.send(f"Your server prefix is `{prefixs}`")

        elif prefix and len(prefix) < 6:
            await self.bot.db.execute("UPDATE guilds SET prefix = $1 WHERE guild_id = $2", prefix, ctx.guild.id)
            self.bot.prefixes[ctx.guild.id] = prefix
            await ctx.send(f"Changed server prefix to `{prefix}`!")
        else:
            await ctx.send(f"{emotes.warning} Prefix is too long!")

    @commands.command(brief="Guild settings", aliases=['guildsettings', 'settings'])
    @commands.guild_only()
    @commands.cooldown(1, 5, commands.BucketType.guild)
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
        joinmsg = await self.bot.db.fetchval("SELECT msg FROM joinmsg WHERE guild_id = $1", ctx.guild.id)
        leavemsg = await self.bot.db.fetchval("SELECT msg FROM leavemsg WHERE guild_id = $1", ctx.guild.id)
        raidmode = await self.bot.db.fetchval("SELECT raidmode FROM raidmode WHERE guild_id = $1", ctx.guild.id)
        raidmodedm = await self.bot.db.fetchval("SELECT dm FROM raidmode WHERE guild_id = $1", ctx.guild.id)

        mention = '{{member.mention}}'
        members = '{{server.members}}'
        if db_check7:
            msg = "{0} {1} joined the server! There are {2} members in the server now.".format(emotes.joined, mention, members)
        elif not db_check7:
            msg = 'Welcoming messages are disabled'
        
        if db_check9:
            msg1 = "{0} {1} left the server... There are {2} members left in the server.".format(emotes.left, mention, members)
        elif not db_check9:
            msg1 = 'Leaving messages are disabled'
        joinmsg = joinmsg or msg
        leavemsg = leavemsg or msg1

        logs  = f"{f'{emotes.setting_no}' if db_check3 is None else f'{emotes.setting_yes}'} Edited messages\n"
        logs += f"{f'{emotes.setting_no}' if db_check1 is None else f'{emotes.setting_yes}'} Deleted messages\n"
        logs += f"{f'{emotes.setting_no}' if db_check2 is None else f'{emotes.setting_yes}'} Moderation\n"
        logs += f"{f'{emotes.setting_no}' if db_check4 is None else f'{emotes.setting_yes}'} Member Joins\n"
        logs += f"{f'{emotes.setting_no}' if db_check6 is None else f'{emotes.setting_yes}'} Member Updates\n"
        logs += f"{f'{emotes.setting_no}' if db_check10 is None else f'{emotes.setting_yes}'} Automod actions\n"

        settings = f"{f'{emotes.setting_no}' if db_check8 is None else f'{emotes.setting_yes}'} Role On Join\n"
        settings += f"{f'{emotes.setting_no}' if db_check7 is None else f'{emotes.setting_yes}'} Welcoming Messages\n"
        settings += f"{f'{emotes.setting_no}' if db_check9 is None else f'{emotes.setting_yes}'} Leaving Messages\n"
        settings += f"{f'{emotes.setting_no}' if raidmode is False else f'{emotes.setting_yes}'} Raid mode\n"
        if raidmode is True:
            settings += f"{f'{emotes.setting_no}' if raidmodedm is False else f'{emotes.setting_yes}'} Raid mode DM"

        welcoming = f"**Join message:**\n{joinmsg}\n"
        welcoming += f"**Leave message:**\n{leavemsg}"


        embed = discord.Embed(color=self.bot.embed_color, description=f"{emotes.log_settings} **{ctx.guild}** server settings")
        embed.add_field(name="Logs:", value=logs, inline=False)
        embed.add_field(name="Settings:", value=settings, inline=False)
        embed.add_field(name="Welcoming & Leaving:", value=welcoming, inline=False)

        await ctx.send(embed=embed)
    
    @commands.command(brief="Log channels", description="Enable logging in your server.")
    @commands.has_permissions(manage_guild=True)
    async def togglelog(self, ctx, option = None, *, channel: discord.TextChannel = None):
        """ Toggle log for the given option.  
        Leaving channel empty will disable the log. 
        It is highly recommended for bot to have view audit logs permissions as well"""

        options = ["msgdelete", "msgedit", "moderation", "joinlog", "joinmsg", "leavemsg", "memberupdate"]
        optionsmsg = f'`joinlog`, `memberupdate`, `msgedit`, `msgdelete`, `moderation`, `joinmsg`, `leavemsg`'

        if option is None or option.lower() not in options:
            e = discord.Embed(color=self.bot.embed_color,
                              title=f"{emotes.warning} Invalid option was given. Here are all the valid options:",
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
            if channel.permissions_for(ctx.guild.me).send_messages == False:
                return await ctx.send(f"{emotes.warning} I can't let you do that! I don't have permissions to talk in {channel.mention}")
            elif channel.permissions_for(ctx.guild.me).send_messages:
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
                    await ctx.send(f"{emotes.white_mark} Welcoming messages have been enabled in this server and will be sent to {channel.mention}! You can change the welcoming message by typing `{ctx.prefix}togglemsg welcoming [message]`", delete_after=20)
                elif option.lower() == 'leavemsg':
                    if db_check is not None:
                        return await ctx.send(f"{emotes.white_mark} Leaving messages will be sent to {channel.mention} from now on!", delete_after=20)
                    await ctx.send(f"{emotes.white_mark} Leaving messages have been enabled in this server and will be sent to {channel.mention}! You can change the leaving message by typing `{ctx.prefix}togglemsg leaving [message]`", delete_after=20)
                elif option.lower() == 'memberupdate':
                    if db_check is not None:
                        return await ctx.send(f"{emotes.white_mark} Member update logs will be sent to {channel.mention} from now on!", delete_after=20)
                    await ctx.send(f"{emotes.white_mark} Member update logs have been enabled in this server and will be sent to {channel.mention}!", delete_after=20)

    @commands.group(brief="Change the welcoming and leaving messages")
    @commands.guild_only()
    @commands.has_permissions(manage_messages=True)
    async def togglemsg(self, ctx):
        """ Setup welcoming and leaving messages in your server. 
        `{{member.mention}}` - Mentions a member that joined/left
        `{{member.name}}` - Displays name of member that joined/left
        `{{server.name}}` - Displays server name
        `{{server.members}}` - Displays how many members server has """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @togglemsg.command()
    async def welcoming(self, ctx, *, message: str = None):
        """ Set welcoming message """

        db_check = await self.bot.db.fetchval("SELECT * FROM joinmsg WHERE guild_id = $1", ctx.guild.id)

        if db_check:
            if message is None:
                await self.bot.db.execute("UPDATE joinmsg SET msg = $1 WHERE guild_id = $2", None, ctx.guild.id)
                await ctx.send(f"{emotes.white_mark} Changed welcoming message to default one.")
            elif message and not len(message) > 250:
                await self.bot.db.execute("UPDATE joinmsg SET msg = $1 WHERE guild_id = $2", message, ctx.guild.id)
                await ctx.send(f"{emotes.white_mark} Changed welcoming message to `{message}`")
            else:
                await ctx.send(f"{emotes.red_mark} Was unable to change welcoming message because it is {len(message)}/250 characters long.")
        elif db_check is None:
            return await ctx.send(f"{emotes.red_mark} Please enable welcoming messages first by typing `{ctx.prefix}togglelog joinmsg [channel mention]`")

    @togglemsg.command()
    async def leaving(self, ctx, *, message: str = None):
        """ Set leaving message """

        db_check = await self.bot.db.fetchval("SELECT * FROM leavemsg WHERE guild_id = $1", ctx.guild.id)

        if db_check:
            if message is None:
                await self.bot.db.execute("UPDATE leavemsg SET msg = $1 WHERE guild_id = $2", None, ctx.guild.id)
                await ctx.send(f"{emotes.white_mark} Changed leaving message to default one.")
            elif message and not len(message) > 250:
                await self.bot.db.execute("UPDATE leavemsg SET msg = $1 WHERE guild_id = $2", message, ctx.guild.id)
                await ctx.send(f"{emotes.white_mark} Changed leaving message to `{message}`")
            else:
                await ctx.send(f"{emotes.red_mark} Was unable to change leaving message because it is {len(message)}/250 characters long.")
        elif db_check is None:
            return await ctx.send(f"{emotes.red_mark} Please enable leaving messages first by typing `{ctx.prefix}togglelog leavemsg [channel mention]`")

    @togglemsg.command(name="bots")
    async def _bots(self, ctx):
        """ Disable join and leave messages for bots """

        check = await self.bot.db.fetchval("SELECT bot_join FROM joinmsg WHERE guild_id = $1", ctx.guild.id)
        check2 = await self.bot.db.fetchval("SELECT bot_join FROM leavemsg WHERE guild_id = $1", ctx.guild.id)

        if check == False and check2 == False:
            await self.bot.db.execute("UPDATE joinmsg SET bot_join = $1 WHERE guild_id = $2", True, ctx.guild.id)
            await self.bot.db.execute("UPDATE leavemsg SET bot_join = $1 WHERE guild_id = $2", True, ctx.guild.id)
            await ctx.send(f"{emotes.white_mark} Bot joins will now be logged!")
        elif check == True and check2 == True:
            await self.bot.db.execute("UPDATE joinmsg SET bot_join = $1 WHERE guild_id = $2", False, ctx.guild.id)
            await self.bot.db.execute("UPDATE leavemsg SET bot_join = $1 WHERE guild_id = $2", False, ctx.guild.id)
            await ctx.send(f"{emotes.white_mark} Bot joins won't be logged anymore!")
        elif check is None and check2 is None:
            await self.bot.db.execute("UPDATE joinmsg SET bot_join = $1 WHERE guild_id = $2", True, ctx.guild.id)
            await self.bot.db.execute("UPDATE leavemsg SET bot_join = $1 WHERE guild_id = $2", True, ctx.guild.id)
            await ctx.send(f"{emotes.white_mark} Bot joins will now be logged!")
        else:
            await ctx.send(f"{emotes.red_mark} You aren't logging member joins, please enable that by typing `{ctx.prefix}togglelog joinmsg [channel mention]`")

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
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def disablecommand(self, ctx, *, command):
        """ Disable command in your server so others couldn't use it
        Once you've disabled it, the command will be locked to server administrators only"""
        cant_disable = ["help", "jishaku", "dev", "disablecmd", "enablecmd", 'admin']
        cmd = self.bot.get_command(command)
        if cmd is None:
            embed = discord.Embed(color=self.bot.logembed_color, description=f"{emotes.red_mark} Command **{command}** doesn't exist.")
            return await ctx.send(embed=embed)

        if cmd.name in cant_disable:
            embed = discord.Embed(color=self.bot.logembed_color, description=f"{emotes.red_mark} Why are you trying to disable **{cmd.name}** you dum dum.")
            return await ctx.send(embed=embed)

        if cmd.parent and str(cmd.parent) not in cant_disable:
            if await self.bot.db.fetchval("SELECT * FROM guilddisabled WHERE command = $1 AND guild_id = $2", str(f"{cmd.parent} {cmd.name}"), ctx.guild.id) is None:
                await self.bot.db.execute("INSERT INTO guilddisabled(guild_id, command) VALUES ($1, $2)", ctx.guild.id, str(f"{cmd.parent} {cmd.name}"))
                return await ctx.send(f"{emotes.white_mark} Okay. **{cmd.parent} {cmd.name}** was disabled.")
            elif await self.bot.db.fetchval("SELECT * FROM guilddisabled WHERE command = $1 and guild_id = $2", str(f"{cmd.parent} {cmd.name}"), ctx.guild.id):
                return await ctx.send(f"{emotes.warning} | `{cmd.parent} {cmd.name}` is already disabled")
        elif cmd.parent and str(cmd.parent) in cant_disable:
            return await ctx.send(f"{emotes.red_mark} You can't do that, sorry!")
        elif not cmd.parent:
            if await self.bot.db.fetchval("SELECT * FROM guilddisabled WHERE command = $1 AND guild_id = $2", str(cmd.name), ctx.guild.id) is None:
                await self.bot.db.execute("INSERT INTO guilddisabled(guild_id, command) VALUES ($1, $2)", ctx.guild.id, str(cmd.name))
                return await ctx.send(f"{emotes.white_mark} Okay. **{cmd.name}** was disabled.")
            elif await self.bot.db.fetchval("SELECT * FROM guilddisabled WHERE command = $1 AND guild_id = $2", str(cmd.name), ctx.guild.id):
                return await ctx.send(f"{emotes.warning} | `{cmd.name}` is already disabled")

    @commands.command(brief='Enable command in your server', aliases=['enablecmd'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    @commands.guild_only()
    @commands.has_permissions(administrator=True)
    async def enablecommand(self, ctx,*, command):
        """ Enable disabled command in your servers so others could use it """
        cmd = self.bot.get_command(command)

        if cmd is None:
            return await ctx.send(f"{emotes.red_mark} Command **{command}** doesn't exist.")

        if cmd.parent:
            if await self.bot.db.fetchval("SELECT * FROM guilddisabled WHERE command = $1 AND guild_id = $2", str(f"{cmd.parent} {cmd.name}"), ctx.guild.id) is None:
                return await ctx.send(f"{emotes.warning} | `{cmd.parent} {cmd.name}` is not disabled!")
            elif await self.bot.db.fetchval("SELECT * FROM guilddisabled WHERE command = $1 AND guild_id = $2", str(f"{cmd.parent} {cmd.name}"), ctx.guild.id):
                await self.bot.db.execute("DELETE FROM guilddisabled WHERE command = $1 AND guild_id =$2", str(f"{cmd.parent} {cmd.name}"), ctx.guild.id)
                return await ctx.send(f"{emotes.white_mark} | `{cmd.parent} {cmd.name}` is now enabled!")
        elif not cmd.parent:
            if await self.bot.db.fetchval("SELECT * FROM guilddisabled WHERE command = $1 AND guild_id = $2", str(cmd.name), ctx.guild.id) is None:
                return await ctx.send(f"{emotes.warning} | `{cmd.name}` is not disabled!")
            elif await self.bot.db.fetchval("SELECT * FROM guilddisabled WHERE command = $1 AND guild_id = $2", str(cmd.name), ctx.guild.id):
                await self.bot.db.execute("DELETE FROM guilddisabled WHERE command = $1 AND guild_id = $2", str(cmd.name), ctx.guild.id)
                return await ctx.send(f"{emotes.white_mark} | `{cmd.name}` is now enabled!")
    
    @commands.group(brief='Turn on/off server raid mode', invoke_without_command=True)
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.bot_has_permissions(kick_members=True)
    async def raidmode(self, ctx):
        """ Raid is happening in your server? Turn on anti-raider! It'll kick every new member that joins. 
        It'll also inform them in DMs that server is currently in anti-raid mode and doesn't allow new members!
        DMs can also be toggled on and off. They're always on by default"""

        raid_check = await self.bot.db.fetchval("SELECT raidmode FROM raidmode WHERE guild_id = $1", ctx.guild.id)

        if raid_check == False:
            await self.bot.db.execute("UPDATE raidmode SET raidmode = $1 WHERE guild_id = $2", True, ctx.guild.id)
            self.bot.raidmode[ctx.guild.id]['raidmode'] = True
            await ctx.send(f"{emotes.white_mark} Raid mode was activated! New members will get kicked with a message in their DMs")
        elif raid_check == True:
            await self.bot.db.execute("UPDATE raidmode SET raidmode = $1, dm = $2 WHERE guild_id = $3", False, True, ctx.guild.id)
            self.bot.raidmode[ctx.guild.id]['raidmode'] = False
            self.bot.raidmode[ctx.guild.id]['dm'] = True
            await ctx.send(f"{emotes.white_mark} Raid mode was deactivated! New members won't be kicked anymore.")
        
    @raidmode.command(name='toggledm', aliases=['dm'], brief='Toggle off/on the DM message')
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def raidmode_toggledm(self, ctx):
        """ Toggle DMs on or off if you want user to get informed about the anti raid mode being enabled
        
        Note: It's on by default!"""
        dm_check = await self.bot.db.fetchval("SELECT dm FROM raidmode WHERE guild_id = $1", ctx.guild.id)

        if dm_check == False:
            await self.bot.db.execute("UPDATE raidmode SET dm = $1 WHERE guild_id = $2", True, ctx.guild.id)
            self.bot.raidmode[ctx.guild.id]['dm'] = True
            return await ctx.send(f"{emotes.white_mark} DMs are now enabled! Users will get DMed anti-raid message")
        elif dm_check == True:
            await self.bot.db.execute("UPDATE raidmode SET dm = $1 WHERE guild_id = $2", False, ctx.guild.id)
            self.bot.raidmode[ctx.guild.id]['dm'] = False
            return await ctx.send(f"{emotes.white_mark} DMs are now disabled! Users won't get DMed anti-raid message")
        else:
            return

def setup(bot):
    bot.add_cog(Managment(bot))

        