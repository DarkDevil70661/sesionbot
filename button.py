from pyrogram.types import InlineKeyboardButton

class ButtonStyle:
    PRIMARY = "primary"
    SUCCESS = "success"
    DANGER = "danger"

def styled_button(text, url=None, callback_data=None, style=ButtonStyle.PRIMARY):
    # Standard Pyrogram InlineKeyboardButton generator
    if url:
        return InlineKeyboardButton(text=text, url=url)
    elif callback_data:
        return InlineKeyboardButton(text=text, callback_data=callback_data)
