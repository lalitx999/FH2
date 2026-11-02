from properties.models import Property


def price_text(prop):
    price = f"{prop.price:,.0f} บาท"
    return f"{price}ต่อเดือน" if prop.property_type == Property.Type.RENT else price


def summary(prop):
    """สรุปข้อเท็จจริงของทรัพย์ในย่อหน้าเดียว ใช้ทั้งบนหน้าเว็บ meta description schema และ llms.txt"""
    action = "ให้เช่า" if prop.property_type == Property.Type.RENT else "ขาย"
    specs = [
        f"{prop.bedrooms} ห้องนอน" if prop.bedrooms else "",
        f"{prop.bathrooms} ห้องน้ำ" if prop.bathrooms else "",
        f"พื้นที่ใช้สอย {prop.size_usable:,.0f} ตร.ม." if prop.size_usable else "",
        f"ที่ดิน {prop.size_land:,.0f} ตร.ว." if prop.size_land else "",
    ]
    spec_text = " ".join(spec for spec in specs if spec)
    text = f"ทรัพย์รหัส {prop.property_code} เป็น{prop.category.name}{action} ทำเล{prop.location.name} ราคา {price_text(prop)}"
    return f"{text} {spec_text}".strip()
