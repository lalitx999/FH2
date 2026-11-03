# Finding House

Django + Bootstrap 5 + Ajax + PostgreSQL

## เริ่มใช้งานในเครื่อง

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
createdb fh_app
.venv/bin/python manage.py migrate
.venv/bin/python manage.py createsuperuser
.venv/bin/python manage.py runserver
```

เว็บอยู่ที่ `http://localhost:8000/` หลังบ้านอยู่ที่ `/dashboard/`

นำเข้าบทความและทรัพย์ตัวอย่าง 15 รายการจากเว็บเดิม หรือลบทรัพย์ตัวอย่างเมื่อมีของจริง:

```bash
.venv/bin/python manage.py load_sample_data
```

```bash
.venv/bin/python manage.py load_sample_data --remove
```

นำเข้าเฉพาะทรัพย์จำลองโซนพัทยา 28 รายการ ทุกหมวดทั้งขายและเช่า คำสั่ง `--remove` ลบรายการเหล่านี้และทำเลพัทยาที่ไม่มีทรัพย์เหลือด้วย:

```bash
.venv/bin/python manage.py load_sample_data --pattaya
```

ถ้ายังไม่ตั้ง `EMAIL_HOST_USER` ใน `.env` อีเมลและรหัส OTP จะพิมพ์ออก console แทนการส่งจริง

```bash
.venv/bin/python manage.py test
```

## กติกาของโปรเจกต์

- Ajax ตอบเป็น HTML จาก template เดียวกับหน้าเว็บ ข้อตกลงอยู่ที่ `config/ajax.py` ฝั่ง JS อยู่ที่ `static/js/app.js`
- กฎการลงทรัพย์อยู่ใน `config/settings/base.py` ที่เดียว
- ไฟล์โฉนดอยู่ใน `private_media/` เปิดได้ผ่าน `/dashboard/deeds/<id>/` เท่านั้น
- ใช้ไฟล์ใน `static/vendor/` เท่านั้น ห้าม CDN
- ปุ่มทรงรี ใช้ไอคอนแทนอิโมจิ สีสว่างแบบเรียบตามตัวแปรใน `static/css/app.css` ห้าม gradient และสีทึบ (`pages/tests.py` ตรวจให้)

## โครงสร้างโค้ด

- `views.py` รับคำขอและส่งคำตอบเท่านั้น
- `<app>/selectors/` คำสั่งอ่านข้อมูล คุม `select_related`, `prefetch_related`, `only` ที่นี่
- `<app>/services/` ตรรกะธุรกิจและการเขียนข้อมูล
- `<app>/tasks.py` งาน Celery เช่น อีเมล คำตอบแชท แปลงคำขอฝากขาย
- `config/settings/` แยกเป็น `base`, `local`, `production`
- `chatbot/providers/` ผู้ให้บริการ LLM เพิ่มรายใหม่ได้โดยไม่แตะส่วนอื่น

## ขึ้นระบบจริง

```bash
docker compose up -d --build
```

Compose รัน web, Celery worker, PostgreSQL, Redis และ nginx โดยใช้ `config.settings.production` ซึ่งจะไม่ยอมเริ่มถ้าขาด `SECRET_KEY`, `ALLOWED_HOSTS` หรือ `REDIS_URL`

เว็บเปิดที่ `127.0.0.1:8023` เปลี่ยนพอร์ตได้ด้วย `HOST_PORT` ใน `.env` และต้องมี reverse proxy ของเซิร์ฟเวอร์ส่งต่อเข้ามา

ก่อนเปิดจริงให้ลบข้อมูลตัวอย่าง

```bash
docker compose exec web python manage.py load_sample_data --remove
```

## ฟอร์มลงทรัพย์และเครื่องคำนวณ

- ช่องเฉพาะของแต่ละหมวดกำหนดที่ `CATEGORY_FIELDS` ใน `properties/constants.py` ที่เดียว ใช้ทั้งการแสดงฟอร์ม การล้างค่าที่ไม่เกี่ยว และคะแนนความครบถ้วน
- หมวดที่สร้างเองในหลังบ้านยังไม่มีกฎ จึงแสดงทุกช่อง
- เครื่องคำนวณสินเชื่อคำนวณในเบราว์เซอร์ ไม่ส่งและไม่บันทึกตัวเลขของผู้ใช้ ค่าเริ่มต้นตั้งด้วย `LOAN_*` ใน `.env` ก่อนเปิดจริงให้เจ้าของเว็บยืนยันค่าเหล่านี้ และเมื่อตรวจทานเนื้อหาแล้วให้แก้วันที่ `LOAN_REVIEWED`

## แชทบอท

ตั้ง `LLM_PROVIDERS` และ API key ใน `.env` ระบบจะลองตามลำดับ ถ้าใช้ไม่ได้ทั้งหมดจะตอบด้วยกฎพื้นฐาน ดูสถานะได้ที่เมนูแชทบอทในหลังบ้าน

## SEO และ AEO

- schema.org ทั้งหมดอยู่ที่ `pages/services/schema_service.py` ข้อมูลต้องตรงกับที่แสดงบนหน้าเว็บ
- เนื้อหาคำถามที่พบบ่อยและคู่มือค่าโอนอยู่ที่ `pages/content.py` ใช้ร่วมกันทั้งหน้าเว็บ schema และ llms.txt เมื่อตรวจทานตัวเลขแล้วให้แก้วันที่ `FEE_REVIEWED`
- `/llms.txt` และ `/llms-full.txt` สร้างจากข้อมูลจริงอัตโนมัติ
- เมื่อใช้ไอคอน Font Awesome ใหม่ ให้รัน `python manage.py build_icon_css`
