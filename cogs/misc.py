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
import asyncio
import random
import aiohttp
import math

from discord.ext import commands
from discord.utils import escape_markdown
from utils.checks import has_voted, is_guild, test_command
from utils.paginator import Pages
from utils.Nullify import clean
from utils import btime
from datetime import datetime
from db import emotes


class misc(commands.Cog, name="Misc"):

    def __init__(self, bot):
        self.bot = bot
        self.help_icon = "<:eta:695710706028380211>"
        self.big_icon = "https://cdn.discordapp.com/emojis/695710706028380211.png?v=1"

    def is_it_me(ctx):
        return ctx.author.id == 345457928972533773

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36"

    MAX_FILE_SIZE = 1024 * 1024 * 20
    TIMEOUT = 20
    NO_IMG = "http://i.imgur.com/62di8EB.jpg"
    CHUNK_SIZE = 512 * 1024

                
    @commands.command(brief="Urban dictionary anything")
    @commands.cooldown(1, 15, commands.BucketType.user)
    @commands.guild_only()
    @commands.is_nsfw()
    async def urban(self, ctx, *, urban: str):
        """ Search anything you want in urban dictionary """

        async with aiohttp.ClientSession() as cs:
            async with cs.get(f'http://api.urbandictionary.com/v0/define?term={urban}') as r:
                url = await r.json()

        if url is None:
            return await ctx.send("No URL found")

        count = len(url['list'])
        if count == 0:
            return await ctx.send("No results were found.")
        result = url['list'][random.randint(0, count - 1)]

        definition = result['definition']
        example = result['example']
        if len(definition) >= 1000:
                definition = definition[:1000]
                definition = definition.rsplit(' ', 1)[0]
                definition += '...'

        embed = discord.Embed(color=self.bot.embed_color,
                              description=f"**Search:** {result['word']} | **by:** {result['author']}")
        embed.add_field(
            name="Votes:", value=f"\U0001f44d **{result['thumbs_up']}** | \U0001f44e **{result['thumbs_down']}**", inline=False)
        embed.add_field(name="Definition", value=definition, inline=True)
        embed.add_field(name="Example", value=example, inline=True)
        embed.set_footer(text=f"© {self.bot.user}")

        async with ctx.channel.typing():
            await asyncio.sleep(5)
            return await ctx.send(embed=embed)

    @commands.command(category="Basic", brief="Suggest anything", aliases=['idea'])
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def suggest(self, ctx, *, suggestion: commands.clean_content):
        """ Suggest anything you want to see in the server/bot!
        Suggestion will be sent to support server for people to vote."""

        try:
            await ctx.message.delete()
        except Exception:
            pass

        logchannel = self.bot.get_channel(674929868345180160)

        if len(suggestion) > 128:
            return await ctx.send(f"{emotes.warning} Your suggestion is over 128 characters!")
        elif len(suggestion) < 128:
            ids = await self.bot.db.fetch("SELECT suggestion_id FROM suggestions")
            e = discord.Embed(color=self.bot.logging_color, title=f"Suggestion! [ID: {len(ids) + 1}]", description=f"A new suggestion was submitted by **{ctx.author}**")
            e.add_field(name="Suggestion:", value=f"```\n{suggestion}```", inline=False)
            msg = await logchannel.send(embed=e)
            await msg.add_reaction(f"{emotes.white_mark}")
            await msg.add_reaction(f"{emotes.red_mark}")
            await self.bot.db.execute("INSERT into suggestions(suggestion_info, suggestion_id, user_id, msg_id, approved) VALUES($1, $2, $3, $4, $5)", suggestion, len(ids) + 1, ctx.author.id, msg.id, False)
            await ctx.send(f"{emotes.white_mark} Your suggestion was sent successfully with id: **{len(ids) + 1}**! You can also follow this suggestion to know if it was approved or not by typing `{ctx.prefix}follow suggestion {len(ids) + 1}`")

    @commands.group(brief='Follow suggestions or bugs')
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def follow(self, ctx):
        """ You can follow suggestions 
        When they'll get approved or denied you'll get a dm from bot with a result """
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @follow.command()
    async def suggestion(self, ctx, suggestionid: int):
        """ Follow suggestions """
        check = await self.bot.db.fetchval("SELECT approved FROM suggestions WHERE suggestion_id = $1", suggestionid)
        tracks = await self.bot.db.fetchval("SELECT * FROM track_suggest WHERE user_id = $1 AND suggestion_id = $2", ctx.author.id, suggestionid)

        if check is None:
            await ctx.send(f"{emotes.warning} Looks like suggestion with id {suggestionid} doesn't exist.")
        elif check == False and tracks is None:
            await self.bot.db.execute("INSERT INTO track_suggest(user_id, suggestion_id) VALUES($1, $2)", ctx.author.id, suggestionid)
            await ctx.send(f"{emotes.white_mark} Started following bug with id: **{suggestionid}**, you'll get notified if the suggestion was approved or not.")
        elif check == True:
            await ctx.send(f"{emotes.warning} That suggestion is already approved/denied, you cannot follow it.")
        elif tracks:
            await ctx.send(f"{emotes.red_mark} You're already following suggestion with id **{suggestionid}**")
    
    @commands.command(brief='Set AFK state', aliases=['afk'])
    @commands.guild_only()
    @has_voted()
    async def setafk(self, ctx, *, message: str = None):
        """
        Set your AFK state. Others will get notified when they'll mention you.
        """
        db_check = await self.bot.db.fetchval("SELECT * FROM userafk WHERE guild_id = $1 AND user_id = $2", ctx.guild.id, ctx.author.id)
        if message is None:
            msgs = "I'm AFK :)"
        elif message and len(message) < 64:
            msgs = message
        else:
            return await ctx.send(f"{emotes.red_mark} Your message is too long! You can have max 64 characters.")
        if db_check is None:
            await self.bot.db.execute("INSERT INTO userafk(user_id, guild_id, message, time) VALUES ($1, $2, $3, $4)", ctx.author.id, ctx.guild.id, msgs, datetime.now())
            self.bot.afk_users.append((ctx.author.id, ctx.guild.id, msgs, datetime.now()))
            await ctx.send(f"{emotes.white_mark} | Set your **AFK** state to --> `{msgs}`", delete_after=20)
        else:
            await self.bot.db.execute("UPDATE userafk SET message = $1 WHERE user_id = $2 AND guild_id = $3", msgs, ctx.author.id, ctx.guild.id)
            for user, guild, msg, time in self.bot.afk_users:
                if ctx.author.id == user and ctx.guild.id == guild:
                    self.bot.afk_users.remove((user, guild, msg, time))
                    self.bot.afk_users.append((user, guild, msgs, datetime.now()))
            await ctx.send(f"{emotes.white_mark} | Changed your **AFK** state to --> `{msgs}`", delete_after=20)
            

    @commands.group(brief="Manage your todo list", invoke_without_command=True)
    async def todo(self, ctx):
        ''' Your todo list '''
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)
        
    @todo.command(aliases=['a'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def add(self, ctx, *, todo: commands.clean_content):
        """ Add something to your todo list 
        Time is in UTC """

        if len(todo) > 200:
            return await ctx.send(f"{emotes.red_mark} Your todo is too long! ({len(todo)}/200)")
        
        todocheck = await self.bot.db.fetchval("SELECT todo FROM todolist WHERE user_id = $1 AND todo = $2", ctx.author.id, todo)

        if todocheck:
            return await ctx.send(f"{emotes.red_mark} You already have `{todo}` in your todo list")
        await self.bot.db.execute("INSERT INTO todolist(user_id, guild_id, todo, time) VALUES ($1, $2, $3, $4)", ctx.author.id, ctx.guild.id, todo, datetime.utcnow())

        await ctx.send(f"{emotes.white_mark} Added `{todo}` to your todo list")
    
    @todo.command(name='list', aliases=['l'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def _list(self, ctx):
        """ Check your todo list """
        todos = []
        for num, todo, in enumerate(await self.bot.db.fetch('SELECT todo FROM todolist WHERE user_id = $1 ORDER BY time ASC', ctx.author.id), start=0):
            todos.append(f"`[{num + 1}]` {todo['todo']}\n")

        if len(todos) == 0:
            return await ctx.send(f"{emotes.red_mark} You don't have any todos")

        paginator = Pages(ctx,
                          title=f"Your todo list:",
                          entries=todos,
                          thumbnail=None,
                          per_page = 10,
                          embed_color=ctx.bot.embed_color,
                          show_entry_count=True)
        try:
            await paginator.paginate()
        except HTTPException:
            paginators = Pages(ctx,
                          title=f"Your todo list:",
                          entries=todos,
                          thumbnail=None,
                          per_page = 5,
                          embed_color=ctx.bot.embed_color,
                          show_entry_count=True)
            await paginators.paginate()
    
    @todo.command(aliases=['r'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def remove(self, ctx, *, todoid: str):
        """ Remove todo from your todo list """
    
        todos = await self.bot.db.fetch('SELECT * FROM todolist WHERE user_id = $1 ORDER BY time', ctx.author.id)
        if not todos:
            return await ctx.send(f'{emotes.red_mark} You don\'t have any todos')

        todos = {f'{index + 1}': todo for index, todo in enumerate(todos)}
        todos_to_remove = []

        todo_ids = todoid

        todo_ids = todo_ids.split(' ')
        for todo_id in todo_ids:

            if not todo_id.isdigit():
                return await ctx.send(f'{emotes.red_mark} You\'ve provided wrong id')
            if todo_id not in todos.keys():
                return await ctx.send(f'{emotes.red_mark} I can\'t find todo with id `{todo_id}` in your todo list list.')
            if todo_id in todos_to_remove:
                return await ctx.send(f'{emotes.red_mark} You provided todo id `{todo_id}` more than once.')
            todos_to_remove.append(todo_id)

        query = 'DELETE FROM todolist WHERE user_id = $1 and time = $2'
        entries = [(todos[todo_id]['user_id'], todos[todo_id]['time']) for todo_id in todos_to_remove]
        await self.bot.db.executemany(query, entries)

        contents = '\n• '.join([f'`{escape_markdown(todos[todo_id]["todo"], as_needed=True)}`' for todo_id in todos_to_remove])
        return await ctx.send(f"{emotes.white_mark} Removed `{len(todo_ids)}` todo from your todo list:\n• {contents}")

    @todo.command(aliases=['c'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def clear(self, ctx):
        """ Clear your todo list """

        todos = await self.bot.db.fetch('SELECT * FROM todolist WHERE user_id = $1 ORDER BY time', ctx.author.id)
        if not todos:
            return await ctx.send(f'{emotes.red_mark} You don\'t have any todos')

        def check(r, u):
            return u.id == ctx.author.id and r.message.id == checkmsg.id
            
        try:
            checkmsg = await ctx.send(f"Are you sure you want to clear **{len(todos)}** todos from your todo list?")
            await checkmsg.add_reaction(f"{emotes.white_mark}")
            await checkmsg.add_reaction(f"{emotes.red_mark}")
            react, user = await self.bot.wait_for('reaction_add', check=check, timeout=30)    
            
            if str(react) == f"{emotes.white_mark}":
                try:
                    await checkmsg.clear_reactions()
                except:
                    pass
                await checkmsg.edit(content=f"{emotes.white_mark} Deleted {len(todos)} todos from your todo list", delete_after=15)
                await self.bot.db.execute("DELETE FROM todolist WHERE user_id = $1", ctx.author.id)
                
            if str(react) == f"{emotes.red_mark}":
                try:
                    await checkmsg.clear_reactions()
                except:
                    pass
                await checkmsg.edit(content=f"{emotes.white_mark} I'm not deleting any todos from your todo list.", delete_after=15)

        except asyncio.TimeoutError:
            try:
                await checkmsg.clear_reactions()
            except:
                pass
            await checkmsg.edit(content="Cancelling...", delete_after=15)
        
    @todo.command(aliases=['e'])
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def edit(self, ctx, todoid: str, *, content: commands.clean_content):
        """ Edit todo in your todo list """

        todos = await self.bot.db.fetch('SELECT * FROM todolist WHERE user_id = $1 ORDER BY time', ctx.author.id)
        if not todos:
            return await ctx.send(f'{emotes.red_mark} You don not have any todos.')


        todos = {f'{index + 1}': todo for index, todo in enumerate(todos)}

        if not todoid.isdigit():
            return await ctx.send(f'{emotes.red_mark} You\'ve provided wrong id')
        if todoid not in todos.keys():
            return await ctx.send(f'{emotes.red_mark} I can\'t find todo with id `{todoid}` in your todo list list.')
        if len(content) > 200:
            return await ctx.send(f"{emotes.red_mark} Your todo is too long! ({len(content)}/200)")

        todo_to_edit = todos[todoid]

        todocheck = await self.bot.db.fetchval("SELECT todo FROM todolist WHERE user_id = $1 AND todo = $2", ctx.author.id, content)

        if todocheck:
            return await ctx.send(f"{emotes.red_mark} You already have `{clean(content)}` in your todo list")

        query = 'UPDATE todolist SET todo = $1 WHERE user_id = $2 and time = $3'
        await self.bot.db.execute(query, content, todo_to_edit['user_id'], todo_to_edit['time'])

        return await ctx.send(f"{emotes.white_mark} Changed `{clean(todo_to_edit['todo'])}` to `{clean(content)}` in your todo list")

    # @commands.group(brief='Presence monitoring', invoked_without_command=True)
    # @commands.guild_only()
    # @commands.cooldown(1, 15, commands.BucketType.user)
    # @test_command()
    # async def presence(self, ctx):
    #     """ When enabled, bot will be logging what you're playing, which later on you'll be able to see. """
    #     if ctx.invoked_subcommand is None:
    #         await ctx.send_help(ctx.command)

    # @presence.command()
    # @test_command()
    # @commands.cooldown(1, 15, commands.BucketType.user)
    # async def enable(self, ctx):
    #     """ Enable this so bot could start logging your presences. """

    #     check = await self.bot.db.fetchval("SELECT * FROM presence_check WHERE user_id = $1", ctx.author.id)

    #     if not check:
    #         await self.bot.db.execute("INSERT INTO presence_check(user_id) VALUES ($1)", ctx.author.id)
    #         return await ctx.send(f"{emotes.white_mark} I will start logging your presences!")
        
    #     if check:
    #         return await ctx.send(f"{emotes.red_mark} I'm already logging your presences")
        
    # @presence.command()
    # @test_command()
    # @commands.cooldown(1, 15, commands.BucketType.user)
    # async def disable(self, ctx):
    #     """ Disable this so bot wouldn't log your presences. All your previous data will be deleted. """

    #     check = await self.bot.db.fetchval("SELECT * FROM presence_check WHERE user_id = $1", ctx.author.id)

    #     if check:
    #         await self.bot.db.execute("DELETE FROM presence_check WHERE user_id = $1", ctx.author.id)
    #         await self.bot.db.execute("DELETE FROM presence WHERE user_id = $1", ctx.author.id)
    #         return await ctx.send(f"{emotes.white_mark} I will stop logging your presences! Deleted your previous data as well!")
        
    #     if not check:
    #         return await ctx.send(f"{emotes.red_mark} I'm not logging your presences")

    # @presence.command(name="logs")
    # @test_command()
    # @commands.cooldown(1, 30, commands.BucketType.user)
    # async def _logs(self, ctx):

    #     check = await self.bot.db.fetchval("SELECT * FROM presence_check WHERE user_id = $1", ctx.author.id)

    #     if check:
    #         status = []
    #         for presence in await self.bot.db.fetch("SELECT * FROM presence WHERE user_id = $1 ORDER BY time DESC", ctx.author.id):
    #             status.append(f"**[{presence['activity_name']}]** - {presence['time']}")

    #         state = ''
    #         for num, states in enumerate(status[:5], start=0):
    #             state += f"`[{num + 1}]` {status}"
            
    #         e = discord.Embed(color=self.bot.embed_color, title=f'{ctx.author}\'s activities.')
    #         e.description = state
    #         await ctx.send(embed=e)
        
    #     if not check:
    #         return await ctx.send(f"{emotes.red_mark} I'm not logging your presences..")

    @commands.command(brief='Tells you user status')
    async def status(self, ctx, member: discord.Member = None):
        """ Check how long have you/others have been online/idle/dnd/offline for.
        You need to be opted in first."""
        member = member or ctx.author

        if member.bot:
            return await ctx.send(f'{emotes.warning} I don\'t log bot statuses')

        black = await self.bot.db.fetchval("SELECT * FROM status_op_out WHERE user_id = $1", member.id)
        if black is None:
            return await ctx.send(f"**{member.name}** is not opted in. {f'Do `{ctx.prefix}status-opt` to opt in.' if member == ctx.author else ''}")
        
        status = await self.bot.db.fetchval("SELECT time FROM useractivity WHERE user_id = $1", member.id)
        name = await self.bot.db.fetchval("SELECT activity_title FROM useractivity WHERE user_id = $1", member.id)

        if status and name:
            await ctx.send(f"**{member.name}** has been **{name}** for {btime.human_timedelta(status, suffix=None)}.")
        else:
            return await ctx.send('I have nothing logged yet')
    
    @commands.command(name='status-opt', aliases=['statusopt', 'sopt'], brief="Opt out/in from/to your status being logged")
    async def status_opt(self, ctx):
        """ Opt in yourself so I would log your statuses. You can also opt in"""
        nicks_opout = await self.bot.db.fetchval("SELECT user_id FROM status_op_out WHERE user_id = $1", ctx.author.id)
        if nicks_opout is not None:
            def check(r, u):
                return u.id == ctx.author.id and r.message.id == checkmsg.id
            try:
                checkmsg = await ctx.send(f"Are you sure you want to opt-out? Once you'll opt-out I won't be logging your statuses anymore and all the data that I have stored in my database will also be deleted.")
                await checkmsg.add_reaction(f'{emotes.white_mark}')
                await checkmsg.add_reaction(f'{emotes.red_mark}')
                react, user = await self.bot.wait_for('reaction_add', check=check, timeout=30.0)

                if str(react) == f"{emotes.white_mark}": 
                    await self.bot.db.execute('DELETE FROM status_op_out WHERE user_id = $1', ctx.author.id)
                    await self.bot.db.execute("DELETE FROM useractivity WHERE user_id = $1", ctx.author.id)
                    await ctx.channel.send(f"{emotes.white_mark} You're now opted-in! I'll be logging your statuses once again.")
                    await checkmsg.delete()


                if str(react) == f"{emotes.red_mark}":      
                    await checkmsg.delete()
                    await ctx.channel.send("Alright. Not opting you out")
            except Exception as e:
                print(e)
                return
            
        elif nicks_opout is None:
            def check(r, u):
                return u.id == ctx.author.id and r.message.id == checkmsg.id
            try:
                checkmsg = await ctx.send(f"Are you sure you want to opt-in? I'll be logging your activity status and you will opt in.")
                await checkmsg.add_reaction(f'{emotes.white_mark}')
                await checkmsg.add_reaction(f'{emotes.red_mark}')
                react, user = await self.bot.wait_for('reaction_add', check=check, timeout=30.0)

                if str(react) == f"{emotes.white_mark}": 
                    await self.bot.db.execute('INSERT INTO status_op_out(user_id) VALUES($1)', ctx.author.id)
                    await ctx.channel.send(f"{emotes.white_mark} You're now opted-in! I'll be logging your statuses from now on!")
                    await checkmsg.delete()


                if str(react) == f"{emotes.red_mark}":      
                    await checkmsg.delete()
                    await ctx.channel.send("Alright. Not opting you in")
            except Exception as e:
                print(e)
                return


    @is_guild(568567800910839811)
    @commands.command(brief="Ice's lmao count", hidden=True)
    async def lmaocount(self, ctx):

        numla = await self.bot.db.fetchval("SELECT count FROM lmaocount WHERE user_id = $1", 302604426781261824)
        numlf = await self.bot.db.fetchval("SELECT lf FROM lmaocount WHERE user_id = $1", 302604426781261824)

        ice = self.bot.get_user(302604426781261824)
        await ctx.send(f"**{ice}** said `lmao` **{numla}** times, and `lmfao` **{numlf}** times.")

def setup(bot):
    bot.add_cog(misc(bot))
