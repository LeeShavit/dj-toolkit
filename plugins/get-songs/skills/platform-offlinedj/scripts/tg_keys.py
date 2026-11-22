"""Save Telegram API keys + Offline DJ bot name.
Interactive (user runs it in Terminal, hash hidden):  tg_keys.py
Non-interactive:  tg_keys.py --api-id 123 --api-hash abc --bot OfflineDJapp_BOT
"""
import argparse, getpass, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from tgcommon import load, save, CFG

ap = argparse.ArgumentParser()
ap.add_argument("--api-id", type=int); ap.add_argument("--api-hash"); ap.add_argument("--bot")
a = ap.parse_args()
cfg = load() if os.path.exists(CFG) else {}
if a.api_id: cfg["api_id"] = a.api_id
if a.api_hash: cfg["api_hash"] = a.api_hash
if a.bot: cfg["bot"] = a.bot.lstrip("@")
if not cfg.get("api_id"):
    print("Get these at https://my.telegram.org -> API development tools")
    cfg["api_id"] = int(input("api_id: ").strip())
if not cfg.get("api_hash"):
    cfg["api_hash"] = getpass.getpass("api_hash (hidden): ").strip()
if not cfg.get("bot"):
    cfg["bot"] = input("Offline DJ bot @username: ").strip().lstrip("@")
save(cfg)
print(f"Saved. Bot: @{cfg['bot']}. Next: tg_qr_login.py")
