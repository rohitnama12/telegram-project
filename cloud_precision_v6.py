import os
import re
import time
import asyncio
import logging
import gc
from datetime import datetime, timedelta, timezone
from telethon import TelegramClient, events, utils
from telethon.sessions import StringSession
from aiohttp import web

# --- Setup Structured Logging ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger("CloudPrecisionV6_IST")

# --- STRICT IST TIMEZONE LOCK ---
IST = timezone(timedelta(hours=5, minutes=30))

# --- Cloud Environment Variables ---
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

# --- THE GOLDEN CLOUD OFFSET (Hardcoded to prevent Env Var errors) ---
SERVER_PROCESSING_OVERHEAD_MS = 15.0
SERVER_PROCESSING_OVERHEAD = SERVER_PROCESSING_OVERHEAD_MS / 1000.0

# --- FIX: Manually create Event Loop ---
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
            
            # Lock calculations exclusively to IST
            now = datetime.now(IST)
            target_dt = now.replace(hour=hours, minute=minutes, second=seconds, microsecond=0)
            if target_dt.timestamp() < now.timestamp(): target_dt += timedelta(days=1)
            target_ts = target_dt.timestamp()

    match_target = re.search(r"target\s*:\s*([^\s\n]+)", text, re.IGNORECASE)
    if match_target:
        try: target_chat = int(match_target.group(1).strip())
        except ValueError: target_chat = match_target.group(1).strip()
        
    return msg_body, target_ts, target_chat

async def schedule_cloud_reply(client: TelegramClient, target_chat, msg_body: str, target_timestamp: float):
    perf_counter = time.perf_counter
    time_func = time.time
    
    try:
        time_until_target = target_timestamp - time_func()
        if time_until_target <= 0:
            logger.error("Target time is in the past! Aborting.")
            return

        # Show logs in IST to avoid confusion
        logger.info(f"Scheduled Cloud Delivery for: {datetime.fromtimestamp(target_timestamp, IST).strftime('%Y-%m-%d %H:%M:%S.%f')} (IST)")
        logger.info(f"Target Chat: {target_chat} | Offset: {SERVER_PROCESSING_OVERHEAD_MS} ms")
        
        execution_time_sys = target_timestamp - SERVER_PROCESSING_OVERHEAD
        
        t_minus_100ms_delay = (execution_time_sys - time_func()) - 0.100
        if t_minus_100ms_delay > 0:
            await asyncio.sleep(t_minus_100ms_delay)
            
        perf_target = perf_counter() + (execution_time_sys - time_func())
        
        logger.info("Entering Cloud Bare-Metal Spinlock...")
        gc.disable()
        try:
            while perf_counter() < perf_target: pass
        finally:
            gc.enable()
            
        t_trigger_sys = time_func()
        await client.send_message(target_chat, msg_body)
        t_ack_sys = time_func()
        
        arrival_delta_ms = (t_ack_sys - target_timestamp) * 1000
        logger.info("========== CLOUD EXECUTION REPORT ==========")
        logger.info(f"Local Cloud Trigger:    {datetime.fromtimestamp(t_trigger_sys, IST).strftime('%Y-%m-%d %H:%M:%S.%f')}")
        logger.info(f"Server Acknowledgment:  {datetime.fromtimestamp(t_ack_sys, IST).strftime('%Y-%m-%d %H:%M:%S.%f')}")
        logger.info(f"Final Landing Delta:    {arrival_delta_ms:+.3f} ms")
        logger.info("============================================")

    except Exception as e:
        logger.error(f"Cloud Execution Error: {e}")

@client.on(events.NewMessage)
async def message_handler(event):
    if SOURCE_CHAT_ID_RESOLVED and event.chat_id != SOURCE_CHAT_ID_RESOLVED: return
    msg_body, target_ts, target_chat = parse_payload(event.raw_text)
    if not target_ts or not msg_body: return
    logger.info("Instruction received.")
    loop.create_task(schedule_cloud_reply(client, target_chat, msg_body, target_ts))

async def health_check(request):
    return web.Response(text="Cloud Precision Bot is Online and Running.")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"Web server started on port {port}")

async def main():
    await client.start()
    global SOURCE_CHAT_ID_RESOLVED
    try:
        entity = await client.get_input_entity(SOURCE_CHAT_ID)
        SOURCE_CHAT_ID_RESOLVED = utils.get_peer_id(entity)
    except Exception:
        SOURCE_CHAT_ID_RESOLVED = int(SOURCE_CHAT_ID) if isinstance(SOURCE_CHAT_ID, int) else SOURCE_CHAT_ID
            
    logger.info(f"Cloud Precision V6 [IST LOCKED] listening on: {SOURCE_CHAT_ID_RESOLVED}")
    
    await start_web_server()
    await client.run_until_disconnected()

if __name__ == '__main__':
    loop.run_until_complete(main())
