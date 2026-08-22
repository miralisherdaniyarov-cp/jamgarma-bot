# Xarajat va Jamg'arma — Telegram Mini App

Bu versiya avvalgi matnli botdan farqli o'laroq, Telegram ichida to'g'ridan-to'g'ri
ochiladigan **chiroyli veb-ilova (Mini App)** beradi. Bitta Railway xizmati uchtasini
birga bajaradi:

- Telegram botga kelgan xabarlarni qabul qiladi (/start)
- Mini App uchun ma'lumot API'sini beradi (/api/...)
- Mini App'ning o'zini (chiroyli sahifani) ko'rsatadi

Ma'lumotlar jamgarma_bot.db (SQLite) faylida saqlanadi.

## Fayllar

- app.py — asosiy server (bot + API + sahifa)
- db.py — ma'lumotlar bazasi funksiyalari
- static/index.html — Mini App'ning ko'rinishi (bitta fayl, build kerak emas)
- requirements.txt, Procfile — Railway uchun sozlamalar

## 1. Bot yaratish (agar hali yaratmagan bo'lsangiz)

Telegramda @BotFather ga yozing, /newbot bilan bot yarating, TOKEN oling.

## 2. GitHub'ga yuklash

1. github.com'da hisob oching, yangi repository yarating (masalan jamgarma-bot).
2. "Add file" -> "Upload files" orqali ushbu papkadagi BARCHA fayllarni
   (shu jumladan static papkasini butunligicha) yuklang. "Commit changes" bosing.

## 3. Railway'da joylashtirish

1. railway.app'ga GitHub orqali kiring.
2. "New Project" -> "Deploy from GitHub repo" -> repositoriyangizni tanlang.
3. "Settings" -> "Networking" bo'limiga o'ting, "Generate Domain" tugmasini
   bosing. Sizga https://xxxxx.up.railway.app kabi manzil beriladi -- uni nusxalang.
4. "Variables" bo'limiga o'ting, ikkita o'zgaruvchi qo'shing:
   - BOT_TOKEN -- BotFather bergan token
   - PUBLIC_URL -- 3-qadamda olgan manzil (oxirida / bo'lmasin), masalan:
     https://xxxxx.up.railway.app
5. Railway avtomatik qayta deploy qiladi. "Deployments" -> "Logs" bo'limida
   xatolik yo'qligini tekshiring.

## 4. Mini App tugmasini Telegram'ga ulash

1. Telegramda @BotFather ga qayting.
2. /mybots -> botingizni tanlang -> "Bot Settings" -> "Menu Button".
3. "Configure Menu Button" ni tanlang, so'ralganda PUBLIC_URL manzilini
   yuboring (masalan https://xxxxx.up.railway.app), so'ng tugma matnini kiriting
   (masalan: "Ochish").

## 5. Sinab ko'rish

Telegram'da botingizga o'ting -- chap pastda (yoki xabar ichida) Mini App tugmasi
paydo bo'lishi kerak. Bosganda ilova to'g'ridan-to'g'ri Telegram ichida ochiladi.
/start yuborsangiz ham ilovani ochuvchi tugma chiqadi.

## Funksiyalar

- Xarajat qo'shish (8 kategoriya bilan)
- Kirim qo'shish
- Jamg'arma -- pul qo'shish, yechish, yig'ilgan summani ko'rish
- Umumiy balans va oylik statistika
- Kategoriyalar bo'yicha diagramma
- Sana bo'yicha guruhlangan tarix, o'chirish imkoniyati

## Eslatma

Har bir foydalanuvchining ma'lumoti uning shaxsiy Telegram ID'siga bog'liq --
ya'ni botni kim ochsa, faqat o'zining xarajatlarini ko'radi.
