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

# جلب البيانات من بيئة GitHub Secrets
API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION_STRING = os.environ.get("TELEGRAM_SESSION", "")

client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# حل مشكلة التكرار: ذاكرة لتخزين الروابط والأكواد التي تم استخدامها مسبقاً
processed_items = set()

# قاموس لتتبع عدد محاولات الضغط على زر "التحقق" لكل بوت لتجنب الحلقات اللانهائية
verification_tracker = {}
# تتبع نشاط القنوات للمغادرة بعد 6 ساعات
channels_activity = {}
SIX_HOURS = 6 * 60 * 60

async def join_channel(channel_link):
    """دالة الانضمام للقنوات الإجبارية مع معالجة الروابط العامة والخاصة"""
    try:
        if "+" in channel_link or "joinchat" in channel_link:
            invite_hash = channel_link.split("/")[-1].replace("+", "")
            await client(ImportChatInviteRequest(invite_hash))
        else:
            username = channel_link.split("/")[-1]
            await client(JoinChannelRequest(username))
        print(f"[+] تم الانضمام إلى القناة: {channel_link}")
        # انتظار بسيط بين الانضمامات لتجنب الحظر
        await asyncio.sleep(random.randint(2, 4))
    except UserAlreadyParticipantError:
        pass
    except Exception as e:
        print(f"[-] فشل الانضمام إلى {channel_link}: {e}")

@client.on(events.NewMessage)
async def handle_new_messages(event):
    chat_id = event.chat_id
    text = event.raw_text or ""
    
    # استخراج الروابط النصية والمخفية (Hyperlinks) لكي لا يفوتنا أي رابط
    urls = []
    if event.entities:
        for entity in event.entities:
            if hasattr(entity, 'url') and entity.url:
                urls.append(entity.url)
    
    # إضافة الروابط العادية الموجودة في النص
    raw_urls = re.findall(r'(https?://t\.me/[^\s]+)', text)
    urls.extend(raw_urls)
    
    # --- القسم الأول: معالجة روابط التمويل المباشرة (?start=) ---
    for url in urls:
        bot_match = re.search(r"t\.me/([a-zA-Z0-9_]+)\?start=([a-zA-Z0-9_]+)", url)
        if bot_match:
            bot_username = bot_match.group(1)
            start_payload = bot_match.group(2)
            
            # منع التكرار: إذا تم استخدام هذا الرابط/الكود من قبل، تخطاه فوراً
            if start_payload in processed_items:
                return
                
            processed_items.add(start_payload)
            channels_activity[chat_id] = time.time()
            
            # انتظار عشوائي لمنع الحظر والسبام (بين 5 إلى 9 ثوانٍ)
            delay = random.randint(5, 9)
            print(f"[*] تم رصد رابط جديد. جاري الانتظار {delay} ثوانٍ للضغط كالبشر...")
            await asyncio.sleep(delay)
            
            try:
                # محاكاة ضغط الرابط الحقيقي بدلاً من إرسال رسالة نصية عادية
                await client(StartBotRequest(bot=bot_username, peer=bot_username, start_param=start_payload))
                print(f"[+] تم النقر على الرابط بنجاح وتفعيل البوت: {bot_username}")
            except FloodWaitError as e:
                print(f"[!] تم حظر العمل مؤقتاً (FloodWait)، يجب الانتظار {e.seconds} ثانية.")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                print(f"[-] خطأ أثناء تفعيل الرابط: {e}")

    # --- القسم الثاني: معالجة نظام الأكواد (مثل بوت طلباتي و FAABOT) ---
    if "الكود" in text or "كود" in text:
        # البحث عن الكود (كلمة أو أرقام تأتي بعد كلمة الكود)
        code_match = re.search(r"(?:الكود|كود)\s*:\s*([a-zA-Z0-9]+)", text)
        if code_match:
            extracted_code = code_match.group(1)
            
            # منع التكرار
            if extracted_code in processed_items:
                return
            processed_items.add(extracted_code)
            
            # البحث عن اسم معرف البوت المستهدف في الرسالة
            bot_username = "TALABATI_BOT" # الافتراضي في حال لم يجده
            bot_name_match = re.search(r"@([a-zA-Z0-9_]+[bB][oO][tT])", text)
            if bot_name_match:
                bot_username = bot_name_match.group(1)
                
            print(f"[*] تم رصد كود نقاط لـ {bot_username}: {extracted_code}")
            
            # الدخول للبوت والتعامل مع الأزرار الشفافة
            try:
                # بدء المحادثة مع البوت أولاً
                await client.send_message(bot_username, "/start")
                await asyncio.sleep(2)
                
                # جلب آخر رسالة من البوت للبحث عن زر "استخدام كود"
                async for message in client.iter_messages(bot_username, limit=1):
                    if message.buttons:
                        for row in message.buttons:
                            for button in row:
                                if "استخدام كود" in button.text or "كود" in button.text:
                                    print(f"[*] جاري الضغط على زر: {button.text}")
                                    await button.click()
                                    # الانتظار حتى يطلب البوت إرسال الكود
                                    await asyncio.sleep(2)
                                    # إرسال الكود المستخرج للبوت فوراً ل نكون أول المستلمين
                                    await client.send_message(bot_username, extracted_code)
                                    print(f"[+] تم إرسال الكود {extracted_code} بنجاح إلى البوت!")
                                    break
            except Exception as e:
                print(f"[-] خطأ أثناء تفعيل كود النقاط: {e}")

@client.on(events.NewMessage)
async def handle_bot_verification(event):
    """التعامل مع ردود البوتات وحل مشكلة حلقة التحقق الإجباري اللانهائية"""
    if not event.is_private:
        return
        
    sender = await event.get_sender()
    if sender and sender.bot:
        text = event.raw_text or ""
        bot_username = sender.username
        
        if "اشترك" in text or "الاشتراك" in text or "قناة" in text or "غير مشترك" in text:
            # تتبع المحاولات لمنع التعليق اللانهائي إذا كانت القناة محذوفة أو بها مشكلة
            attempts = verification_tracker.get(bot_username, 0)
            if attempts > 3:
                print(f"[!] تم تخطي البوت {bot_username} لتجاوزه حد محاولات التحقق الفاشلة (تجنباً للحظر).")
                return
                
            print(f"[*] البوت {bot_username} يطلب اشتراكاً إجبارياً...")
            
            # 1. الانضمام عبر الأزرار الشفافة
            if event.buttons:
                for row in event.buttons:
                    for button in row:
                        if button.url and "t.me" in button.url:
                            await join_channel(button.url)
            
            # 2. الانضمام عبر الروابط النصية
            urls = re.findall(r'(https?://t\.me/[^\s]+)', text)
            for url in urls:
                if "bot" not in url.lower():
                    await join_channel(url)
            
            # --- حل مشكلة عدم التزامن ---
            # ننتظر 4 ثوانٍ كاملة للتأكد من أن سيرفرات تيليجرام سجلت الحساب في القنوات قبل الضغط
            print("[*] جاري الانتظار 4 ثوانٍ ليتزامن الاشتراك في السيرفرات...")
            await asyncio.sleep(4)
            
            # 3. الضغط على زر التحقق
            if event.buttons:
                for row in event.buttons:
                    for button in row:
                        if button.text and ("تحقق" in button.text or "Check" in button.text or "اشتركت" in button.text or "تأكيد" in button.text):
                            print(f"[*] جاري الضغط على زر التأكيد: {button.text}")
                            verification_tracker[bot_username] = attempts + 1
                            await button.click()
                            return

async def channel_cleaner():
    """مهمة تنظيف لمغادرة القنوات الخاملة كل 6 ساعات لمنع امتلاء الحساب"""
    while True:
        await asyncio.sleep(3600) # فحص دوري كل ساعة
        current_time = time.time()
        for chat_id, last_time in list(channels_activity.items()):
            if current_time - last_time > SIX_HOURS:
                try:
                    await client(LeaveChannelRequest(chat_id))
                    print(f"[!] تم مغادرة القناة {chat_id} تلقائياً بسبب الخمول.")
                    del channels_activity[chat_id]
                    await asyncio.sleep(5)
                except Exception as e:
                    print(f"[-] خطأ أثناء مغادرة القناة {chat_id}: {e}")

async def main():
    print("[*] تم تشغيل النظام المطور بنجاح. جاري صيد النقاط والأكواد...")
    asyncio.create_task(channel_cleaner())
    await client.run_until_disconnected()

if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(main())

