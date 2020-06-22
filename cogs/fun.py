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
import random
import aiohttp
import typing
import urllib

from discord.ext import commands
from utils import default, argparser, http, checks
from datetime import datetime
from utils.Nullify import clean
from io import BytesIO
from utils.checks import has_voted
from db import emotes


class fun(commands.Cog, name="Fun"):

    def __init__(self, bot):
        self.bot = bot
        self._last_result = None
        self.help_icon = "<:funn:695710705932042244>"
        self.big_icon = "https://cdn.discordapp.com/emojis/695710705932042244.png?v=1"

    async def bot_check(self, ctx):
        if not ctx.guild:
            self.bot.embed_color = 0x0361D2
            return True

        else:
            self.bot.embed_color = 0x0361D2
            return True

    async def api_img_creator(self, ctx, url, filename, content=None):
        async with ctx.channel.typing():
            req = await http.get(url, res_method="read")

            if req is None:
                return await ctx.send("I couldn't create the image ;-;")

            bio = BytesIO(req)
            bio.seek(0)
            await ctx.send(content=content, file=discord.File(bio, filename=filename))
    
    async def __get_image(self, ctx, user=None):
        if user:
            try:
                u = await commands.UserConverter().convert(ctx, user)
                if u.is_avatar_animated():
                    return str(u.avatar_url_as(format="gif"))
                else:
                    return str(u.avatar_url_as(format="png"))
            except Exception:
                try:
                    e = await commands.EmojiConverter().convert(ctx, user)
                    return str(e.url)
                except Exception:
                    try:
                        e = await commands.PartialEmojiConverter().convert(ctx, user)
                        return str(e.url)
                    except Exception:
                        return str(user.strip("<>"))


    @commands.command(brief="Tweet as someone", description='You can tweet as someone else to troll others')
    @commands.cooldown(1, 30, commands.BucketType.user)
    # @commands.check(is_it_me)
    async def tweet(self, ctx, username: commands.clean_content(fix_channel_mentions=True), *, text: commands.clean_content(fix_channel_mentions=True)):
        """ Tweet as someone else. """

        if len(text) > 65:
            text = text[:65]
            text += "..."

        await ctx.trigger_typing()
        async with aiohttp.ClientSession() as cs:
            async with cs.get("https://nekobot.xyz/api/imagegen?type=tweet&username=%s&text=%s" % (username, text)) as r:
                res = await r.json()

        embed = discord.Embed(color=self.bot.embed_color,
                              title=f"You made {username} tweet this:")
        embed.set_image(url=res["message"])
        await ctx.send(embed=embed)

    @commands.command(brief="Trap someone", description="You can trap anyone with this card")
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def trap(self, ctx, user: commands.clean_content = None):
        """ Trap anyone with trap card """

        owner = self.bot.get_user(345457928972533773)
        bot = self.bot.get_user(667117267405766696)
        if user == bot:
            return await ctx.send("Don't you dare trapping me")
        elif user == owner:
            return await ctx.send("Why are you trying to trap my owner? Don't do that :(")
        elif user is None:
            return await ctx.send(f"Please add a user!")
        

        try:
            await ctx.trigger_typing()
            img = await self.__get_image(ctx, user)
            if not isinstance(img, str):
                return img
            author = ctx.author.name
            async with aiohttp.ClientSession() as cs:
                async with cs.get(f"https://nekobot.xyz/api/imagegen?type=trap&author={author}&name={user}&image={img}") as r:
                    res = await r.json()
                        
            embed = discord.Embed(color=self.bot.embed_color)
            embed.set_image(url=res["message"])
            await ctx.send(embed=embed)
        except Exception as e:
            print(e)
            await ctx.send("Couldn't trap that user")

    @commands.command(brief="Rate any thing", description="Rate anything you want")
    @commands.cooldown(1, 15, commands.BucketType.user)
    # @commands.check(is_it_me)
    async def rate(self, ctx, *, thing):
        """ Rates what you desire """

        num = random.randint(0, 100)
        deci = random.randint(0, 9)

        if num == 100:
            deci = 0

        rating = f"{num}.{deci}"
        await ctx.send(f"I'd give {clean(thing)} a rating **{rating}** of **100**")


    @commands.command(brief="Make clyde say something", description="Make clyde tell you something")
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def clyde(self, ctx, *, text: commands.clean_content):
        """Make clyde say something"""

        if len(text) > 70:
            text = text[:70]
            text += "..."

        await ctx.trigger_typing()
        async with aiohttp.ClientSession() as cs:
            async with cs.get("https://nekobot.xyz/api/imagegen?type=clyde&text=%s" % text) as r:
                res = await r.json()

        embed = discord.Embed(color=self.bot.embed_color,
                              title="You made Clyde said this:")
        embed.set_image(url=res["message"])
        await ctx.send(embed=embed)
    
    @commands.command(brief="F in the chat", aliases=['f'])
    async def pressf(self, ctx, *, text: commands.clean_content = None):
        """ Press F to pay respect """
        hearts = ['❤', '💛', '💚', '💙', '💜']
        reason = f"for **{text}** " if text else ""
        await ctx.send(f"**{ctx.author.name}** has paid their respect {reason}{random.choice(hearts)}")
    
    @commands.command(brief="Ship someone")
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def ship(self, ctx, user1: discord.User, user2: discord.User):
        """ Ship two users together """

        owner = self.bot.get_user(345457928972533773)
        bot = self.bot.get_user(667117267405766696)
        if user1 == bot or user2 == bot:
            return await ctx.send("Why are you trying to ship me with someone?")
        if user1 == owner or user2 == owner:
            return await ctx.send("Don't ship my owner to anyone. He belongs to me.")
        await ctx.trigger_typing()
        async with aiohttp.ClientSession() as cs:
            async with cs.get(f"https://nekobot.xyz/api/imagegen?type=ship&user1={user1.avatar_url}&user2={user2.avatar_url}") as r:
                res = await r.json()

        embed = discord.Embed(color=self.bot.embed_color)
        embed.set_image(url=res["message"])
        await ctx.send(embed=embed)
    
    
    @commands.command(brief="Change my mind", description="Make someone change your mind", aliases=["cmm"])
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def changemymind(self, ctx, *, text: commands.clean_content):
        """ Change my mind """

        if len(text) > 70:
            text = text[:70]
            text += "..."
        await ctx.trigger_typing()
        async with aiohttp.ClientSession() as cs:
            async with cs.get("https://nekobot.xyz/api/imagegen?type=changemymind&text=%s" % text) as r:
                res = await r.json()

        embed = discord.Embed(color=self.bot.embed_color,
                              title=f"Change {ctx.author}'s mind")
        embed.set_image(url=res["message"])
        await ctx.send(embed=embed)

    @commands.command(description='Do you have a question? Ask the almighty 8ball what you should do', aliases=['8ball'], brief="Ask the 8ball")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def eightball(self, ctx, *, question):
        """ Ask the mighty 8ball """
        await ctx.trigger_typing()

        with open("db/lines.json", "r") as f:
            data = json.load(f)

        responses = data["eightball"]

        embed = discord.Embed(color=self.bot.embed_color, title=f"🎱 You've asked the 8ball", description=f"``Question:`` {question}\n``Answer:`` {random.choice(responses)}")
        
        await ctx.send(embed=embed)

    @commands.command(description='Reverse any text you want', brief="Reverse any text")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def reverse(self, ctx, *, text: str):
        """ !poow ,ffuts esreveR
        Everything you type after reverse will of course, be reversed
        """

        t_rev = text[::-1].replace("@", "@\u200B").replace("&", "&\u200B")
        embed = discord.Embed(color=self.bot.embed_color, title='Text was reversed!',
                              description=f"**Input:** {text}\n**Output:** {t_rev}")
        await ctx.send(embed=embed)

    @commands.command(brief="Choose between multiple choices", description="For when you wanna settle the score some other way")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def choose(self, ctx, *choices: str):
        """ Choose between multiple choices. """

        try:
            choice = "`" + '`, `'.join(choices) + "`"

            embed = discord.Embed(color=self.bot.embed_color,
                              description=f"**Choices:** {choice}\n**I'd choose:** `{random.choice(choices)}`")
            await ctx.send(embed=embed)
        except IndexError:
            await ctx.send(f"{emotes.red_mark} Can't choose from empty choices")

    @commands.command(brief="Fight someone", description="Fight someone! Wanna fight with yourself? Leave [user2] empty.\nRequires NSFW marked channel")
    @commands.cooldown(1, 15, commands.BucketType.user)
    @commands.is_nsfw()
    @commands.guild_only()
    async def fight(self, ctx, user1: discord.Member, user2: discord.Member = None):
        """ Fight someone! """

        if user2 == None:
            user2 = ctx.author
        bot = self.bot.get_user(667117267405766696)
        owner = self.bot.get_user(345457928972533773)
        if user1 ==bot or user2 == bot:
            return await ctx.send("I'm not fighting with anyone.")
        if user1 == owner or user2 == owner:
            return await ctx.send("Moksej fucked you up so hard that you died immediately.")

        win = random.choice([user1, user2])
        if win == user1:
            lose = user2
        else:
            lose = user1

        responses = [
            f'That was intense battle, but unfortunatelly {win.mention} has beaten up {lose.mention} to death',
            f'That was a shitty battle, they both fight themselves to death',
            f'Is that a battle? You both suck',
            f'Yo {lose.mention} you lose! Ha',
            f'I\'m not sure how, but {win.mention} has won the battle']

        await ctx.send(f'{random.choice(responses)}')

    @commands.command(aliases=['howhot'], brief="See how hot someone is", description="I wonder how hot are you UwU")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def hot(self, ctx, *, user: discord.Member = None):
        """ I wonder how hot are you 🤔 """

        owner = self.bot.get_user(345457928972533773)
        if user == owner:
            return await ctx.send("My hot calculator has melted down, because of him.")

        bot = self.bot.get_user(667117267405766696)
        if user == bot:
            return await ctx.send("I'm too hot for you 😏")

        if user is None:
            user = ctx.author

        random.seed(user.id)
        r = random.randint(1, 100)
        hot = r / 1.17

        emoji = "\U0001f494"
        if hot > 25:
            emoji = "\U0001f494"
        if hot > 50:
            emoji = "\U00002764"
        if hot > 75:
            emoji = "\U0001f49e"

        embed = discord.Embed(color=self.bot.embed_color,
                              description=f"**{user}** is **{hot:.2f}%** hot. {emoji}")
        await ctx.send(embed=embed)

    @commands.command(brief="Random dad joke", description="Read random dad joke")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def dadjoke(self, ctx):
        """ Dad Jokes """
        async with aiohttp.ClientSession() as session:
            resp = await session.get("https://icanhazdadjoke.com", headers={"Accept": "text/plain"})
            await ctx.send((await resp.content.read()).decode("utf-8 "))

    @commands.command(brief="Roast someone", description="Roast anyone you want\nRequires NSFW marked channel")
    @commands.is_nsfw()
    @commands.guild_only()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def roast(self, ctx, member: discord.Member = None):
        """ Roast someone in the server.
        Requires NSFW channel."""

        await ctx.trigger_typing()

        if member is None:
            member = ctx.author
        bot = self.bot.get_user(667117267405766696)
        if member == bot:
            return await ctx.send("Don't you dare doing that!")
        owner = self.bot.get_user(345457928972533773)
        if member == owner:
            return await ctx.send("I'm not going to do that.")

        with open("db/lines.json", "r") as f:
            data = json.load(f)

        roasts = data["roasts"]
        
        await ctx.send(f"{member.name}, {random.choice(roasts)}")

    @commands.command(brief="Random memes", description=f"Want to see some bad bad random memes? This is the place where you can see them.")
    @commands.cooldown(1, 15)
    async def meme(self, ctx):
        """ Make your life a little bit funnier with memes """

        async with aiohttp.ClientSession() as cs:
            async with cs.get('https://meme-api.herokuapp.com/gimme') as r:
                r = await r.json()
        embed = discord.Embed(color=self.bot.embed_color, title=f"**{r['title']}**", url=r['postLink'])
        embed.set_image(url=r['url'])

        await ctx.send(embed=embed)
    
    @commands.command(brief="Spank someone", description="Spank those naughty users")
    @commands.guild_only()
    @commands.is_nsfw()
    @commands.cooldown(1, 15, commands.BucketType.user)
    @checks.has_voted()
    async def spank(self, ctx, member: discord.Member):
        """ Spank those naughty users """

        bot = self.bot.get_user(667117267405766696)
        if member == bot:
            return await ctx.send("Don't spank me!")
        owner = self.bot.get_user(345457928972533773)
        if member == owner:
            return await ctx.send("Whaaaat?? You're trying to spank my owner?!?")

        async with aiohttp.ClientSession() as cs:
            async with cs.get('https://nekos.life/api/v2/img/spank') as r:
                r = await r.json()
        await ctx.send(embed=discord.Embed(color=self.bot.embed_color, description=f"**{ctx.author}** spanked **{member}**").set_image(url=r['url']))


    @commands.command(brief="Cuddle someone", description="Cuddle someone")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def cuddle(self, ctx, member: discord.Member):
        """ Cuddle someone you want """
        bot = self.bot.get_user(667117267405766696)
        if member == bot:
            return await ctx.send("I don't need any cuddles, kthnxbye.")
        owner = self.bot.get_user(345457928972533773)
        if member == owner:
            return await ctx.send("He doesn't need any cuddles.")
        async with aiohttp.ClientSession() as cs:
            async with cs.get('https://nekos.life/api/v2/img/cuddle') as r:
                r = await r.json()
        await ctx.send(embed=discord.Embed(color=self.bot.embed_color, description=f"**{ctx.author}** cuddled **{member}**").set_image(url=r['url']))

    @commands.command(brief="Hug someone", description="Give someone a hug")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def hug(self, ctx, member: discord.Member):
        """ Give someone a hug """
        bot = self.bot.get_user(667117267405766696)
        if member == bot:
            return await ctx.send("I don't need any hugs, kthnxbye.")
        owner = self.bot.get_user(345457928972533773)
        if member == owner:
            return await ctx.send("He doesn't need any hugs.")
        async with aiohttp.ClientSession() as cs:
            async with cs.get('https://nekos.life/api/v2/img/hug') as r:
                r = await r.json()
        await ctx.send(embed=discord.Embed(color=self.bot.embed_color, description=f"**{ctx.author}** gave **{member}** a hug").set_image(url=r['url']))

    @commands.command(brief="Wallpaper", description="Get yourself a wallpaper")
    @commands.guild_only()
    @commands.cooldown(1, 15, commands.BucketType.user)
    @commands.is_nsfw()
    async def wallpaper(self, ctx):
        """ Get yourself a (cool?) wallpaper """
        async with aiohttp.ClientSession() as cs:
            async with cs.get('https://nekos.life/api/v2/img/wallpaper') as r:
                r = await r.json()
        await ctx.send(embed=discord.Embed(color=self.bot.embed_color).set_image(url=r['url']))
    
    @commands.command(brief="Supreme logo")
    async def supreme(self, ctx, *, text: commands.clean_content(fix_channel_mentions=True)):
        """ Make a fake Supreme logo

        Arguments:
            --dark / -d | Make the background dark
            --light / -l | Make the background light and the text dark
        """
        parser = argparser.Arguments()
        parser.add_argument('input', nargs="+", default=None)
        parser.add_argument('-d', '--dark', action='store_true')
        parser.add_argument('-l', '--light', action='store_true')

        args, valid_check = parser.parse_args(text)
        if not valid_check:
            return await ctx.send(args)

        inputText = urllib.parse.quote(' '.join(args.input))
        if len(inputText) > 500:
            return await ctx.send(f"**{ctx.author.name}**, the Supreme API is limited to 500 characters, sorry.")

        darkorlight = ""
        if args.dark:
            darkorlight = "dark=true"
        if args.light:
            darkorlight = "light=true"
        if args.dark and args.light:
            return await ctx.send(f"**{ctx.author.name}**, you can't define both --dark and --light, sorry..")

        await self.api_img_creator(ctx, f"https://api.alexflipnote.dev/supreme?text={inputText}&{darkorlight}", "supreme.png")

    @commands.command(brief="Pussy images")
    @commands.guild_only()
    @commands.cooldown(1, 15, commands.BucketType.user)
    @commands.is_nsfw()
    @checks.has_voted()
    async def pussy(self, ctx):
        """ Pussy here, pussy there, pussy everywhere """
        async with aiohttp.ClientSession() as cs:
            async with cs.get('https://nekobot.xyz/api/image?type=pussy') as r:
                r = await r.json()
        await ctx.send(embed=discord.Embed(color=self.bot.embed_color).set_image(url=r['message']))

def setup(bot):
    bot.add_cog(fun(bot))
