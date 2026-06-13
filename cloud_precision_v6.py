# import os
# import re
# import asyncio
# import logging
# import gc
# import random
# from time import perf_counter
# from datetime import datetime, timedelta, timezone
# from aiohttp import web
# from telethon import TelegramClient, events, utils
# from telethon.sessions import StringSession
# from telethon.tl.functions.messages import SendMessageRequest
# from telethon.tl.functions import PingRequest

# # ================= CONFIGURATION =================
# logging.basicConfig(
#     level=logging.INFO,
#     format='%(asctime)s - CloudPrecisionV7 - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger("CloudPrecisionV7_IST")

# # --- Cloud Environment Variables (Same as V6) ---
# API_ID = int(os.environ.get("API_ID"))
# API_HASH = os.environ.get("API_HASH")
# SESSION_STRING = os.environ.get("SESSION_STRING")

# SOURCE_CHAT_ID = os.environ.get("SOURCE_CHAT_ID", "me")
# SOURCE_CHAT_ID_RESOLVED = None
# try: SOURCE_CHAT_ID = int(SOURCE_CHAT_ID)
# except ValueError: pass

# DEFAULT_TARGET_CHAT_ID = os.environ.get("TARGET_CHAT_ID")
# try: DEFAULT_TARGET_CHAT_ID = int(DEFAULT_TARGET_CHAT_ID)
# except (ValueError, TypeError): pass

# # --- V7 GOD-MODE OFFSET ---
# # Ab delay bohot kam ho gaya hai raw request ki wajah se. 12ms safe zone hai.
# SERVER_PROCESSING_OVERHEAD_MS = 12.0

# # Base timezone difference (IST is UTC+5:30)
# IST_OFFSET = timedelta(hours=5, minutes=30)

# loop = asyncio.new_event_loop()
# asyncio.set_event_loop(loop)
# client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH, loop=loop)

# # V6 wala robust payload parser
# TIMESTAMP_REGEX = re.compile(r'(?:time|timestamp|unix)?\s*[:=]?\s*(\d{10}(?:\.\d+)?|\d{13})', re.IGNORECASE)

# def parse_payload(text):
#     msg_body, target_ts, target_chat = None, None, DEFAULT_TARGET_CHAT_ID
#     match_msg = re.search(r"message\s*:\s*(.*?)\s*time\s*:", text, re.IGNORECASE | re.DOTALL)
#     if match_msg: msg_body = match_msg.group(1).strip()
    
#     match_unix = TIMESTAMP_REGEX.search(text)
#     if match_unix and not match_msg:
#         ts_str = match_unix.group(1)
#         target_ts = float(ts_str) / 1000.0 if len(ts_str) >= 13 and '.' not in ts_str else float(ts_str)
#         msg_body = text.replace(match_unix.group(0), "").strip() or "Cloud Trigger Event"
#     else:
#         match_time = re.search(r"time\s*:\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(am|pm)?", text, re.IGNORECASE)
#         if match_time:
#             hours, minutes = int(match_time.group(1)), int(match_time.group(2))
#             seconds = int(match_time.group(3)) if match_time.group(3) else 0
#             am_pm = match_time.group(4).lower() if match_time.group(4) else None
#             if am_pm == 'pm' and hours != 12: hours += 12
#             elif am_pm == 'am' and hours == 12: hours = 0
            
#             # IST based calculation
#             now_ist = datetime.now(timezone.utc) + IST_OFFSET
#             target_dt_ist = now_ist.replace(hour=hours, minute=minutes, second=seconds, microsecond=0)
#             if target_dt_ist < now_ist: target_dt_ist += timedelta(days=1)
#             target_ts = (target_dt_ist - IST_OFFSET).timestamp()

#     match_target = re.search(r"target\s*:\s*([^\s\n]+)", text, re.IGNORECASE)
#     if match_target:
#         try: target_chat = int(match_target.group(1).strip())
#         except ValueError: target_chat = match_target.group(1).strip()
        
#     return msg_body, target_ts, target_chat

# async def function_pre_warm(client):
#     """Sends a silent ping to keep the MTProto socket hot."""
#     try:
#         await client(PingRequest(ping_id=random.randint(1, 100000)))
#         logger.info("MTProto Socket Pre-Warmed Successfully.")
#     except Exception as e:
#         logger.warning(f"Socket warmup failed, but continuing: {e}")

# async def schedule_cloud_delivery(target_ts, chat_id, message_text):
#     try:
#         target_dt_utc = datetime.fromtimestamp(target_ts, timezone.utc)
#         target_dt_ist = target_dt_utc + IST_OFFSET
#         offset_seconds = SERVER_PROCESSING_OVERHEAD_MS / 1000.0
        
#         logger.info(f"Scheduled Cloud Delivery for: {target_dt_ist.strftime('%Y-%m-%d %H:%M:%S.%f')} (IST)")
#         logger.info(f"Target Chat: {chat_id} | V7 Raw Offset: {SERVER_PROCESSING_OVERHEAD_MS} ms")

#         # V7 PRE-RESOLVE: Entity aur Raw Request pehle hi banakar ready rakhlo
#         target_entity = await client.get_input_entity(chat_id)
        
#         raw_request = SendMessageRequest(
#             peer=target_entity,
#             message=message_text,
#             random_id=random.randint(-9223372036854775808, 9223372036854775807),
#             no_webpage=True
#         )

#         warmed_up = False

#         while True:
#             current_time = datetime.now(timezone.utc)
#             time_left = (target_dt_utc - current_time).total_seconds()

#             if time_left <= 0:
#                 break

#             # T-Minus 3 seconds: Pre-warm socket
#             if time_left <= 3.0 and not warmed_up:
#                 await function_pre_warm(client)
#                 warmed_up = True

#             # Hybrid Spinlock Phase 1: OS-Friendly Sleep (Bachaav from CPU Lag)
#             if time_left > 0.005:
#                 await asyncio.sleep(0.001)
#                 continue
            
#             # Hybrid Spinlock Phase 2: Bare-Metal Micro-Spinlock
#             logger.info("Entering V7 Hybrid Micro-Spinlock...")
#             gc.disable()
            
#             trigger_target_ts = target_dt_utc.timestamp() - offset_seconds
            
#             # Absolute tight loop for the last 5 milliseconds
#             while datetime.now(timezone.utc).timestamp() < trigger_target_ts:
#                 pass
            
#             # FIRE RAW PACKET
#             trigger_time = datetime.now(timezone.utc)
#             await client(raw_request)
#             ack_time = datetime.now(timezone.utc)
            
#             gc.enable()

#             delta_ms = (ack_time.timestamp() - target_dt_utc.timestamp()) * 1000

#             logger.info("========== V7 CLOUD EXECUTION REPORT ==========")
#             logger.info(f"Local Cloud Trigger:    {(trigger_time + IST_OFFSET).strftime('%Y-%m-%d %H:%M:%S.%f')}")
#             logger.info(f"Server Acknowledgment:  {(ack_time + IST_OFFSET).strftime('%Y-%m-%d %H:%M:%S.%f')}")
#             logger.info(f"Final Landing Delta:    {delta_ms:+.3f} ms")
#             logger.info("============================================")
#             break

#     except Exception as e:
#         gc.enable()
#         logger.error(f"Execution Failed: {e}")

# @client.on(events.NewMessage)
# async def message_handler(event):
#     if SOURCE_CHAT_ID_RESOLVED and event.chat_id != SOURCE_CHAT_ID_RESOLVED: return
#     msg_body, target_ts, target_chat = parse_payload(event.raw_text)
#     if not target_ts or not msg_body: return
    
#     logger.info("Instruction received.")
#     loop.create_task(schedule_cloud_delivery(target_ts, target_chat, msg_body))

# async def dummy_web_handler(request):
#     return web.Response(text="Cloud Precision Bot V7 (Env Secured) is Online and Running.")

# async def start_web_server():
#     app = web.Application()
#     app.router.add_get('/', dummy_web_handler)
#     runner = web.AppRunner(app)
#     await runner.setup()
#     port = int(os.environ.get("PORT", 10000))
#     site = web.TCPSite(runner, '0.0.0.0', port)
#     await site.start()
#     logger.info(f"Web server started on port {port}")

# async def main():
#     await client.start()
#     global SOURCE_CHAT_ID_RESOLVED
#     try:
#         entity = await client.get_input_entity(SOURCE_CHAT_ID)
#         SOURCE_CHAT_ID_RESOLVED = utils.get_peer_id(entity)
#     except Exception:
#         SOURCE_CHAT_ID_RESOLVED = int(SOURCE_CHAT_ID) if isinstance(SOURCE_CHAT_ID, int) else SOURCE_CHAT_ID
            
#     logger.info(f"Cloud Precision V7 [IST LOCKED] listening on: {SOURCE_CHAT_ID_RESOLVED}")
    
#     await start_web_server()
#     await client.run_until_disconnected()

# if __name__ == '__main__':
#     loop.run_until_complete(main())








#--------------------------------------------------------------------------------------------------------------------------------



import os
import re
import asyncio
import logging
import gc
import random
from time import perf_counter
from datetime import datetime, timedelta, timezone
from aiohttp import web
from telethon import TelegramClient, events, utils
from telethon.sessions import StringSession
from telethon.tl.functions.messages import SendMessageRequest
from telethon.tl.functions import PingRequest

# ================= CONFIGURATION =================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - CloudPrecisionV8.1 - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CloudPrecisionV8_IST")

API_ID = int(os.environ.get("API_ID"))
API_HASH = os.environ.get("API_HASH")
SESSION_STRING = os.environ.get("SESSION_STRING")

SOURCE_CHAT_ID = os.environ.get("SOURCE_CHAT_ID", "me")
SOURCE_CHAT_ID_RESOLVED = None
try: SOURCE_CHAT_ID = int(SOURCE_CHAT_ID)
except ValueError: pass

DEFAULT_TARGET_CHAT_ID = os.environ.get("TARGET_CHAT_ID")
try: DEFAULT_TARGET_CHAT_ID = int(DEFAULT_TARGET_CHAT_ID)
except (ValueError, TypeError): pass

# V8.1 ABORT FEATURE: Lock ki jagah hum Task ko memory mein hold karenge
CURRENT_SNIPER_TASK = None

# Base timezone difference (IST is UTC+5:30)
IST_OFFSET = timedelta(hours=5, minutes=30)

loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH, loop=loop)

TIMESTAMP_REGEX = re.compile(r'(?:time|timestamp|unix)?\s*[:=]?\s*(\d{10}(?:\.\d+)?|\d{13})', re.IGNORECASE)

def parse_payload(text):
    msg_body, target_ts, target_chat = None, None, DEFAULT_TARGET_CHAT_ID
    match_msg = re.search(r"message\s*:\s*(.*?)\s*time\s*:", text, re.IGNORECASE | re.DOTALL)
    if match_msg: msg_body = match_msg.group(1).strip()
    
    match_unix = TIMESTAMP_REGEX.search(text)
    if match_unix and not match_msg:
        ts_str = match_unix.group(1)
        target_ts = float(ts_str) / 1000.0 if len(ts_str) >= 13 and '.' not in ts_str else float(ts_str)
        msg_body = text.replace(match_unix.group(0), "").strip() or "Cloud Trigger Event"
    else:
        match_time = re.search(r"time\s*:\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(am|pm)?", text, re.IGNORECASE)
        if match_time:
            hours, minutes = int(match_time.group(1)), int(match_time.group(2))
            seconds = int(match_time.group(3)) if match_time.group(3) else 0
            am_pm = match_time.group(4).lower() if match_time.group(4) else None
            if am_pm == 'pm' and hours != 12: hours += 12
            elif am_pm == 'am' and hours == 12: hours = 0
            
            now_ist = datetime.now(timezone.utc) + IST_OFFSET
            target_dt_ist = now_ist.replace(hour=hours, minute=minutes, second=seconds, microsecond=0)
            if target_dt_ist < now_ist: target_dt_ist += timedelta(days=1)
            target_ts = (target_dt_ist - IST_OFFSET).timestamp()

    match_target = re.search(r"(?:target|target_id)\s*:\s*([^\s\n]+)", text, re.IGNORECASE)
    if match_target:
        try: target_chat = int(match_target.group(1).strip())
        except ValueError: target_chat = match_target.group(1).strip()
        
    return msg_body, target_ts, target_chat

async def measure_live_rtt():
    latencies = []
    for _ in range(3):
        try:
            start = perf_counter()
            await client(PingRequest(ping_id=random.randint(1, 100000)))
            latencies.append((perf_counter() - start) * 1000.0)
        except Exception:
            pass
    if latencies:
        return sum(latencies) / len(latencies)
    return 10.0  

async def schedule_cloud_delivery(target_ts, chat_id, message_text):
    global CURRENT_SNIPER_TASK
    try:
        target_dt_utc = datetime.fromtimestamp(target_ts, timezone.utc)
        target_dt_ist = target_dt_utc + IST_OFFSET
        
        logger.info(f"🎯 Scheduled Cloud Delivery for: {target_dt_ist.strftime('%Y-%m-%d %H:%M:%S.%f')} (IST)")
        
        target_entity = await client.get_input_entity(chat_id)
        raw_request = SendMessageRequest(
            peer=target_entity,
            message=message_text,
            random_id=random.randint(-9223372036854775808, 9223372036854775807),
            no_webpage=True
        )

        rtt_calculated = False
        dynamic_offset_seconds = 0.002  
        
        while True:
            current_time = datetime.now(timezone.utc)
            time_left = (target_dt_utc - current_time).total_seconds()

            if time_left <= 0:
                break

            if time_left <= 5.0 and not rtt_calculated:
                logger.info("📡 Radar Active: Measuring live Telegram DC latency...")
                avg_rtt = await measure_live_rtt()
                one_way_delay = avg_rtt / 2.0
                dynamic_offset_seconds = max(0.0005, (one_way_delay - 1.5) / 1000.0)
                
                logger.info(f"📊 Live RTT: {avg_rtt:.2f}ms | One-Way Transit: {one_way_delay:.2f}ms")
                logger.info(f"⚙️ V8 Adaptive Offset Locked: {dynamic_offset_seconds * 1000.0:.3f} ms")
                rtt_calculated = True

            if time_left > 0.004:
                await asyncio.sleep(0.001)
                continue
            
            gc.disable()
            trigger_target_ts = target_dt_utc.timestamp() - dynamic_offset_seconds
            
            while datetime.now(timezone.utc).timestamp() < trigger_target_ts:
                pass
            
            trigger_time = datetime.now(timezone.utc)
            await client(raw_request)
            ack_time = datetime.now(timezone.utc)
            
            gc.enable()

            delta_ms = (ack_time.timestamp() - target_dt_utc.timestamp()) * 1000.0
            logger.info("========== V8 CLOUD EXECUTION REPORT ==========")
            logger.info(f"Local Cloud Trigger:    {(trigger_time + IST_OFFSET).strftime('%Y-%m-%d %H:%M:%S.%f')}")
            logger.info(f"Server Acknowledgment:  {(ack_time + IST_OFFSET).strftime('%Y-%m-%d %H:%M:%S.%f')}")
            logger.info(f"Final Landing Delta:    {delta_ms:+.3f} ms")
            logger.info("============================================")
            break

    except asyncio.CancelledError:
        gc.enable()
        logger.info("🛑 Sniper mission was officially aborted by the user.")
    except Exception as e:
        gc.enable()
        logger.error(f"Execution System Failure: {e}")
    finally:
        CURRENT_SNIPER_TASK = None

@client.on(events.NewMessage(outgoing=True))
async def message_handler(event):
    global CURRENT_SNIPER_TASK
    text = event.raw_text.strip().lower()
    
    # V8.1: The Kill Switch (Cancel Command)
    if text == "cancel":
        if CURRENT_SNIPER_TASK and not CURRENT_SNIPER_TASK.done():
            CURRENT_SNIPER_TASK.cancel()
            CURRENT_SNIPER_TASK = None
            await event.reply("🛑 **Mission Aborted!** The sniper has been stood down.\nReady for new coordinates.")
        else:
            await event.reply("⚠️ No active sniper mission to cancel.")
        return

    msg_body, target_ts, target_chat = parse_payload(event.raw_text)
    
    if not target_ts or not msg_body: 
        return
        
    if CURRENT_SNIPER_TASK and not CURRENT_SNIPER_TASK.done():
        logger.warning("⚠️ Execution Collision Blocked! A sniper task is already tracking a target.")
        await event.reply("❌ **Operation Blocked:** Engine is currently tracking another target.\n\n⚠️ Type `cancel` to abort the current mission before setting a new one.")
        return

    target_dt_ist = datetime.fromtimestamp(target_ts, timezone.utc) + IST_OFFSET
    time_str = target_dt_ist.strftime('%Y-%m-%d %I:%M:%S %p')
    
    logger.info(f"🚀 Master V8 Lock Established! Target: {target_chat} | Time: {time_str}")
    CURRENT_SNIPER_TASK = loop.create_task(schedule_cloud_delivery(target_ts, target_chat, msg_body))
    
    try:
        reply_msg = (
            f"⚡ **V8 God-Mode Engine Engaged!**\n\n"
            f"🎯 **Target ID:** `{target_chat}`\n"
            f"⏰ **Time Slot:** `{time_str}` (IST)\n"
            f"🛡️ **System:** Radar Calibration active.\n"
            f"*(Type `cancel` to abort)*"
        )
        await event.reply(reply_msg)
    except Exception as e:
        logger.error(f"Failed to transmit confirmation payload: {e}")
        
async def dummy_web_handler(request):
    return web.Response(text="Cloud Precision Bot V8.1 (Adaptive Core) is Online.")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', dummy_web_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Web server safely bound to port {port}")

async def main():
    await client.start()
    global SOURCE_CHAT_ID_RESOLVED
    try:
        entity = await client.get_input_entity(SOURCE_CHAT_ID)
        SOURCE_CHAT_ID_RESOLVED = utils.get_peer_id(entity)
    except Exception:
        SOURCE_CHAT_ID_RESOLVED = int(SOURCE_CHAT_ID) if isinstance(SOURCE_CHAT_ID, int) else SOURCE_CHAT_ID
            
    logger.info(f"Cloud Precision V8 Core Active on: {SOURCE_CHAT_ID_RESOLVED}")
    await start_web_server()
    await client.run_until_disconnected()

if __name__ == '__main__':
    loop.run_until_complete(main())
