import os
import re
import asyncio
import random
import time
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest, StartBotRequest
from telethon.errors import FloodWaitError, UserAlreadyParticipantError

# إعدادات البيئة من جيت هوب
API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION_STRING = os.environ.get("TELEGRAM_SESSION", "")

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# ذاكرة الحظر والتكرار لتجنب إعادة معالجة الروابط أو الأكواد القديمة
processed_items = set()
verification_tracker = {}
channels_activity = {}
SIX_HOURS = 6 * 60 * 60

async def join_channel(channel_link):
    """الانضمام الذكي للقنوات الإجبارية"""
    try:
        if "+" in channel_link or "joinchat" in channel_link:
            invite_hash = channel_link.split("/")[-1].replace("+", "")
            await client(ImportChatInviteRequest(invite_hash))
        else:
            username = channel_link.split("/")[-1]
            await client(JoinChannelRequest(username))
        print(f"[+] تم الانضمام بنجاح: {channel_link}")
        await asyncio.sleep(random.randint(2, 4))
    except UserAlreadyParticipantError:
        pass
    except Exception as e:
        print(f"[-] فشل الانضمام إلى {channel_link}: {e}")

async def process_link_bot(bot_username, start_payload):
    """معالجة روابط التمويل المباشرة محاكية لضغطات البشر"""
    try:
        delay = random.randint(5, 9)
        print(f"[*] رابط تمويل مباشر. جاري الانتظار {delay} ثوانٍ لمحاكاة العنصر البشري...")
        await asyncio.sleep(delay)
        
        # الضغط الرسمي على الرابط
        await client(StartBotRequest(bot=bot_username, peer=bot_username, start_param=start_payload))
        print(f"[+] تم تفعيل رابط البوت بنجاح: {bot_username}")
    except FloodWaitError as e:
        print(f"[!] تفادي الحظر: يجب الانتظار {e.seconds} ثانية.")
        await asyncio.sleep(e.seconds)
    except Exception as e:
        print(f"[-] خطأ في معالجة رابط البوت {bot_username}: {e}")

async def process_code_bot(bot_username, extracted_code):
    """فتح محادثة تفاعلية خطوة بخطوة مع بوتات الأكواد مثل طلباتي"""
    try:
        print(f"[*] بدء تدفق تفاعلي مع بوت الأكواد (@{bot_username}) للكود: {extracted_code}")
        
        # فتح محادثة (Conversation) مخصصة تنتظر ردود البوت بدقة
        async with client.conversation(bot_username, timeout=20) as conv:
            # 1. إرسال ستارت للبوت
            await conv.send_message("/start")
            
            # 2. الانتظار حتى يستجيب البوت ويرسل القائمة التي تحتوي الأزرار
            bot_reply = await conv.get_response()
            
            target_button = None
            if bot_reply.buttons:
                for row in bot_reply.buttons:
                    for button in row:
                        if "استخدام" in button.text or "كود" in button.text:
                            target_button = button
                            break
            
            if target_button:
                # محاكاة التفكير البشري قبل الضغط
                await asyncio.sleep(random.randint(2, 3))
                await target_button.click()
                print(f"[+] تم الضغط على زر '{target_button.text}'. ننتظر طلب البوت للكود...")
                
                # 3. الانتظار حتى يطلب البوت الكود (الاستجابة التالية)
                await conv.get_response()
                
                # 4. إرسال الكود فوراً وبسرعة لنكون أول المستفيدين
                await asyncio.sleep(1)
                await conv.send_message(extracted_code)
                print(f"[🎉] تم تسليم الكود بنجاح لبوت {bot_username}!")
            else:
                print(f"[-] لم يتم العثور على زر استخدام الكود في رد بوت {bot_username}.")
                
    except asyncio.TimeoutError:
        print(f"[-] انتهت مهلة الاستجابة من البوت {bot_username} (البوت بطيء أو معلق).")
    except Exception as e:
        print(f"[-] خطأ أثناء التفاعل مع بوت الأكواد {bot_username}: {e}")

@client.on(events.NewMessage)
async def handle_incoming_content(event):
    chat_id = event.chat_id
    text = event.raw_text or ""
    
    # تجميع كافة الروابط (نصية أو مخفية كـ Hyperlinks)
    urls = []
    if event.entities:
        for entity in event.entities:
            if hasattr(entity, 'url') and entity.url:
                urls.append(entity.url)
    raw_urls = re.findall(r'(https?://t\.me/[^\s]+)', text)
    urls.extend(raw_urls)
    
    # أولاً: التحقق من روابط التمويل المباشرة (?start=)
    for url in urls:
        bot_match = re.search(r"t\.me/([a-zA-Z0-9_]+)\?start=([a-zA-Z0-9_]+)", url)
        if bot_match:
            bot_username = bot_match.group(1)
            start_payload = bot_match.group(2)
            
            if start_payload not in processed_items:
                processed_items.add(start_payload)
                channels_activity[chat_id] = time.time()
                # تشغيل المهمة في الخلفية فوراً لعدم تجميد السكريبت
                asyncio.create_task(process_link_bot(bot_username, start_payload))

    # ثانياً: التحقق من نظام الأكواد (مثل طلباتي / FAABOT)
    if "الكود" in text or "كود" in text:
        code_match = re.search(r"(?:الكود|كود)\s*:\s*([a-zA-Z0-9]+)", text)
        if code_match:
            extracted_code = code_match.group(1)
            
            if extracted_code not in processed_items:
                processed_items.add(extracted_code)
                channels_activity[chat_id] = time.time()
                
                # تخمين المعرف الافتراضي أو استخراجه من النص
                bot_username = "TALABATI_BOT"
                bot_name_match = re.search(r"@([a-zA-Z0-9_]+[bB][oO][tT])", text)
                if bot_name_match:
                    bot_username = bot_name_match.group(1)
                
                # تشغيل المهمة فوراً وبشكل منفصل لسرعة الاستجابة
                asyncio.create_task(process_code_bot(bot_username, extracted_code))

@client.on(events.NewMessage)
async def handle_forced_subscriptions(event):
    """معالجة الاشتراكات الإجبارية للبوتات عند الرد وتأكيد التحقق"""
    if not event.is_private:
        return
        
    sender = await event.get_sender()
    if sender and sender.bot:
        text = event.raw_text or ""
        bot_username = sender.username
        
        if "اشترك" in text or "الاشتراك" in text or "قناة" in text or "غير مشترك" in text:
            attempts = verification_tracker.get(bot_username, 0)
            if attempts > 3:
                return
                
            print(f"[*] البوت {bot_username} يطلب قنوات إجبارية، جاري الاشتراك...")
            
            # الاشتراك من الأزرار أو الروابط النصية
            if event.buttons:
                for row in event.buttons:
                    for button in row:
                        if button.url and "t.me" in button.url:
                            await join_channel(button.url)
            
            urls = re.findall(r'(https?://t\.me/[^\s]+)', text)
            for url in urls:
                if "bot" not in url.lower():
                    await join_channel(url)
            
            # مهلة ضرورية لتزامن البيانات في سيرفرات تيليجرام
            await asyncio.sleep(4)
            
            # الضغط على زر التحقق والتأكيد
            if event.buttons:
                for row in event.buttons:
                    for button in row:
                        if button.text and any(keyword in button.text for keyword in ["تحقق", "Check", "اشتركت", "تأكيد"]):
                            print(f"[*] الضغط على زر التأكيد للبوت {bot_username}")
                            verification_tracker[bot_username] = attempts + 1
                            await button.click()
                            return

async def channel_cleaner():
    """مغادرة القنوات التي لم تنشر عروضاً منذ 6 ساعات"""
    while True:
        await asyncio.sleep(3600)
        current_time = time.time()
        for chat_id, last_time in list(channels_activity.items()):
            if current_time - last_time > SIX_HOURS:
                try:
                    await client(LeaveChannelRequest(chat_id))
                    print(f"[!] تم تنظيف ومغادرة القناة الخاملة: {chat_id}")
                    del channels_activity[chat_id]
                    await asyncio.sleep(5)
                except Exception as e:
                    print(f"[-] خطأ أثناء مغادرة القناة {chat_id}: {e}")

async def main():
    print("[*] تم تفعيل النظام الخالي من الثغرات. جاري العمل...")
    asyncio.create_task(channel_cleaner())
    await client.run_until_disconnected()

if __name__ == '__main__':
    try:
        with client:
            client.loop.run_until_complete(main())
    except Exception as fatal_err:
        print(f"[💥] خطأ في تشغيل السكريبت الرئيسي: {fatal_err}")

