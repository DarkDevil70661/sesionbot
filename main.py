import asyncio
import yaml
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import (
    UserNotParticipant, SessionPasswordNeeded, FloodWait, InputUserDeactivated, UserIsBlocked
)
from motor.motor_asyncio import AsyncIOMotorClient

import config

# Load all strings from en.yml
with open("en.yml", "r", encoding="utf-8") as f:
    strings = yaml.safe_load(f)

# MongoDB Connection Setup
mongo_client = AsyncIOMotorClient(config.MONGO_URL)
db = mongo_client["session_bot_db"]
users_collection = db["users"]

bot = Client("session_generator_bot", api_id=config.API_ID, api_hash=config.API_HASH, bot_token=config.BOT_TOKEN)

user_steps = {}
user_data = {}

# User Logger Function
async def log_new_user(client, user):
    first = user.first_name or "N/A"
    last = user.last_name or ""
    full_name = f"{first} {last}".strip()
    username = f"@{user.username}" if user.username else "No Username"
    user_id = user.id

    await users_collection.update_one(
        {"user_id": user_id},
        {"$set": {"full_name": full_name, "username": username}},
        upsert=True
    )

    log_text = strings["log_text"].format(
        full_name=full_name,
        user_id=user_id,
        username=username
    )

    try:
        photos = [p async for p in client.get_chat_photos(user_id, limit=1)]
        if photos:
            await client.send_photo(
                chat_id=config.LOG_GROUP_ID,
                photo=photos[0].file_id,
                caption=log_text,
                parse_mode=enums.ParseMode.HTML
            )
        else:
            await client.send_message(
                chat_id=config.LOG_GROUP_ID, 
                text=log_text,
                parse_mode=enums.ParseMode.HTML
            )
    except Exception:
        try:
            await client.send_message(
                chat_id=config.LOG_GROUP_ID, 
                text=log_text,
                parse_mode=enums.ParseMode.HTML
            )
        except Exception:
            pass

# Channel Membership Check Function
async def check_joined(client, user_id):
    try:
        await client.get_chat_member(config.CHANNEL_1, user_id)
        await client.get_chat_member(config.CHANNEL_2, user_id)
        return True
    except UserNotParticipant:
        return False
    except Exception:
        return False

# Send Main Interface Function (Photo and Caption Together in a Single Message)
async def send_main_menu(message_obj):
    if hasattr(message_obj, "from_user"):
        user = message_obj.from_user
        target_msg = message_obj
    else:
        user = message_obj.message.chat
        target_msg = message_obj.message

    first_name = user.first_name or "User"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(text="✨ ⚡ GENERATE SESSION ⚡ ✨", callback_data="gen_session")
        ],
        [
            InlineKeyboardButton(text="🚀 FAST SESSION 🚀", callback_data="fast_session")
        ],
        [
            InlineKeyboardButton(text="👑 OWNER", url="https://t.me/OWNER_ENAFUL"),
            InlineKeyboardButton(text="📢 CHANNEL", url=f"https://t.me/{config.CHANNEL_1}")
        ],
        [
            InlineKeyboardButton(text="💬 SUPPORT GROUP", url=f"https://t.me/{config.CHANNEL_2}")
        ]
    ])

    caption = strings["welcome_caption"].format(
        first_name=first_name,
        user_id=user.id
    )

    # Sending photo and caption together in one single message
    try:
        await target_msg.reply_photo(
            photo=config.WELCOME_IMG,
            caption=caption,
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.HTML
        )
    except Exception:
        # Fallback to text only if photo link fails
        await target_msg.reply_text(
            text=caption, 
            reply_markup=keyboard,
            parse_mode=enums.ParseMode.HTML
        )

# Start Command
@bot.on_message(filters.command("start"))
async def start_cmd(client, message):
    user_id = message.from_user.id
    user_steps[user_id] = None
    user_data[user_id] = {}

    await log_new_user(client, message.from_user)

    is_joined = await check_joined(client, user_id)
    if not is_joined:
        join_buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(text="📢 JOIN CHANNEL 1", url=f"https://t.me/{config.CHANNEL_1}"),
                InlineKeyboardButton(text="📢 JOIN CHANNEL 2", url=f"https://t.me/{config.CHANNEL_2}")
            ],
            [
                InlineKeyboardButton(text="👑 BOT OWNER", url="https://t.me/OWNER_ENAFUL")
            ],
            [
                InlineKeyboardButton(text="✅ VERIFY JOIN ✅", callback_data="verify_join")
            ]
        ])
        
        verify_text = strings["verify_text"]
        return await message.reply_text(
            verify_text, 
            reply_markup=join_buttons,
            parse_mode=enums.ParseMode.HTML
        )

    await send_main_menu(message)

# Callback Handlers
@bot.on_callback_query()
async def callback_handler(client, query):
    user_id = query.from_user.id

    if query.data == "verify_join":
        is_joined = await check_joined(client, user_id)
        if is_joined:
            await query.answer("✅ Verification successful!", show_alert=True)
            try:
                await query.message.delete()
            except Exception:
                pass
            await send_main_menu(query)
        else:
            await query.answer("❌ Channel missing! Please join both channels.", show_alert=True)

    elif query.data == "gen_session":
        user_steps[user_id] = "WAITING_API_ID"
        await query.message.reply_text(
            strings["api_id_prompt"],
            parse_mode=enums.ParseMode.HTML
        )

    elif query.data == "fast_session":
        user_data[user_id]["api_id"] = config.API_ID
        user_data[user_id]["api_hash"] = config.API_HASH
        user_steps[user_id] = "WAITING_PHONE"
        await query.message.reply_text(
            strings["phone_prompt"],
            parse_mode=enums.ParseMode.HTML
        )

# Broadcast Command
@bot.on_message(filters.command("broadcast") & filters.user(config.OWNER_ID))
async def broadcast_handler(client, message):
    if not message.reply_to_message:
        return await message.reply_text(
            strings["broadcast_no_reply"],
            parse_mode=enums.ParseMode.HTML
        )

    status_msg = await message.reply_text(
        strings["broadcast_start"],
        parse_mode=enums.ParseMode.HTML
    )

    success = 0
    failed = 0
    blocked = 0

    cursor = users_collection.find({})
    async for user in cursor:
        user_id = user["user_id"]
        try:
            await message.reply_to_message.copy(chat_id=user_id)
            success += 1
            await asyncio.sleep(0.05)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            await message.reply_to_message.copy(chat_id=user_id)
            success += 1
        except (UserIsBlocked, InputUserDeactivated):
            blocked += 1
            await users_collection.delete_one({"user_id": user_id})
        except Exception:
            failed += 1

    await status_msg.edit_text(
        strings["broadcast_done"].format(
            success=success,
            failed=failed,
            blocked=blocked
        ),
        parse_mode=enums.ParseMode.HTML
    )

# Message Handler
@bot.on_message(filters.text & filters.private)
async def process_inputs(client, message):
    user_id = message.from_user.id
    step = user_steps.get(user_id)
    text = message.text

    if not step:
        return

    if step == "WAITING_API_ID":
        if not text.isdigit():
            return await message.reply_text(
                strings["api_numeric_error"],
                parse_mode=enums.ParseMode.HTML
            )
        user_data[user_id]["api_id"] = int(text)
        user_steps[user_id] = "WAITING_API_HASH"
        await message.reply_text(
            strings["api_hash_prompt"],
            parse_mode=enums.ParseMode.HTML
        )

    elif step == "WAITING_API_HASH":
        user_data[user_id]["api_hash"] = text
        user_steps[user_id] = "WAITING_PHONE"
        await message.reply_text(
            strings["phone_prompt"],
            parse_mode=enums.ParseMode.HTML
        )

    elif step == "WAITING_PHONE":
        user_data[user_id]["phone"] = text
        await message.reply_text(
            strings["otp_sending"],
            parse_mode=enums.ParseMode.HTML
        )
        
        temp_client = Client(
            f"user_{user_id}",
            api_id=user_data[user_id]["api_id"],
            api_hash=user_data[user_id]["api_hash"],
            in_memory=True
        )
        await temp_client.connect()
        try:
            code_info = await temp_client.send_code(user_data[user_id]["phone"])
            user_data[user_id]["temp_client"] = temp_client
            user_data[user_id]["phone_code_hash"] = code_info.phone_code_hash
            user_steps[user_id] = "WAITING_OTP"
            await message.reply_text(
                strings["otp_prompt"],
                parse_mode=enums.ParseMode.HTML
            )
        except Exception as e:
            await temp_client.disconnect()
            user_steps[user_id] = None
            await message.reply_text(
                strings["otp_error"].format(e=e),
                parse_mode=enums.ParseMode.HTML
            )

    elif step == "WAITING_OTP":
        otp = text.replace(" ", "")
        temp_client = user_data[user_id]["temp_client"]
        try:
            await temp_client.sign_in(
                phone_number=user_data[user_id]["phone"],
                phone_code_hash=user_data[user_id]["phone_code_hash"],
                phone_code=otp
            )
            string_session = await temp_client.export_session_string()
            await temp_client.disconnect()
            
            await message.reply_text(
                strings["session_success"].format(string_session=string_session),
                parse_mode=enums.ParseMode.HTML
            )
            user_steps[user_id] = None
            
        except SessionPasswordNeeded:
            user_steps[user_id] = "WAITING_PASSWORD"
            await message.reply_text(
                strings["password_prompt"],
                parse_mode=enums.ParseMode.HTML
            )
        except Exception as e:
            await temp_client.disconnect()
            user_steps[user_id] = None
            await message.reply_text(
                strings["otp_fail"].format(e=e),
                parse_mode=enums.ParseMode.HTML
            )

    elif step == "WAITING_PASSWORD":
        temp_client = user_data[user_id]["temp_client"]
        try:
            await temp_client.check_password(text)
            string_session = await temp_client.export_session_string()
            await temp_client.disconnect()
            
            await message.reply_text(
                strings["session_success"].format(string_session=string_session),
                parse_mode=enums.ParseMode.HTML
            )
            user_steps[user_id] = None
        except Exception as e:
            await temp_client.disconnect()
            user_steps[user_id] = None
            await message.reply_text(
                strings["password_fail"].format(e=e),
                parse_mode=enums.ParseMode.HTML
            )

bot.run()
