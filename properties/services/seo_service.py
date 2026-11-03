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
        f"ที่ดิน {prop.land_display}" if prop.size_land else "",
        prop.get_zoning_display(),
    ]
    spec_text = " ".join(spec for spec in specs if spec)
    place = prop.address_text or prop.location.name
    text = f"ทรัพย์รหัส {prop.display_code} เป็น{prop.category.name}{action} ทำเล{place} ราคา {price_text(prop)}"
    return f"{text} {spec_text}".strip()
