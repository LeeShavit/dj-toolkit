# Learning a new platform

Use this when the user has a source with no skill yet (e.g. "I use DJcity", "I have Juno Download credits", "my friend uses Lucida"). The output is a **new skill** in `~/.claude/skills/get-songs-platform-<slug>/SKILL.md`, so next time it simply works.

## 1. Explore (research before touching anything)
Find out, in this order of preference, how the platform can be driven:
1. **Official API or CLI**: docs, developer portal.
2. **Well-known open-source tools**: search GitHub for "<platform> downloader cli" and check stars, last commit and open issues. Prefer maintained tools with releases.
3. **Built-in integrations** the user's app already offers: Telegram/WhatsApp bots, watch folders, email-in, URL schemes, text-file import. (Offline DJ's Telegram bot is the model example: Claude sends messages from the user's account and the app does the rest.)
4. **Its local files**: settings/queue files in Application Support / AppData that reveal folders, queues and not-found lists.
5. **Browser automation** (Claude in Chrome) on the website, with the user's own login. This works almost everywhere but is slow and breaks easily, so use it last.
6. **Computer use** on a desktop app. The very last resort.

Collect: how to authenticate, how to submit tracks (one or many), where files land, how to tell success from not-found, rate limits, quality options, and whether purchasing is involved.

## 2. Ask the user only what research can't answer
For example: do you have an account? Which plan? Is it OK if I send messages from your Telegram account to this bot? Credentials go into `~/.claude/dj-toolkit/secrets/<slug>.*` (chmod 600) or the tool's own config. Never put them in markdown or chat logs if there's another way (hidden-input prompts the user runs themselves, QR logins, browser sessions).

## 3. Test with 1-2 tracks
Pick one popular track that should certainly exist and one the user wants. Run the method end to end, find the file on disk and verify it with `scripts/check_audio.py`. If the platform involves money, test only up to "added to cart".

## 4. Write the skill
Copy `../templates/platform-skill.md` to `~/.claude/skills/get-songs-platform-<slug>/SKILL.md` and fill it in from what actually worked: exact commands, file paths, quirks and failure signs. Put helper scripts next to it in `scripts/`. Write it for a future Claude who knows nothing about today's session: concrete commands, and why each step matters.

## 5. Register it
- Add or update the row in `~/.claude/dj-toolkit/platforms.md` (status `ready`, skill name, test result).
- Insert the platform into `source_order` in `config.md` where the user wants it.
- Tell the user it's learned, and that they can share the skill folder with friends who use the same platform.

## Boundaries
- Use only accounts the user owns. Don't create accounts in their name without asking.
- Don't bypass paywalls, DRM, CAPTCHAs or login walls with tricks. If the only route is circumvention, say so and stop.
- Don't complete purchases.
