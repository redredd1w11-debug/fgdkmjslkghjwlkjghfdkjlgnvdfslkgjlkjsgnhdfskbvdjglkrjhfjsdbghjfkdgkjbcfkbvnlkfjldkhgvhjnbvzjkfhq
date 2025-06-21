import os
import time
import asyncio
import aiohttp
import aiofiles
import random
import io
from telethon import TelegramClient, events

api_id = 28135093
api_hash = "f1abba5a1346741d35084fd2621860f2"
session_name = "dake_session"

client = TelegramClient(session_name, api_id, api_hash)

HELP_TEXT = """dake v2 
==========================
※ .dake - вывод хелпа 
※ .dh (время в секундах) (файл с шаблонами) (название картинки или точка) (комментарий)
※ .save (имя) - сохранить медиа
※ .dxadd (id или @username) (задержка в секундах) [название_медиа]
※ .dxrem (id) - удалить таргет
※ .dxlist - список целей
※ .st - остановить автоответы
※ .dz - остановить dh
※ .dtime - аптайм бота
※ .dclear - очистить все цели и задачи
※ .dclearimgs - очистить все изображения из памяти
※ .id - узнать айди чата или пользователя
==========================
soft by @BloodyCircletov // Купить софт там же"""

HELP_IMAGE_URL = "https://i.postimg.cc/c1Qx7S32/1000049329.jpg"
TEMPLATES_DIR = "templates"
TEMPLATES_FILE = os.path.join(TEMPLATES_DIR, "templates.txt")

os.makedirs(TEMPLATES_DIR, exist_ok=True)

template_lines_cache = {}
memory_images = {}
start_time = time.time()
auto_targets = {}
dh_tasks = {}
last_reply_time = {}

async def download_image_to_memory(name: str, url: str) -> bool:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    memory_images[name] = data
                    return True
    except:
        pass
    return False

async def read_template_lines(filename: str):
    path = os.path.join(TEMPLATES_DIR, filename)
    if not os.path.isfile(path):
        return []
    if filename in template_lines_cache:
        return template_lines_cache[filename]
    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in await f.readlines() if line.strip()]
    template_lines_cache[filename] = lines
    return lines

async def get_random_template_line():
    if os.path.isfile(TEMPLATES_FILE):
        async with aiofiles.open(TEMPLATES_FILE, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in await f.readlines() if line.strip()]
        if lines:
            return random.choice(lines)
    return random.choice([
        "я тебе мать ебал", "ты пидорасина ебаная", "ты слабый пидорас"
    ])

async def dh_worker(chat_id, cooldown, template_file, image_key, comment):
    try:
        lines = await read_template_lines(template_file)
        if not lines:
            return
        idx = 0
        while True:
            line = lines[idx]
            idx = (idx + 1) % len(lines)
            text = (comment + "\n") if comment else "" + line
            if image_key != "." and image_key in memory_images:
                bio = io.BytesIO(memory_images[image_key])
                bio.name = image_key
                await client.send_file(chat_id, bio, caption=text)
            else:
                await client.send_message(chat_id, text)
            await asyncio.sleep(cooldown)
    except asyncio.CancelledError:
        pass

async def safe_get_user(uid_or_username: str):
    try:
        if uid_or_username.startswith("@"):
            return await client.get_entity(uid_or_username)
        uid_int = int(uid_or_username)
        return await client.get_entity(uid_int)
    except:
        return None

@client.on(events.NewMessage(outgoing=True, pattern=r"^\.(.+)"))
async def commands_handler(event):
    me = await client.get_me()
    if event.sender_id != me.id:
        return

    text = event.raw_text
    args = text.strip().split()
    cmd = args[0][1:].lower()
    cid = event.chat_id

    if cmd in {"dake", "help"}:
        try:
            await event.delete()
        except:
            pass
        if "help.jpg" not in memory_images:
            ok = await download_image_to_memory("help.jpg", HELP_IMAGE_URL)
            if not ok:
                await event.respond("ошибка загрузки изображения хелпа")
                return
        bio = io.BytesIO(memory_images["help.jpg"])
        bio.name = "help.jpg"
        await client.send_file(cid, bio, caption=HELP_TEXT)

    elif cmd == "dtime":
        uptime = int(time.time() - start_time)
        d, rem = divmod(uptime, 86400)
        h, rem = divmod(rem, 3600)
        m, _ = divmod(rem, 60)
        msg = f"{d}д {h}ч {m}м" if d else f"{h}ч {m}м" if h else f"{m}м"
        await event.edit(f"аптайм бота: {msg}")

    elif cmd == "id":
        if event.is_reply:
            reply = await event.get_reply_message()
            await event.edit(f"id пользователя: {reply.sender_id}")
        else:
            await event.edit(f"id чата: {cid}")

    elif cmd == "save":
        if len(args) < 2 or not event.is_reply:
            await event.edit("использование: .save <имя> (ответ на медиа)")
            return
        name = args[1]
        reply = await event.get_reply_message()
        data = await reply.download_media(bytes)
        if reply.photo or reply.document:
            ext = ".png"
        elif reply.video:
            ext = ".mp4"
        else:
            await event.edit("тип медиа не поддерживается")
            return
        memory_images[name + ext] = data
        await event.edit(f"медиа сохранено как {name}{ext}")

    elif cmd == "dclearimgs":
        memory_images.clear()
        await event.edit("все изображения из памяти очищены")

    elif cmd == "dxadd":
        if len(args) < 3:
            await event.edit("использование: .dxadd <id или @username> <delay> [медиа]")
            return
        uid_or_username = args[1]
        try:
            delay = int(args[2])
        except:
            delay = 15
        media_key = args[3] if len(args) > 3 else None
        user = await safe_get_user(uid_or_username)
        if not user:
            await event.edit("пользователь не найден")
            return
        display_name = user.username if getattr(user, 'username', None) else f"{user.first_name or ''}{(' ' + user.last_name) if getattr(user, 'last_name', None) else ''}".strip()
        if not display_name:
            display_name = str(user.id)
        if cid not in auto_targets:
            auto_targets[cid] = {}
        auto_targets[cid][str(user.id)] = (media_key, display_name, delay)
        await event.edit(f"цель {display_name}/{user.id} добавлена с задержкой {delay}с и медиа: {media_key or 'нет'}")

    elif cmd == "dxrem":
        if len(args) < 2:
            await event.edit(".dxrem <id>")
            return
        uid = args[1]
        if cid in auto_targets and uid in auto_targets[cid]:
            del auto_targets[cid][uid]
            await event.edit(f"цель {uid} удалена")
        else:
            await event.edit("цель не найдена")

    elif cmd == "dxlist":
        lines = []
        for chat_key, targets in auto_targets.items():
            for i, (uid, (media, uname, delay)) in enumerate(targets.items(), 1):
                lines.append(f"[чат {chat_key}] {i} - {uname}/{uid} (медиа:{media or 'нет'} дельта:{delay}s)")
        await event.edit("\n".join(lines) if lines else "целей нет")

    elif cmd == "st":
        auto_targets.pop(cid, None)
        await event.edit("автоответы остановлены")

    elif cmd == "dz":
        if cid in dh_tasks:
            dh_tasks[cid].cancel()
            del dh_tasks[cid]
        await event.edit("dh остановлена")

    elif cmd == "dclear":
        dh_tasks.pop(cid, None)
        auto_targets.pop(cid, None)
        await event.edit("все цели и задачи зачищены")

    elif cmd == "dh":
        if len(args) < 4:
            await event.edit("использование: .dh <кд> <шаблон> <картинка или .> [коммент]")
            return
        try:
            cooldown = int(args[1])
        except:
            await event.edit("кд должно быть числом")
            return
        template_file = args[2]
        image_key = args[3]
        comment = " ".join(args[4:]) if len(args) > 4 else ""
        if cid in dh_tasks:
            dh_tasks[cid].cancel()
        dh_tasks[cid] = asyncio.create_task(dh_worker(cid, cooldown, template_file, image_key, comment))
        await event.edit(f"dh запущена: кд={cooldown}, шаблон={template_file}, картинка={image_key}, коммент='{comment}'")

    else:
        await event.edit("неизвестная команда")

@client.on(events.NewMessage(incoming=True))
async def auto_reply_targets(event):
    me = await client.get_me()
    if event.sender_id == me.id:
        return
    cid = event.chat_id
    uid = str(event.sender_id)
    if cid not in auto_targets or uid not in auto_targets[cid]:
        return
    media, uname, delay = auto_targets[cid][uid]
    now = time.time()
    key = (cid, uid)
    if key in last_reply_time and now - last_reply_time[key] < delay:
        return
    text = await get_random_template_line()
    full_text = f"{uname} {text}"
    reply_to_id = event.message.id
    if media and media in memory_images:
        bio = io.BytesIO(memory_images[media])
        bio.name = media
        await client.send_file(cid, bio, caption=full_text, reply_to=reply_to_id)
    else:
        await client.send_message(cid, full_text, reply_to=reply_to_id)
    last_reply_time[key] = now

async def main():
    await client.start()  # без input, потому что сессия уже есть
    print("бот запущен и подключён")
    await client.run_until_disconnected()

if __name__ == "__main__":
    asyncio.run(main())
