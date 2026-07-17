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



# import os
# import re
# import asyncio
# import logging
# import gc
# import random
# import socket
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
#     format='%(asctime)s - CloudPrecisionV8.7 - %(levelname)s - %(message)s'
# )
# logger = logging.getLogger("CloudPrecisionV8.7_IST")

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

# CURRENT_SNIPER_TASK = None
# IST_OFFSET = timedelta(hours=5, minutes=30)

# loop = asyncio.new_event_loop()
# asyncio.set_event_loop(loop)
# client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH, loop=loop)

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
            
#             now_ist = datetime.now(timezone.utc) + IST_OFFSET
#             target_dt_ist = now_ist.replace(hour=hours, minute=minutes, second=seconds, microsecond=0)
#             if target_dt_ist < now_ist: target_dt_ist += timedelta(days=1)
#             target_ts = (target_dt_ist - IST_OFFSET).timestamp()

#     match_target = re.search(r"(?:target|target_id)\s*:\s*([^\s\n]+)", text, re.IGNORECASE)
#     if match_target:
#         try: target_chat = int(match_target.group(1).strip())
#         except ValueError: target_chat = match_target.group(1).strip()
        
#     return msg_body, target_ts, target_chat

# async def tune_network_socket():
#     try:
#         transport = client._sender._connection._writer.transport
#         sock = transport.get_extra_info('socket')
#         if sock is not None:
#             sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
#             sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 0x10) 
#     except Exception:
#         pass

# async def get_loop_lag():
#     start = perf_counter()
#     await asyncio.sleep(0)
#     return (perf_counter() - start) * 1000.0

# async def measure_live_rtt():
#     latencies = []
#     await tune_network_socket()
#     for _ in range(4):
#         try:
#             start = perf_counter()
#             await client._sender.send(PingRequest(ping_id=random.randint(1, 100000)))
#             latencies.append((perf_counter() - start) * 1000.0)
#         except Exception: pass
#     if latencies:
#         return sum(latencies) / len(latencies), min(latencies), max(latencies), max(latencies) - min(latencies)
#     return 10.0, 10.0, 10.0, 0.0

# async def schedule_cloud_delivery(target_ts, chat_id, message_text):
#     global CURRENT_SNIPER_TASK
#     try:
#         target_dt_utc = datetime.fromtimestamp(target_ts, timezone.utc)
#         target_dt_ist = target_dt_utc + IST_OFFSET
#         logger.info(f"🎯 Target Locked: {target_dt_ist.strftime('%Y-%m-%d %H:%M:%S.%f')} (IST)")
        
#         target_entity = await client.get_input_entity(chat_id)
#         raw_request = SendMessageRequest(
#             peer=target_entity, message=message_text,
#             random_id=random.randint(-9223372036854775808, 9223372036854775807), no_webpage=True
#         )

#         rtt_calculated = False
#         dynamic_offset_seconds = 0.005  
        
#         while True:
#             current_time = datetime.now(timezone.utc)
#             time_left = (target_dt_utc - current_time).total_seconds()

#             if time_left <= 0: break

#             if time_left <= 5.0 and not rtt_calculated:
#                 avg_rtt, min_rtt, max_rtt, jitter = await measure_live_rtt()
#                 one_way_delay = avg_rtt / 2.0
                
#                 # V8.7 REALITY MATH (No Magic Numbers)
#                 sys_load = os.getloadavg() if hasattr(os, 'getloadavg') else (1.0, 1.0, 1.0)
#                 current_1m_load = sys_load[0]
                
#                 # Very gentle OS penalty to avoid early hitting
#                 os_choke_penalty = max(0.0, (current_1m_load - 3.5) * 1.5)
                
#                 if str(chat_id).startswith('-100'):
#                     dynamic_offset_seconds = (one_way_delay + os_choke_penalty + 1.0) / 1000.0  
#                 else:
#                     dynamic_offset_seconds = (one_way_delay + os_choke_penalty) / 1000.0 
                
#                 logger.info(f"📊 Live RTT: {avg_rtt:.2f}ms | Render CPU Load: {current_1m_load:.2f}")
#                 logger.info(f"⚙️ V8.7 True-Offset Locked: {dynamic_offset_seconds * 1000.0:.3f} ms")
#                 rtt_calculated = True

#             if time_left > (dynamic_offset_seconds + 0.002):
#                 await asyncio.sleep(0.001)
#                 continue
            
#             gc.disable()
#             trigger_target_ts = target_dt_utc.timestamp() - dynamic_offset_seconds
            
#             while datetime.now(timezone.utc).timestamp() < trigger_target_ts: pass
            
#             trigger_time = datetime.now(timezone.utc)
#             t_dispatch_start = perf_counter()
#             await client._sender.send(raw_request)
#             dispatch_to_ack_ms = (perf_counter() - t_dispatch_start) * 1000.0
#             ack_time = datetime.now(timezone.utc)
#             gc.enable()

#             # V8.7 THE TRUE STAMP CALCULATION
#             true_hit_time = ack_time - timedelta(milliseconds=(dispatch_to_ack_ms / 2.0))
#             true_delta_ms = (true_hit_time.timestamp() - target_dt_utc.timestamp()) * 1000.0
            
#             logger.info("========== V8.7 TRUE-STAMP EXECUTION REPORT ==========")
#             logger.info(f"[TIMING] Local Trigger:   {(trigger_time + IST_OFFSET).strftime('%H:%M:%S.%f')}")
#             logger.info(f"[TIMING] TRUE TG HIT:     {(true_hit_time + IST_OFFSET).strftime('%H:%M:%S.%f')} 🎯")
#             logger.info(f"[TIMING] True Delta:      {true_delta_ms:+.3f} ms")
#             logger.info("------------------------------------------------------")
#             logger.info(f"[DIAG] Raw Dispatch: {dispatch_to_ack_ms:.1f}ms | Base RTT: {avg_rtt:.2f}ms")
#             logger.info("======================================================")
#             break

#     except asyncio.CancelledError:
#         gc.enable()
#         logger.info("🛑 Sniper mission aborted by user.")
#     except Exception as e:
#         gc.enable()
#         logger.error(f"Execution System Failure: {e}")
#     finally:
#         CURRENT_SNIPER_TASK = None

# @client.on(events.NewMessage(outgoing=True))
# async def message_handler(event):
#     global CURRENT_SNIPER_TASK
#     text = event.raw_text.strip().lower()
#     if text == "cancel":
#         if CURRENT_SNIPER_TASK and not CURRENT_SNIPER_TASK.done():
#             CURRENT_SNIPER_TASK.cancel()
#             CURRENT_SNIPER_TASK = None
#             await event.reply("🛑 **Mission Aborted!**")
#         else: await event.reply("⚠️ No active mission.")
#         return

#     msg_body, target_ts, target_chat = parse_payload(event.raw_text)
#     if not target_ts or not msg_body: return
        
#     if CURRENT_SNIPER_TASK and not CURRENT_SNIPER_TASK.done():
#         await event.reply("❌ **Operation Blocked:** Engine tracking another target. Type `cancel` first.")
#         return

#     target_dt_ist = datetime.fromtimestamp(target_ts, timezone.utc) + IST_OFFSET
#     time_str = target_dt_ist.strftime('%Y-%m-%d %I:%M:%S %p')
    
#     logger.info(f"🚀 V8.7 Lock: {target_chat} | {time_str}")
#     CURRENT_SNIPER_TASK = loop.create_task(schedule_cloud_delivery(target_ts, target_chat, msg_body))
    
#     try:
#         reply_msg = (
#             f"⚡ **V8.7 True-Stamp Engine Engaged!**\n\n"
#             f"🎯 **Target ID:** `{target_chat}`\n"
#             f"⏰ **Time Slot:** `{time_str}` (IST)\n"
#             f"🧮 **System:** Anti-Negative Delta Active.\n*(Type `cancel` to abort)*"
#         )
#         await event.reply(reply_msg)
#     except Exception: pass
        
# async def dummy_web_handler(request): return web.Response(text="Cloud Precision Bot V8.7 is Online.")

# async def start_web_server():
#     app = web.Application()
#     app.router.add_get('/', dummy_web_handler)
#     runner = web.AppRunner(app)
#     await runner.setup()
#     port = int(os.environ.get("PORT", 10000))
#     site = web.TCPSite(runner, '0.0.0.0', port)
#     await site.start()

# async def main():
#     await client.start()
#     await start_web_server()
#     await client.run_until_disconnected()

# if __name__ == '__main__':
#     loop.run_until_complete(main())









#-------------------------------------------------------------------------------------------------------------------------------




import os
import re
import asyncio
import logging
import gc
import random
import socket
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
    format='%(asctime)s - CloudPrecisionV9.1 - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CloudPrecisionV9.1_IST")

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

# ================= STATE MANAGEMENT =================
CURRENT_MODE = None  

# Single Mode State
CURRENT_SNIPER_TASK = None

# Multiple Mode State
ACTIVE_PAYLOADS = []  
QUEUE_REGISTRY = {}   
MASTER_BATCH_TASKS = {}

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

def rebuild_queue_registry():
    global QUEUE_REGISTRY, ACTIVE_PAYLOADS
    QUEUE_REGISTRY.clear()
    for p in ACTIVE_PAYLOADS:
        if p['ts'] not in QUEUE_REGISTRY:
            QUEUE_REGISTRY[p['ts']] = []
        QUEUE_REGISTRY[p['ts']].append(p)

def reset_all_systems(new_mode=None):
    global CURRENT_MODE, CURRENT_SNIPER_TASK, ACTIVE_PAYLOADS, QUEUE_REGISTRY, MASTER_BATCH_TASKS
    
    if CURRENT_SNIPER_TASK and not CURRENT_SNIPER_TASK.done():
        CURRENT_SNIPER_TASK.cancel()
    CURRENT_SNIPER_TASK = None
    
    for ts, task in list(MASTER_BATCH_TASKS.items()):
        if not task.done():
            task.cancel()
            
    ACTIVE_PAYLOADS.clear()
    QUEUE_REGISTRY.clear()
    MASTER_BATCH_TASKS.clear()
    CURRENT_MODE = new_mode

async def tune_network_socket():
    try:
        transport = client._sender._connection._writer.transport
        sock = transport.get_extra_info('socket')
        if sock is not None:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 0x10) 
    except Exception: pass

async def measure_live_rtt():
    latencies = []
    await tune_network_socket()
    for _ in range(4):
        try:
            start = perf_counter()
            await client._sender.send(PingRequest(ping_id=random.randint(1, 100000)))
            latencies.append((perf_counter() - start) * 1000.0)
        except Exception: pass
    if latencies:
        return sum(latencies) / len(latencies), min(latencies), max(latencies), max(latencies) - min(latencies)
    return 10.0, 10.0, 10.0, 0.0

# ================= V9.1 SINGLE SHOT ENGINE =================
async def schedule_single_delivery(target_ts, chat_id, message_text):
    global CURRENT_SNIPER_TASK
    try:
        target_dt_utc = datetime.fromtimestamp(target_ts, timezone.utc)
        target_dt_ist = target_dt_utc + IST_OFFSET
        logger.info(f"🎯 [SINGLE MODE] Target Locked: {target_dt_ist.strftime('%Y-%m-%d %H:%M:%S.%f')} (IST)")
        
        target_entity = await client.get_input_entity(chat_id)
        raw_request = SendMessageRequest(
            peer=target_entity, message=message_text,
            random_id=random.randint(-9223372036854775808, 9223372036854775807), no_webpage=True
        )

        rtt_calculated = False
        pre_flight_done = False
        dynamic_offset_seconds = 0.005  
        
        while True:
            current_time = datetime.now(timezone.utc)
            time_left = (target_dt_utc - current_time).total_seconds()

            if time_left <= 0: break

            # V9.1 UPGRADE: Pre-Flight Socket Wakeup
            if time_left <= 15.0 and not pre_flight_done:
                try:
                    await client._sender.send(PingRequest(ping_id=random.randint(1, 100000)))
                    logger.info("🔌 Pre-Flight TCP Socket Wakeup Ping Sent.")
                except Exception: pass
                pre_flight_done = True

            if time_left <= 5.0 and not rtt_calculated:
                avg_rtt, min_rtt, max_rtt, jitter = await measure_live_rtt()
                one_way_delay = avg_rtt / 2.0
                
                sys_load = os.getloadavg() if hasattr(os, 'getloadavg') else (1.0, 1.0, 1.0)
                current_1m_load = sys_load[0]
                
                os_choke_penalty = max(0.0, (current_1m_load - 3.5) * 1.5)
                
                if str(chat_id).startswith('-100'):
                    dynamic_offset_seconds = (one_way_delay + os_choke_penalty + 1.0) / 1000.0  
                else:
                    dynamic_offset_seconds = (one_way_delay + os_choke_penalty) / 1000.0 
                
                logger.info(f"📊 Live RTT: {avg_rtt:.2f}ms | Load: {current_1m_load:.2f} | True-Offset: {dynamic_offset_seconds * 1000.0:.3f} ms")
                rtt_calculated = True

            if time_left > (dynamic_offset_seconds + 0.002):
                await asyncio.sleep(0.001)
                continue
            
            gc.disable()
            
            # V9.1 UPGRADE: Monotonic Hardware Spinlock
            trigger_target_ts = target_dt_utc.timestamp() - dynamic_offset_seconds
            current_ts = datetime.now(timezone.utc).timestamp()
            hardware_wait_time = trigger_target_ts - current_ts
            
            if hardware_wait_time > 0:
                target_hardware_tick = perf_counter() + hardware_wait_time
                while perf_counter() < target_hardware_tick: pass
            
            trigger_time = datetime.now(timezone.utc)
            t_dispatch_start = perf_counter()
            await client._sender.send(raw_request)
            dispatch_to_ack_ms = (perf_counter() - t_dispatch_start) * 1000.0
            ack_time = datetime.now(timezone.utc)
            gc.enable()

            true_hit_time = ack_time - timedelta(milliseconds=(dispatch_to_ack_ms / 2.0))
            true_delta_ms = (true_hit_time.timestamp() - target_dt_utc.timestamp()) * 1000.0
            
            logger.info("========== V9.1 SINGLE-STAMP EXECUTION REPORT ==========")
            logger.info(f"[TIMING] Hardware Trigger: {(trigger_time + IST_OFFSET).strftime('%H:%M:%S.%f')}")
            logger.info(f"[TIMING] TRUE TG HIT:      {(true_hit_time + IST_OFFSET).strftime('%H:%M:%S.%f')} 🎯")
            logger.info(f"[TIMING] True Delta:       {true_delta_ms:+.3f} ms")
            logger.info("--------------------------------------------------------")
            logger.info(f"[DIAG] Raw Dispatch: {dispatch_to_ack_ms:.1f}ms | Clock Type: Monotonic")
            logger.info("========================================================")
            break

    except asyncio.CancelledError:
        gc.enable()
        logger.info("🛑 Single Sniper mission aborted by user.")
    except Exception as e:
        gc.enable()
        logger.error(f"Single Execution System Failure: {e}")
    finally:
        CURRENT_SNIPER_TASK = None

# ================= V9.1 MULTIPLE GATLING ENGINE (GHOST PIPELINE) =================
async def schedule_master_batch(target_ts):
    global QUEUE_REGISTRY, MASTER_BATCH_TASKS, ACTIVE_PAYLOADS
    try:
        target_dt_utc = datetime.fromtimestamp(target_ts, timezone.utc)
        target_dt_ist = target_dt_utc + IST_OFFSET
        
        logger.info(f"💥 [MULTIPLE MODE] Master Batch Lock Engaged for {target_dt_ist.strftime('%H:%M:%S')} (IST)")
        
        rtt_calculated = False
        pre_flight_done = False
        dynamic_offset_seconds = 0.005  
        avg_rtt = 10.0
        
        while True:
            current_time = datetime.now(timezone.utc)
            time_left = (target_dt_utc - current_time).total_seconds()
            
            current_payloads = QUEUE_REGISTRY.get(target_ts, [])

            if time_left <= 0: break

            # V9.1 UPGRADE: Pre-Flight Socket Wakeup
            if time_left <= 15.0 and not pre_flight_done:
                try:
                    await client._sender.send(PingRequest(ping_id=random.randint(1, 100000)))
                    logger.info("🔌 Pre-Flight TCP Socket Wakeup Ping Sent.")
                except Exception: pass
                pre_flight_done = True

            if time_left <= 5.0 and not rtt_calculated:
                avg_rtt, min_rtt, max_rtt, jitter = await measure_live_rtt()
                one_way_delay = avg_rtt / 2.0
                
                sys_load = os.getloadavg() if hasattr(os, 'getloadavg') else (1.0, 1.0, 1.0)
                current_1m_load = sys_load[0]
                
                os_choke_penalty = max(0.0, (current_1m_load - 3.5) * 1.5)
                is_supergroup = any(str(p['chat_id']).startswith('-100') for p in current_payloads)
                padding = 1.0 if is_supergroup else 0.0
                
                dynamic_offset_seconds = (one_way_delay + os_choke_penalty + padding) / 1000.0 
                
                logger.info(f"📡 Batch Radar -> RTT: {avg_rtt:.2f}ms | Load: {current_1m_load:.2f} | Offset: {dynamic_offset_seconds*1000.0:.2f}ms")
                rtt_calculated = True

            if time_left > (dynamic_offset_seconds + 0.002):
                await asyncio.sleep(0.001)
                continue
            
            gc.disable()
            
            # V9.1 UPGRADE: Monotonic Hardware Spinlock
            trigger_target_ts = target_dt_utc.timestamp() - dynamic_offset_seconds
            current_ts = datetime.now(timezone.utc).timestamp()
            hardware_wait_time = trigger_target_ts - current_ts
            
            if hardware_wait_time > 0:
                target_hardware_tick = perf_counter() + hardware_wait_time
                while perf_counter() < target_hardware_tick: pass
            
            trigger_time = datetime.now(timezone.utc)
            t_dispatch_start = perf_counter()
            
            final_payloads = QUEUE_REGISTRY.get(target_ts, [])
            
            # Ghost Pipeline: Push packets directly to socket buffer bypassing ACK lag
            for p in final_payloads:
                loop.create_task(client._sender.send(p['req']))
            
            # Force exact 1 cycle to write to OS Socket Buffer instantly
            await asyncio.sleep(0)
            
            dispatch_to_flush_ms = (perf_counter() - t_dispatch_start) * 1000.0
            gc.enable()

            true_hit_time = trigger_time + timedelta(milliseconds=avg_rtt / 2.0)
            true_delta_ms = (true_hit_time.timestamp() - target_dt_utc.timestamp()) * 1000.0
            
            logger.info(f"========== V9.1 GHOST BATCH EXECUTION REPORT ({len(final_payloads)} Bursts) ==========")
            logger.info(f"[TIMING] Hardware Trigger: {(trigger_time + IST_OFFSET).strftime('%H:%M:%S.%f')}")
            logger.info(f"[TIMING] Est. TG HIT:      {(true_hit_time + IST_OFFSET).strftime('%H:%M:%S.%f')} 🎯")
            logger.info(f"[TIMING] Est. Delta:       {true_delta_ms:+.3f} ms")
            logger.info(f"[DIAG] OS Socket Flush:    {dispatch_to_flush_ms:.2f}ms | Clock Type: Monotonic")
            logger.info("==========================================================================")
            break

    except asyncio.CancelledError:
        gc.enable()
        logger.info(f"🛑 Batch task for {target_ts} was aborted.")
    except Exception as e:
        gc.enable()
        logger.error(f"Gatling Engine Failure: {e}")
    finally:
        if target_ts in QUEUE_REGISTRY: del QUEUE_REGISTRY[target_ts]
        if target_ts in MASTER_BATCH_TASKS: del MASTER_BATCH_TASKS[target_ts]
        ACTIVE_PAYLOADS = [p for p in ACTIVE_PAYLOADS if p['ts'] != target_ts]

# ================= COMMAND HANDLER (MODE AI) =================
@client.on(events.NewMessage(outgoing=True))
async def message_handler(event):
    global CURRENT_MODE, CURRENT_SNIPER_TASK, ACTIVE_PAYLOADS
    text = event.raw_text.strip().lower()
    
    if text == "single":
        reset_all_systems("single")
        await event.reply("✅ **SINGLE SHOT MODE ACTIVATED**\n*V9.1 Monotonic Precision Engine is ready.*")
        return
        
    if text == "multiple":
        reset_all_systems("multiple")
        await event.reply("✅ **MULTIPLE BATCH MODE ACTIVATED**\n*V9.1 Monotonic Ghost Pipeline is ready.*")
        return
        
    if text == "cancel":
        reset_all_systems(None)
        await event.reply("🛑 **SYSTEM CANCELLED & RESET**\n*Please type `single` or `multiple` to choose a mode again.*")
        return

    batch_cancel_match = re.match(r"cancel batch\s*(\d+)", text)
    if batch_cancel_match:
        if CURRENT_MODE != "multiple":
            await event.reply("⚠️ You are not in 'multiple' mode.")
            return
            
        barrel_index = int(batch_cancel_match.group(1)) - 1
        if 0 <= barrel_index < len(ACTIVE_PAYLOADS):
            ACTIVE_PAYLOADS.pop(barrel_index)
            rebuild_queue_registry()
            await event.reply(f"🗑️ **Barrel #{barrel_index + 1} Removed!**\n*Remaining payloads: {len(ACTIVE_PAYLOADS)}*")
        else:
            await event.reply(f"❌ Invalid barrel number. Only {len(ACTIVE_PAYLOADS)} barrels currently loaded.")
        return

    msg_body, target_ts, target_chat = parse_payload(event.raw_text)
    if not target_ts or not msg_body: return
    
    if CURRENT_MODE is None:
        await event.reply("⚠️ **MODE NOT SELECTED**\n*Please type `single` or `multiple` first before sending payloads.*")
        return

    if CURRENT_MODE == "single":
        if CURRENT_SNIPER_TASK and not CURRENT_SNIPER_TASK.done():
            await event.reply("❌ **Operation Blocked:** Single engine already armed. Type `cancel` first.")
            return
            
        target_dt_ist = datetime.fromtimestamp(target_ts, timezone.utc) + IST_OFFSET
        time_str = target_dt_ist.strftime('%I:%M:%S %p')
        
        CURRENT_SNIPER_TASK = loop.create_task(schedule_single_delivery(target_ts, target_chat, msg_body))
        await event.reply(f"⚡ **SINGLE SHOT ARMED!**\n🎯 Target: `{target_chat}`\n⏰ Slot: `{time_str}` (IST)")
        
    elif CURRENT_MODE == "multiple":
        try:
            target_entity = await client.get_input_entity(target_chat)
            raw_request = SendMessageRequest(
                peer=target_entity, message=msg_body,
                random_id=random.randint(-9223372036854775808, 9223372036854775807), no_webpage=True
            )
        except Exception as e:
            await event.reply(f"❌ **Entity Error:** Cannot cache `{target_chat}`. ({e})")
            return
            
        payload_data = {"ts": target_ts, "chat_id": target_chat, "req": raw_request}
        ACTIVE_PAYLOADS.append(payload_data)
        rebuild_queue_registry()
        
        current_count = len(ACTIVE_PAYLOADS)
        target_dt_ist = datetime.fromtimestamp(target_ts, timezone.utc) + IST_OFFSET
        time_str = target_dt_ist.strftime('%I:%M:%S %p')
        
        if target_ts not in MASTER_BATCH_TASKS or MASTER_BATCH_TASKS[target_ts].done():
            MASTER_BATCH_TASKS[target_ts] = loop.create_task(schedule_master_batch(target_ts))
        
        await event.reply(f"🚀 **Barrel #{current_count} Loaded!**\n🎯 Target: `{target_chat}`\n⏰ Slot: `{time_str}` (IST)")

# ================= WEB SERVER & MAIN =================
async def dummy_web_handler(request): 
    return web.Response(text="Cloud Precision V9.1 (Monotonic Engine) Active.")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', dummy_web_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    await client.start()
    
    logger.info("🔥 Warming up Entity Cache from Telegram...")
    try:
        await client.get_dialogs(limit=50)
        logger.info("✅ Entity Cache Warmup Complete!")
    except Exception as e:
        logger.warning(f"Cache warmup failed: {e}")

    global SOURCE_CHAT_ID_RESOLVED
    try:
        entity = await client.get_input_entity(SOURCE_CHAT_ID)
        SOURCE_CHAT_ID_RESOLVED = utils.get_peer_id(entity)
    except Exception:
        SOURCE_CHAT_ID_RESOLVED = int(SOURCE_CHAT_ID) if isinstance(SOURCE_CHAT_ID, int) else SOURCE_CHAT_ID
            
    logger.info(f"Cloud Precision V9.1 Core Active on: {SOURCE_CHAT_ID_RESOLVED}")
    logger.info("Waiting for Mode Selection ('single' or 'multiple')...")
    await start_web_server()
    await client.run_until_disconnected()

if __name__ == '__main__':
    loop.run_until_complete(main())
