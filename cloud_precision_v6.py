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
    format='%(asctime)s - CloudPrecisionV8.5 - %(levelname)s - %(message)s'
)
logger = logging.getLogger("CloudPrecisionV8.5_IST")

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

CURRENT_SNIPER_TASK = None
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

async def tune_network_socket():
    """Hardware Bypass: OS Buffer Kill-Switch"""
    try:
        transport = client._sender._connection._writer.transport
        sock = transport.get_extra_info('socket')
        if sock is not None:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_TOS, 0x10) 
            logger.info("🔌 Hardware Tuned: Zero-Buffer Routing Engaged!")
    except Exception as e:
        logger.warning(f"Socket tuning bypassed: {e}")

async def get_loop_lag():
    start = perf_counter()
    await asyncio.sleep(0)
    return (perf_counter() - start) * 1000.0

async def measure_live_rtt():
    latencies = []
    await tune_network_socket()
    
    for _ in range(4):
        try:
            start = perf_counter()
            await client._sender.send(PingRequest(ping_id=random.randint(1, 100000)))
            latencies.append((perf_counter() - start) * 1000.0)
        except Exception:
            pass
    
    if latencies:
        avg_rtt = sum(latencies) / len(latencies)
        min_rtt = min(latencies)
        max_rtt = max(latencies)
        jitter = max_rtt - min_rtt
        return avg_rtt, min_rtt, max_rtt, jitter
    return 10.0, 10.0, 10.0, 0.0

async def schedule_cloud_delivery(target_ts, chat_id, message_text):
    global CURRENT_SNIPER_TASK
    try:
        t_setup_start = perf_counter()
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
        
        setup_ms = (perf_counter() - t_setup_start) * 1000.0

        rtt_calculated = False
        dynamic_offset_seconds = 0.050  
        radar_stats = (0, 0, 0, 0)
        os_choke_penalty = 0.0
        
        while True:
            current_time = datetime.now(timezone.utc)
            time_left = (target_dt_utc - current_time).total_seconds()

            if time_left <= 0:
                break

            if time_left <= 5.0 and not rtt_calculated:
                logger.info("📡 V8.5 CPU-Aware Radar Active...")
                avg_rtt, min_rtt, max_rtt, jitter = await measure_live_rtt()
                radar_stats = (avg_rtt, min_rtt, max_rtt, jitter)
                
                one_way_delay = avg_rtt / 2.0
                
                # ========================================================
                # V8.5 THE PERFECT MATH (OS Load Compensator)
                # ========================================================
                sys_load = os.getloadavg() if hasattr(os, 'getloadavg') else (1.0, 1.0, 1.0)
                current_1m_load = sys_load[0]
                
                # Equation: Calculate MS penalty based on CPU queue length.
                # Every 1 point above 1.0 adds 25ms of early fire penalty.
                # Maximum allowed penalty is 120ms to prevent premature execution.
                raw_penalty = (current_1m_load - 1.0) * 25.0
                os_choke_penalty = max(0.0, min(raw_penalty, 120.0))
                
                if str(chat_id).startswith('-100'):
                    # Supergroup: Network + OS Penalty + 15ms Group Queue Padding
                    dynamic_offset_seconds = (one_way_delay + os_choke_penalty + 15.0) / 1000.0  
                else:
                    # Private Chat: Network + OS Penalty + 2ms Safe Zone
                    dynamic_offset_seconds = (one_way_delay + os_choke_penalty + 2.0) / 1000.0 
                
                logger.info(f"📊 RTT: {avg_rtt:.2f}ms | Render CPU Load: {current_1m_load:.2f}")
                logger.info(f"🧮 OS Choke Penalty Calculated: +{os_choke_penalty:.1f}ms")
                logger.info(f"⚙️ V8.5 Dynamic Pre-Fire Locked: {dynamic_offset_seconds * 1000.0:.3f} ms")
                rtt_calculated = True

            # Standard yielding
            if time_left > 0.005:
                await asyncio.sleep(0.001)
                continue
            
            loop_lag_ms = await get_loop_lag()
            
            gc.disable()
            trigger_target_ts = target_dt_utc.timestamp() - dynamic_offset_seconds
            
            # Spinlock Zero-Yield
            t_spin_start = perf_counter()
            while datetime.now(timezone.utc).timestamp() < trigger_target_ts:
                pass
            spin_time_ms = (perf_counter() - t_spin_start) * 1000.0
            
            # BARE-METAL DISPATCH
            trigger_time = datetime.now(timezone.utc)
            t_dispatch_start = perf_counter()
            
            await client._sender.send(raw_request)
            
            dispatch_to_ack_ms = (perf_counter() - t_dispatch_start) * 1000.0
            ack_time = datetime.now(timezone.utc)
            gc.enable()

            delta_ms = (ack_time.timestamp() - target_dt_utc.timestamp()) * 1000.0
            sys_load_final = os.getloadavg() if hasattr(os, 'getloadavg') else ("N/A", "N/A", "N/A")
            
            logger.info("========== V8.5 AI EXECUTION REPORT ==========")
            logger.info(f"[TIMING] Local Trigger:   {(trigger_time + IST_OFFSET).strftime('%H:%M:%S.%f')}")
            logger.info(f"[TIMING] Server Ack:      {(ack_time + IST_OFFSET).strftime('%H:%M:%S.%f')}")
            logger.info(f"[TIMING] Landing Delta:   {delta_ms:+.3f} ms")
            logger.info("-------------------------------------------------------")
            logger.info(f"[MATH] OS Penalty Applied: +{os_choke_penalty:.1f}ms | Loop Lag: {loop_lag_ms:.3f}ms")
            logger.info(f"[MATH] Final CPU Load: {sys_load_final}")
            logger.info(f"[DIAG] Spinlock Held: {spin_time_ms:.1f}ms | Raw Dispatch: {dispatch_to_ack_ms:.1f}ms")
            logger.info(f"[DIAG] Net Jitter: {radar_stats[3]:.2f}ms | Base RTT: {radar_stats[0]:.2f}ms")
            logger.info("==============================================")
            break

    except asyncio.CancelledError:
        gc.enable()
        logger.info("🛑 Sniper mission aborted by user.")
    except Exception as e:
        gc.enable()
        logger.error(f"Execution System Failure: {e}")
    finally:
        CURRENT_SNIPER_TASK = None

@client.on(events.NewMessage(outgoing=True))
async def message_handler(event):
    global CURRENT_SNIPER_TASK
    text = event.raw_text.strip().lower()
    
    if text == "cancel":
        if CURRENT_SNIPER_TASK and not CURRENT_SNIPER_TASK.done():
            CURRENT_SNIPER_TASK.cancel()
            CURRENT_SNIPER_TASK = None
            await event.reply("🛑 **Mission Aborted!**")
        else:
            await event.reply("⚠️ No active mission.")
        return

    msg_body, target_ts, target_chat = parse_payload(event.raw_text)
    
    if not target_ts or not msg_body: 
        return
        
    if CURRENT_SNIPER_TASK and not CURRENT_SNIPER_TASK.done():
        await event.reply("❌ **Operation Blocked:** Engine tracking another target. Type `cancel` first.")
        return

    target_dt_ist = datetime.fromtimestamp(target_ts, timezone.utc) + IST_OFFSET
    time_str = target_dt_ist.strftime('%Y-%m-%d %I:%M:%S %p')
    
    logger.info(f"🚀 V8.5 Lock: {target_chat} | {time_str}")
    CURRENT_SNIPER_TASK = loop.create_task(schedule_cloud_delivery(target_ts, target_chat, msg_body))
    
    try:
        reply_msg = (
            f"⚡ **V8.5 CPU-Aware AI Engaged!**\n\n"
            f"🎯 **Target ID:** `{target_chat}`\n"
            f"⏰ **Time Slot:** `{time_str}` (IST)\n"
            f"🧮 **System:** Extreme Math & OS Compensator active.\n"
            f"*(Type `cancel` to abort)*"
        )
        await event.reply(reply_msg)
    except Exception as e:
        pass
        
async def dummy_web_handler(request):
    return web.Response(text="Cloud Precision Bot V8.5 (CPU-Aware) is Online.")

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
            
    logger.info(f"Cloud Precision V8.5 Core Active on: {SOURCE_CHAT_ID_RESOLVED}")
    await start_web_server()
    await client.run_until_disconnected()

if __name__ == '__main__':
    loop.run_until_complete(main())

