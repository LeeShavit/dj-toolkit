"""Talk to the Offline DJ Telegram bot from the user's account.

  tg.py send "Artist - Title"     send one message, print the bot's reply
  tg.py send-file list.txt        one message per line; report how many the bot confirmed
  tg.py read [N]                  last N messages in the bot chat (default 20)
"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tgcommon import load, SESSION
from telethon.sync import TelegramClient

cfg = load()
client = TelegramClient(SESSION, cfg["api_id"], cfg["api_hash"])


def fmt(m):
    who = "me " if m.out else "bot"
    txt = (m.message or "").replace("\n", "\n      ")
    btns = ("  [buttons: " + " | ".join(b.text for row in m.buttons for b in row) + "]") if m.buttons else ""
    return f"{m.date:%H:%M:%S} {who}: {txt}{btns}"


def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    cmd, args = sys.argv[1], sys.argv[2:]
    client.connect()
    try:
        if not client.is_user_authorized():
            sys.exit("Not logged in - run tg_qr_login.py first.")
        bot = client.get_entity(cfg["bot"])
        if cmd == "send":
            sent = client.send_message(bot, " ".join(args)); print("sent")
            for _ in range(10):
                time.sleep(1)
                replies = client.get_messages(bot, min_id=sent.id, limit=10)
                if replies:
                    for m in reversed(replies): print(fmt(m))
                    break
        elif cmd == "send-file":
            lines = [l.strip() for l in open(args[0], encoding="utf-8") if l.strip()]
            first = None
            for l in lines:
                m = client.send_message(bot, l); first = first or m.id; time.sleep(1.5)
            time.sleep(4)
            replies = [m for m in client.get_messages(bot, min_id=first - 1, limit=1000) if not m.out]
            ok = sum("SENT" in (m.message or "") for m in replies)
            print(f"sent {len(lines)} messages, bot confirmed {ok}")
            for m in reversed(replies):
                if "SENT" not in (m.message or ""): print(fmt(m))
        elif cmd == "read":
            for m in reversed(client.get_messages(bot, limit=int(args[0]) if args else 20)):
                print(fmt(m))
        else:
            print(__doc__)
    finally:
        client.disconnect()


main()
