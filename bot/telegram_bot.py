import asyncio
import os
import re

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.resolver.core import resolve

URL_RE = re.compile(r"https?://\S+", re.I)
MAX_LINKS = 3


async def start(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "vplink.in ya koi bhi safelink bhejo, seedha destination de dunga."
    )


async def on_message(update: Update, _: ContextTypes.DEFAULT_TYPE) -> None:
    links = URL_RE.findall(update.message.text or "")[:MAX_LINKS]
    if not links:
        return
    status = await update.message.reply_text("Resolving...")
    lines = []
    for link in links:
        r = await resolve(link)
        if r.status == "ok":
            lines.append(f"✅ `{r.destination}`\n   _{r.elapsed_ms} ms_")
        elif r.status == "invalid":
            lines.append(f"⚠️ `{link}` invalid")
        elif r.status == "protected":
            lines.append(f"🔒 `{link}` gate clear nahi hua (proxy lagao)")
        else:
            lines.append(f"❌ `{link}` -> {r.status}")
    await status.edit_text("\n\n".join(lines), parse_mode=ParseMode.MARKDOWN,
                           disable_web_page_preview=True)


def main() -> None:
    app = Application.builder().token(os.environ["BOT_TOKEN"]).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    asyncio.run(main())
