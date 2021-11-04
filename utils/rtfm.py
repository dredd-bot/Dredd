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
import re
import io
import zlib
import os


def finder(text, collection, *, key=None, lazy=False):
    suggestions = []
    text = str(text)
    pat = '.*?'.join(map(re.escape, text))
    regex = re.compile(pat, flags=re.IGNORECASE)
    for item in collection:
        to_search = key(item) if key else item
        r = regex.search(to_search)
        if r:
            suggestions.append((len(r.group()), r.start(), item))

    def sort_key(tup):
        if key:
            return tup[0], tup[1], key(tup[2])
        return tup

    if lazy:
        return (z for _, _, z in sorted(suggestions, key=sort_key))
    else:
        return [z for _, _, z in sorted(suggestions, key=sort_key)]


class SphinxObjectFileReader:
    # Inspired by Sphinx's InventoryFileReader
    BUFSIZE = 16 * 1024

    def __init__(self, buffer):
        self.stream = io.BytesIO(buffer)

    def readline(self):
        return self.stream.readline().decode('utf-8')

    def skipline(self):
        self.stream.readline()

    def read_compressed_chunks(self):
        decompressor = zlib.decompressobj()
        while True:
            chunk = self.stream.read(self.BUFSIZE)
            if len(chunk) == 0:
                break
            yield decompressor.decompress(chunk)
        yield decompressor.flush()

    def read_compressed_lines(self):
        buf = b''
        for chunk in self.read_compressed_chunks():
            buf += chunk
            pos = buf.find(b'\n')
            while pos != -1:
                yield buf[:pos].decode('utf-8')
                buf = buf[pos + 1:]
                pos = buf.find(b'\n')


def parse_object_inv(stream, url):
    # key: URL
    # n.b.: key doesn't have `discord` or `discord.ext.commands` namespaces
    result = {}

    # first line is version info
    inv_version = stream.readline().rstrip()

    if inv_version != '# Sphinx inventory version 2':
        raise RuntimeError('Invalid objects.inv file version.')

    # next line is "# Project: <name>"
    # then after that is "# Version: <version>"
    projname = stream.readline().rstrip()[11:]
    version = stream.readline().rstrip()[11:]

    # next line says if it's a zlib header
    line = stream.readline()
    if 'zlib' not in line:
        raise RuntimeError('Invalid objects.inv file, not z-lib compatible.')

    # This code mostly comes from the Sphinx repository.
    entry_regex = re.compile(r'(?x)(.+?)\s+(\S*:\S*)\s+(-?\d+)\s+(\S+)\s+(.*)')
    for line in stream.read_compressed_lines():
        match = entry_regex.match(line.rstrip())
        if not match:
            continue

        name, directive, prio, location, dispname = match.groups()
        domain, _, subdirective = directive.partition(':')
        if directive == 'py:module' and name in result:
            # From the Sphinx Repository:
            # due to a bug in 1.1 and below,
            # two inventory entries are created
            # for Python modules, and the first
            # one is correct
            continue

        # Most documentation pages have a label
        if directive == 'std:doc':
            subdirective = 'label'

        if location.endswith('$'):
            location = location[:-1] + name

        key = name if dispname == '-' else dispname
        prefix = f'{subdirective}:' if domain == 'std' else ''

        if projname == 'discord.py':
            key = key.replace('discord.ext.commands.', '').replace('discord.', '')

        result[f'{prefix}{key}'] = os.path.join(url, location)

    return result


async def build_rtfm_lookup_table(self, page_types):
    cache = {}
    for key, page in page_types.items():
        cache[key] = {}
        async with self.session.get(page + '/objects.inv', max_redirects=30) as resp:
            if resp.status != 200:
                raise RuntimeError(_('Cannot build rtfm lookup table, try again later.'))

            stream = SphinxObjectFileReader(await resp.read())
            cache[key] = parse_object_inv(stream, page)

    self._rtfm_cache = cache


# noinspection PyProtectedMember
async def do_rtfm(self, ctx, key, obj):
    page_types = {
        'latest': 'https://enhanced-dpy.readthedocs.io/en/latest',
        'python': 'https://docs.python.org/3'
    }

    if obj is None:
        await ctx.send(page_types[key])
        return

    if not hasattr(self.bot, '_rtfm_cache'):
        await ctx.trigger_typing()
        await build_rtfm_lookup_table(self.bot, page_types)

    obj = re.sub(r'^(?:discord\.(?:ext\.)?)?(?:commands\.)?(.+)', r'\1', obj)

    if key.startswith('latest'):
        # point the abc.Messageable types properly:
        q = obj.lower()
        for name in dir(discord.abc.Messageable):
            if name[0] == '_':
                continue
            if q == name:
                obj = f'abc.Messageable.{name}'
                break

    cache = list(self.bot._rtfm_cache[key].items())

    matches = finder(obj, cache, key=lambda t: t[0])[:12]
    e = discord.Embed(colour=discord.Colour.blurple())
    if len(matches) == 0:
        return await ctx.send(_('I could not find anything, sorry.'))
    v = discord.__version__
    if page_types[key] == page_types['latest']:
        e.set_author(name=_('enhanced discord.py {0}').format(v), icon_url=ctx.author.display_avatar.url, url=page_types[key])
        e.set_footer(text=_("Keep in mind this is NOT the original d.py; certain things may be different"))
    e.title = _('**Search query:** `{0}`\n\n').format(obj.lower())

    e.description = '\n'.join(f'[`{key}`]({url})' for key, url in matches)
    await ctx.send(embed=e)
