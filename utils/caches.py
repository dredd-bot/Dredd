import json
from utils.default import traceback_maker

async def cache(bot):
    owners = await bot.db.fetch("SELECT * FROM owners")
    for res in owners:
        bot.owners[res['user_id']] = 'my owner'
    print(f'[OWNERS] Owners loaded')

    admins = await bot.db.fetch("SELECT * FROM admins")
    for res in admins:
        bot.admins[res['user_id']] = 'my admin'
    print(f'[ADMINS] Admins loaded')

    boosters = await bot.db.fetch("SELECT * FROM vip")
    for res in boosters:
        bot.boosters[res['user_id']] = {'custom_prefix': res['prefix']}
    print(f'[BOOSTERS] Boosters loaded')

    prefixes = await bot.db.fetch("SELECT * FROM guilds")
    for res in prefixes:
        bot.prefixes[res['guild_id']] = res['prefix']
    print(f'[PREFIXES] Prefixes loaded')

    blacklist_user = await bot.db.fetch("SELECT * FROM blacklist")
    for user in blacklist_user:
        bot.blacklisted_users[user['user_id']] = [user['reason']]
    print(f'[BLACKLIST] Users blacklist loaded [{len(blacklist_user)}]')

    blacklist_guild = await bot.db.fetch("SELECT * FROM blockedguilds")
    for guild in blacklist_guild:
        bot.blacklisted_guilds[guild['guild_id']] = [guild['reason']]
    print(f'[BLACKLIST] Guilds blacklist loaded [{len(blacklist_guild)}]')

    afk_user = await bot.db.fetch("SELECT * FROM userafk")
    for res in afk_user:
        #bot.afk_users[res['user_id']] = {'time': res['time'], 'guild': res['guild_id'], 'message': res['message']}
        bot.afk_users.append((res['user_id'], res['guild_id'], res['message'], res['time']))
    print(f'[AFK] AFK users loaded [{len(afk_user)}]')

    temp_mutes = await bot.db.fetch("SELECT * FROM moddata")
    for res in temp_mutes:
        if res['time'] is None:
            continue
        if res['type'] == 'mute':
            bot.temp_timer.append((res['guild_id'], res['user_id'], res['mod_id'], res['reason'], res['time'], res['role_id'], res['type']))
    print(f'[TEMP MUTE] Mutes loaded [{len(bot.temp_timer)}]')

    temp_mutes = await bot.db.fetch("SELECT * FROM moddata")
    for res in temp_mutes:
        if res['time'] is None:
            continue
        if res['type'] == 'ban':
            bot.temp_bans.append((res['guild_id'], res['user_id'], res['mod_id'], res['reason'], res['time'], res['type']))
    print(f'[TEMP BAN] Bans loaded [{len(bot.temp_bans)}]')

    automod = await bot.db.fetch("SELECT * FROM automods")
    for res in automod:
        bot.automod[res['guild_id']] = res['punishment']
    print(f"[AUTOMOD] Automod settings loaded")

    automod_actions = await bot.db.fetch("SELECT * FROM automodaction")
    for res in automod_actions:
        bot.automod_actions[res['guild_id']] = res['channel_id']
    print(f"[AUTOMOD] Automod logging loaded")

    invites = await bot.db.fetch("SELECT * FROM inv")
    for res in invites:
        bot.invites[res['guild_id']] = res['punishment']
    print(f"[INVITES AUTOMOD] Loaded!")

    caps = await bot.db.fetch("SELECT * FROM caps")
    for res in caps:
        bot.mascaps[res['guild_id']] = res['punishment']
    print(f"[CAPS AUTOMOD] Loaded!")

    links = await bot.db.fetch("SELECT * FROM link")
    for res in links:
        bot.links[res['guild_id']] = res['punishment']
    print(f"[LINKS AUTOMOD] Loaded!")

    mentions = await bot.db.fetch("SELECT * FROM massmention")
    for res in mentions:
        bot.mentionslimit[res['guild_id']] = res['punishment']
    print(f"[MENTIONS LIMIT AUTOMOD] Loaded!")

    mentions2 = await bot.db.fetch("SELECT * FROM mentions")
    for res in mentions2:
        bot.massmentions[res['guild_id']] = res['mentions']
    print(f"[MENTIONS AUTOMOD] Loaded!")

    raid_mode = await bot.db.fetch("SELECT * FROM raidmode")
    for res in raid_mode:
        bot.raidmode[res['guild_id']] = {'raidmode': res['raidmode'], 'dm': res['dm']}
    print(f'[RAID MODE] raid mode settings loaded')

    case = await bot.db.fetch("SELECT * FROM modlog")
    for res in case:
        bot.case_num[res['guild_id']] = res['case_num']
    print("[CASES] Cases loaded")

    mod = await bot.db.fetch("SELECT * FROM moderation")
    for res in mod:
        bot.moderation[res['guild_id']] = res['channel_id']
    print(f"[MODERATION] Moderation logs loaded")
    
    msgedit = await bot.db.fetch("SELECT * FROM msgedit")
    for res in msgedit:
        bot.msgedit[res['guild_id']] = res['channel_id']
    print(f"[MESSAGE EDITS] Edited messages logs loaded")

    joinlog = await bot.db.fetch("SELECT * FROM joinlog")
    for res in joinlog:
        bot.joinlog[res['guild_id']] = res['channel_id']
    print(f"[JOIN LOGGING] Join logs loaded")

    joinrole = await bot.db.fetch("SELECT * FROM joinrole")
    for res in joinrole:
        bot.joinrole[res['guild_id']] = {'people': res['role_id'], 'bots': res['bots']}
    print(f"[JOIN ROLE] Join roles loaded")

    memberupdate = await bot.db.fetch("SELECT * FROM memberupdate")
    for res in memberupdate:
        bot.memberupdate[res['guild_id']] = res['channel_id']
    print(f"[MEMBER UPDATE] Member update logs loaded")

    msgdelete = await bot.db.fetch("SELECT * FROM msgdelete")
    for res in msgdelete:
        bot.msgdelete[res['guild_id']] = res['channel_id']
    print(f"[MESSAGE DELETIONS] Deleted messages logs loaded")

    joinmsg = await bot.db.fetch("SELECT * FROM joinmsg")
    for res in joinmsg:
        bot.joinmsg[res['guild_id']] = {'channel': res['channel_id'], 'bot_joins': res['bot_join'], 'embed': res['embed'], 'message': res['msg']}
    print(f"[WELCOMING MESSAGES] Welcoming messages loaded")

    leavemsg = await bot.db.fetch("SELECT * FROM leavemsg")
    for res in leavemsg:
        bot.leavemsg[res['guild_id']] = {'channel': res['channel_id'], 'bot_joins': res['bot_join'], 'embed': res['embed'], 'message': res['msg']}
    print(f"[LEAVING MESSAGES] Leaving messages loaded")

    antidehoist = await bot.db.fetch("SELECT * FROM antidehoist")
    for res in antidehoist:
        bot.antidehoist[res['guild_id']] = {'channel': res['channel_id'], 'nickname': res['new_nick']}
    print(f"[ANTI DEHOIST] Anti dehoist logs loaded")

    whitelisted_channels = await bot.db.fetch("SELECT * FROM whitelist")
    for res in whitelisted_channels:
        if res['channel_id'] is None:
            continue
        try:
            bot.whitelisted_channels[res['guild_id']].append(res['channel_id'])
        except KeyError:
            bot.whitelisted_channels[res['guild_id']] = [res['channel_id']]
    print("[WHITELISTED CHANNELS] Whitelisted channels loaded")

    whitelisted_roles = await bot.db.fetch("SELECT * FROM whitelist")
    for res in whitelisted_roles:
        if res['role_id'] is None:
            continue
        try:
            bot.whitelisted_roles[res['guild_id']].append(res['role_id'])
        except KeyError:
            bot.whitelisted_roles[res['guild_id']] = [res['role_id']]
    print("[WHITELISTED ROLES] Whitelisted roles loaded")

    try:
        with open('db/badges.json', 'r') as f:
            data = json.load(f)
        for user in data['Users']:
            bot.user_badges[user] = {"Badges": data['Users'][user]['Badges']}
        print('[BADGES] User badges cached!')
    except Exception as e:
        print(f'[BADGES EXCEPTION!] Failed to cache badges: {e}')
    
    snipe_op_out = await bot.db.fetch("SELECT * FROM snipe_op_out")
    for res in snipe_op_out:
        bot.snipes_op_out[res['user_id']] = '.'
    print("[SNIPES] Opted out users loaded")

    status_op_out = await bot.db.fetch("SELECT * FROM status_op_out")
    for res in status_op_out:
        bot.status_op_out[res['user_id']] = '.'
    print("[STATUS] Opted in users laoded")

class CacheManager:
    def __init__(self, bot, *, id: int, data: str):
        self.bot = bot

    def get_cache(self, id: int, data: str):

        try:
            attr = getattr(self, data)
            if attr is None:
                print("Not found")
                return
            d = attr[id]

        except Exception as e:
            return

        return d
    
    def delete_cache(self, id: int):
        try:
            self.prefixes.pop(id)
        except:
            pass
        try:
            self.automod.pop(id)
        except:
            pass
        try:
            self.raidmode.pop(id)
        except:
            pass
        try:
            self.case_num.pop(id)
        except:
            pass
        try:
            self.moderation.pop(id)
        except:
            pass
        try:
            self.msgedit.pop(id)
        except:
            pass
        try:
            self.msgdelete.pop(id)
        except:
            pass
        try:
            self.joinlog.pop(id)
        except:
            pass
        try:
            self.invites.pop(id)
        except:
            pass
        try:
            self.links.pop(id)
        except:
            pass
        try:
            self.masscaps.pop(id)
        except:
            pass
        try:
            self.massmentions.pop(id)
        except:
            pass
        try:
            self.memberupdate.pop(id)
        except:
            pass
        try:
            self.joinmsg.pop(id)
        except:
            pass
        try:
            self.leavemsg.pop(id)
        except:
            pass
        try:
            self.antidehoist.pop(id)
        except:
            pass
        try:
            self.whitelisted_channels.pop(id)
        except:
            pass
        try:
            self.whitelisted_roles.pop(id)
        except:
            pass