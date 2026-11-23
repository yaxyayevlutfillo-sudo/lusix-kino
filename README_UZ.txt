LUSIX KINO — SERVER + TELEGRAM ADMIN
=====================================

LOYIHA TARKIBI
- index.html: foydalanuvchi sayti. Sayt ichida admin panel yo‘q.
- main.py: FastAPI server, foydalanuvchi autentifikatsiyasi, profil, VIP va Telegram bot.
- requirements.txt: Python kutubxonalari.
- render.yaml: Render deploy va PostgreSQL sozlamasi.

MUHIM: BU HALI INTERNETGA DEPLOY QILINMAGAN. ZIPNI YUKLAB OLISH SAYTNI O‘Z-O‘ZIDAN INTERNETGA CHIQARMAYDI.

TELEGRAM ADMIN BOTNI SOZLASH
1. Telegramda @BotFather ni oching, /newbot yuboring va bot yarating.
2. BotFather bergan tokenni maxfiy saqlang. Uni chatga yubormang.
3. Telegramda @userinfobot orqali o‘zingizning raqamli Telegram ID'ingizni oling.
4. Render servisining Environment bo‘limida:
   BOT_TOKEN = BotFather bergan token
   TELEGRAM_ADMIN_IDS = sizning raqamli Telegram ID'ingiz
5. Deploy/Restart qiling va botga /start yuboring.
6. Admin buyruqlari faqat TELEGRAM_ADMIN_IDS ro‘yxatidagi IDlarga ishlaydi.

TELEGRAM BUYRUQLARI
/start yoki /help — yordam
/movies — kinolar ro‘yxati
/addmovie nomi|film/serial/cartoon/anime|2026|tavsif|poster_url|video_url|vip(yes/no)
   Misol: /addmovie Interstellar|film|2014|Kosmik sarguzasht|https://...poster.jpg|https://...mp4|no
/addepisode kinoID|1-qism|https://...mp4 — serialga qism qo‘shish
/editmovie ID|yangi nomi|tavsif|poster_url|video_url — kino ma’lumotini o‘zgartirish
/delmovie ID — kinoni o‘chirish
/pending — kutilayotgan to‘lovlar
/approve ID — so‘rovni tasdiqlash va tarif bo‘yicha VIP berish
/reject ID — to‘lov so‘rovini rad etish
/vip email@gmail.com|30 — 7, 30, 90 yoki 365 kun VIP berish
/user email@gmail.com — foydalanuvchi ma’lumoti
/users — hisoblar, kinolar va to‘lovlar soni

SAYTDA ISHLAYDIGAN QISMLAR
- Ro‘yxatdan o‘tish va kirish: server bazasida parol xeshi bilan.
- Profil: ID, ism, email, telefon, ro‘yxatdan o‘tgan sana.
- Profil ichida VIP holati, muddati, qolgan vaqti, to‘lovlar tarixi.
- Ism va telefonni tahrirlash.
- Sevimli va ko‘rilgan kinolar serverda saqlanadi.
- Katalog, qidirish, tur bo‘yicha filter, kino oynasi va video player.
- VIP talab qiladigan videolarni VIP bo‘lmagan foydalanuvchi ko‘ra olmaydi.
- VIP so‘rovi Telegram admin botiga xabar bo‘lib keladi; admin tasdiqlasa VIP beriladi.
- Profil sahifasiga kirganda bosh sahifa, katalog va VIP reklama bloki yashiriladi.

TO‘LOV VA MEDIA CHEKLOVLARI
- Payme, Click, Uzum Bank, Paynet, UZCARD va HUMO hozircha to‘lov so‘rovining usuli sifatida tanlanadi.
- Haqiqiy avtomatik pul qabul qilish uchun har bir provayderdan merchant shartnomasi, API kalitlari va callback/webhook ma’lumotlari kerak. Hozirgi admin tasdig‘i qo‘lda bajariladi; bu real pul to‘langanini avtomatik tekshirmaydi.
- Video ko‘rsatish uchun hammaga ochiq, to‘g‘ridan-to‘g‘ri ishlaydigan MP4/HLS URL kerak. Katta video/poster fayllarni serverga yuklash uchun alohida S3-compatible storage (masalan Cloudflare R2) ulash kerak.
- Serial qismlari Telegramdagi /addepisode buyrug‘i orqali qo‘shiladi.
- Render bepul servislarining uxlab qolish, limit va ma’lumotlar saqlash shartlari bo‘lishi mumkin. Ishga tushgach backup va doimiy hostingni sozlash tavsiya etiladi.

DEPLOY (TELEFONDAN)
1. ZIPni yuklab oling va telefoningizdagi fayl menejerida arxivdan chiqaring.
2. Ichidagi index.html, main.py, requirements.txt, render.yaml va README_UZ.txt fayllarini GitHub repository ildiziga yuklang.
3. Render.com saytida New > Blueprint tanlang va GitHub repositoryni ulang.
4. Render PostgreSQL bazasi va web servisni render.yaml orqali yaratadi.
5. Render servisining Environment bo‘limida BOT_TOKEN va TELEGRAM_ADMIN_IDS ni kiriting.
6. Deploy tugagach berilgan https://...onrender.com manzilini oching.
7. /health manzili {"status":"ok"} qaytarsa server ishlayapti.

XAVFSIZLIK
- Bot tokenini HTML, GitHub ochiq repozitoriy yoki chatga yozmang.
- TELEGRAM_ADMIN_IDS ga faqat o‘zingiz ishonadigan admin IDlarini kiriting.
- JWT_SECRET Render tomonidan avtomatik yaratiladi.
