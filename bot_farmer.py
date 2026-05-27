import os
import re
import asyncio
import random
import time
from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.functions.channels import JoinChannelRequest, LeaveChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest
from telethon.errors import FloodWaitError, UserAlreadyParticipantError

# جلب البيانات من بيئة GitHub Secrets
API_ID = int(os.environ.get("TELEGRAM_API_ID", 0))
API_HASH = os.environ.get("TELEGRAM_API_HASH", "")
SESSION_STRING = os.environ.get("TELEGRAM_SESSION", "")

# إعداد العميل (Userbot)
client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

# قاموس لتتبع آخر مرة تم فيها إرسال رابط في كل قناة
channels_activity = {}
SIX_HOURS = 6 * 60 * 60

async def join_channel(channel_link):
    """دالة للانضمام إلى القنوات (سواء كانت عامة أو خاصة عبر رابط دعوة)"""
    try:
        if "+" in channel_link or "joinchat" in channel_link:
            # روابط الدعوة الخاصة
            invite_hash = channel_link.split("/")[-1].replace("+", "")
            await client(ImportChatInviteRequest(invite_hash))
        else:
            # القنوات العامة
            username = channel_link.split("/")[-1]
            await client(JoinChannelRequest(username))
        print(f"[+] تم الانضمام بنجاح إلى: {channel_link}")
        await asyncio.sleep(random.randint(2, 5)) # انتظار بسيط بعد الانضمام
    except UserAlreadyParticipantError:
        pass # أنت مشترك بالفعل
    except Exception as e:
        print(f"[-] خطأ أثناء الانضمام للقناة {channel_link}: {e}")

@client.on(events.NewMessage)
async def handle_new_messages(event):
    chat_id = event.chat_id
    text = event.raw_text
    
    # 1. البحث عن روابط البوتات لجمع النقاط
    # مثال: https://t.me/botname?start=12345
    bot_link_pattern = r"t\.me/([a-zA-Z0-9_]+)\?start=([a-zA-Z0-9_]+)"
    match = re.search(bot_link_pattern, text)
    
    if match:
        bot_username = match.group(1)
        start_payload = match.group(2)
        
        print(f"[*] تم رصد رابط نقاط! البوت: {bot_username}")
        
        # تحديث نشاط القناة التي نشرت الرابط (لكي لا نغادرها)
        channels_activity[chat_id] = time.time()
        
        # تأخير عشوائي لتجنب الحظر
        delay = random.randint(5, 9)
        print(f"[*] جاري الانتظار {delay} ثوانٍ لتجنب الحظر...")
        await asyncio.sleep(delay)
        
        try:
            # إرسال رسالة /start للبوت مع الكود
            await client.send_message(bot_username, f"/start {start_payload}")
            print(f"[+] تم النقر على الرابط وإرسال Start إلى {bot_username}")
        except FloodWaitError as e:
            print(f"[!] تحذير FloodWait: يجب الانتظار {e.seconds} ثانية.")
            await asyncio.sleep(e.seconds)

@client.on(events.NewMessage)
async def handle_bot_replies(event):
    # 2. التعامل مع ردود البوتات (الاشتراك الإجباري)
    if not event.is_private:
        return
        
    sender = await event.get_sender()
    if sender and sender.bot:
        text = event.raw_text
        
        # إذا طلب البوت الاشتراك، نقوم باستخراج الروابط من النص أو الأزرار الشفافة
        if "اشترك" in text or "الاشتراك" in text or "قناة" in text:
            print(f"[*] البوت {sender.username} يطلب اشتراك إجباري.")
            
            # استخراج الروابط من الأزرار (Inline Buttons)
            if event.buttons:
                for row in event.buttons:
                    for button in row:
                        if button.url and "t.me" in button.url:
                            await join_channel(button.url)
                        # إذا كان الزر للتحقق من الاشتراك
                        elif button.text and ("تحقق" in button.text or "Check" in button.text or "اشتركت" in button.text):
                            print(f"[*] جاري الضغط على زر: {button.text}")
                            await asyncio.sleep(random.randint(3, 6))
                            await button.click()
            
            # استخراج الروابط من النص (في حال لم تكن أزرار شفافة)
            urls = re.findall(r'(https?://t\.me/[^\s]+)', text)
            for url in urls:
                if "bot" not in url.lower(): # نتجنب الانضمام لبوتات كأنها قنوات
                    await join_channel(url)
            
            # محاولة إرسال /start مجدداً بعد الانضمام إذا لم يكن هناك زر تحقق
            if not event.buttons:
                await asyncio.sleep(3)
                await event.reply("/start")

async def channel_cleaner():
    """مهمة تعمل في الخلفية لمغادرة القنوات غير النشطة بعد 6 ساعات"""
    while True:
        await asyncio.sleep(3600) # فحص كل ساعة
        current_time = time.time()
        
        for chat_id, last_time in list(channels_activity.items()):
            if current_time - last_time > SIX_HOURS:
                try:
                    await client(LeaveChannelRequest(chat_id))
                    print(f"[!] تم مغادرة القناة {chat_id} بسبب الخمول (مرت 6 ساعات دون روابط).")
                    del channels_activity[chat_id]
                    await asyncio.sleep(5) # لتجنب الحظر أثناء المغادرة
                except Exception as e:
                    print(f"[-] خطأ أثناء مغادرة القناة {chat_id}: {e}")

async def main():
    print("[*] تم تشغيل السكريبت بنجاح، جاري المراقبة...")
    # تشغيل مهمة التنظيف في الخلفية
    asyncio.create_task(channel_cleaner())
    # إبقاء العميل قيد التشغيل
    await client.run_until_disconnected()

if __name__ == '__main__':
    with client:
        client.loop.run_until_complete(main())

