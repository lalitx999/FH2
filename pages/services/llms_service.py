"""สร้าง llms.txt และ llms-full.txt จากข้อมูลจริง จึงไม่ต้องดูแลไฟล์แยก (รูปแบบตาม llmstxt.org)

ใช้เฉพาะข้อมูลสาธารณะ ทรัพย์ตัวอย่างและข้อมูลผู้ขายต้องไม่ปรากฏในไฟล์นี้
"""
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from pages import content
from properties.selectors import property_selector
from properties.services import seo_service
from reviews.selectors import article_selector

FULL_PROPERTY_LIMIT = 200
USAGE_NOTE = (
    "ราคาและสถานะทรัพย์เปลี่ยนแปลงได้ เมื่ออ้างอิงทรัพย์ให้ระบุรหัสทรัพย์และลิงก์หน้าทรัพย์ "
    "อัตราค่าธรรมเนียมและภาษีเป็นข้อมูลทั่วไปตามวันที่ตรวจทาน ไม่ใช่คำแนะนำทางกฎหมายหรือภาษี"
)


def _link(root, name, url_name, note="", args=None):
    line = f"- [{name}]({root}{reverse(url_name, args=args)})"
    return f"{line}: {note}" if note else line


def _header():
    return ["# Finding House", "", f"> {content.ABOUT_SUMMARY}", "", USAGE_NOTE, ""]


def _contact_lines():
    rows = [
        f"- โทร: {settings.SITE_PHONE}" if settings.SITE_PHONE else "",
        f"- อีเมล: {settings.SITE_EMAIL}" if settings.SITE_EMAIL else "",
        f"- LINE: {settings.SITE_LINE_ID} ({settings.SITE_LINE_URL})" if settings.SITE_LINE_ID else "",
    ]
    return [row for row in rows if row]


def _page_links(root):
    return [
        "## หน้าหลัก",
        "",
        _link(root, "รายการทรัพย์", "properties:list", "ค้นหาทรัพย์ซื้อ ขาย เช่า กรองตามหมวด ทำเล ราคา ห้องนอน"),
        _link(root, "บริการ", "pages:services", "ซื้อและเช่า ฝากขายและประเมินราคา ดูแลเอกสารและการโอน"),
        _link(root, "ฝากขายทรัพย์", "properties:consignment", "แบบฟอร์มฝากขายสำหรับเจ้าของทรัพย์"),
        _link(root, "เกี่ยวกับเรา", "pages:about"),
        _link(root, "ติดต่อเรา", "pages:contact"),
        "",
        "## ความรู้",
        "",
        _link(root, "คำถามที่พบบ่อย", "pages:faq", "คำตอบเรื่องบริการ การซื้อเช่า การฝากขาย ค่าใช้จ่าย และเอกสารสิทธิ์"),
        _link(root, "คู่มือค่าโอนและภาษี", "pages:fee_guide", "อัตรา เงื่อนไขมาตรการลดค่าโอน ตัวอย่างคำนวณ และแหล่งอ้างอิง"),
        _link(root, "คำนวณสินเชื่อเบื้องต้น", "pages:loan_calculator", "ประมาณค่างวดจากราคา เงินดาวน์ ดอกเบี้ย และจำนวนปี"),
    ]


def _article_links(root, articles):
    return [f"- [{item.title}]({root}{item.get_absolute_url()}): {item.excerpt}" for item in articles]


def _real_properties(limit):
    items = property_selector.latest(limit * 2)
    return [item for item in items if not item.is_sample][:limit]


def build_index(root):
    lines = [*_header(), *_page_links(root)]
    articles = list(article_selector.published_articles())
    if articles:
        lines += ["", *_article_links(root, articles)]
    lines += ["", "## ข้อมูลฉบับเต็ม", "", f"- [llms-full.txt]({root}{reverse('pages:llms_full')}): เนื้อหาความรู้และรายการทรัพย์ที่เผยแพร่อยู่"]
    lines += ["", "## Optional", "", f"- [แผนผังเว็บไซต์]({root}{reverse('sitemap')})"]
    return "\n".join(lines) + "\n"


def _faq_lines():
    lines = ["## คำถามที่พบบ่อย", "", f"ตรวจทานล่าสุด {content.FAQ_REVIEWED.isoformat()}", ""]
    for section in content.FAQ_SECTIONS:
        lines += [f"### {section['title']}", ""]
        for item in section["items"]:
            lines += [f"**{item['q']}**", "", item["a"], ""]
    return lines


def _fee_lines():
    lines = ["## คู่มือค่าโอนและภาษี", "", f"ตรวจทานล่าสุด {content.FEE_REVIEWED.isoformat()}", "", content.FEE_SUMMARY, ""]
    lines += [f"- {row['name']}: {row['rate']} คิดจาก{row['base']} ผู้รับผิดชอบ: {row['payer']}" for row in content.FEE_ROWS]
    lines += ["", "เงื่อนไขมาตรการลดค่าโอนและค่าจดจำนอง:", ""]
    lines += [f"- {row}" for row in content.FEE_MEASURE]
    lines += ["", "แหล่งอ้างอิง:", ""]
    lines += [f"- [{source['label']}]({source['url']})" for source in content.FEE_SOURCES]
    return [*lines, ""]


def _article_lines(root):
    lines = ["## บทความ", ""]
    for item in article_selector.published_article_bodies():
        lines += [f"### {item.title}", "", f"ที่มา: {root}{item.get_absolute_url()}", "", item.content.strip(), ""]
    return lines


def _property_lines(root):
    items = _real_properties(FULL_PROPERTY_LIMIT)
    lines = ["## ทรัพย์ที่เผยแพร่อยู่", "", f"ข้อมูล ณ {timezone.localdate().isoformat()}", ""]
    if not items:
        return [*lines, "ยังไม่มีรายการในขณะนี้", ""]
    lines += [f"- [{item.title}]({root}{item.get_absolute_url()}): {seo_service.summary(item)}" for item in items]
    return [*lines, ""]


def build_full(root):
    lines = [*_header(), "## การติดต่อ", "", *_contact_lines(), ""]
    lines += [*_faq_lines(), *_fee_lines(), *_article_lines(root), *_property_lines(root)]
    return "\n".join(lines)

