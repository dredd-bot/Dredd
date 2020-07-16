## Dredd's Privacy Policy

### By using Dredd you accept with its privacy policy. 

### 1. What does it store?
#### Dredd stores the following: 
##### • Server IDs for servers data (prefixes, and other settings like logging, automod and so on), blacklist.
##### • User IDs for blacklist, nickname changes, todo lists, warnings (including automod warns) from moderators in servers, temporary mutes, suggestions, bug reports and following suggestions/bug reports.

### 2. Who can access the data?
#### Following people can access ALL of the data:
##### • Bot developer(s)
#### Following people can access secret data (servers data/settings, blacklists, suggestions and bug reports):
##### • Bot administrator
##### • Bot developer(s)
#### Following people can access warnings, temporary mutes:
##### • Server moderators that the user was muted/warned
#### Following people can access nickname changes (history):
##### • Everyone who is in the same server as you
#### Following people can access todo lists:
##### • No one, besides you. (not including bot developer(s))

### 3. How can I get rid of the data stored?
#### To clear your nicknames you can opt-out which will also stop logging your nicknames by invoking `<serverprefix>nicks opt-out`. That will fully erase your nicknames you had in the past and will stop logging your future nicknames.
#### To clear your todo list you can invoke `<serverprefix>todo clear`
#### To clear your warnings:
##### • You must leave the server
##### • You must kick the bot from the server
#### To clear your temporary punishments:
##### • You must kick the bot from the server

### 4. Why does it store the data?
#### It stores server IDs for settings and data because:
##### • Without those most of the bot wouldn't be functional. The loggs would break or wouldn't be customisable, you couldn't invoke any of the commands bot has.
#### It stores user IDs for nickname changes, todo lists, warnings, temporary mutes, suggestions and bugs because:
##### • Bot needs to find the user that has the data stored in the database as - todo lists, nickname changes and return that data to them
##### • Bot needs to find the user that has data stored in database as - suggestions, bug reports to know who was the owner of the suggestion/bug report and inform them when the suggestion/bug was approved/confirmed. Also the users that followed that suggestion/bug report.
##### • Bot needs to find the user who was temporarily muted and punish them if they try to rejoin or unmute them when their punishment ends.
#### It stores server IDs and user IDs for blacklist because:
##### • We need to prevent people/servers that abuse the bot, break bot rules.

### 5. I'm questioning why do you need all this data, and this Privacy Policy doesn't answer my question. What should I do?
#### Feel free to join the [support server](https://discord.gg/f3MaASW) and/or contact [Moksej#3335](https://discord.com/channels/@me/345457928972533773).
