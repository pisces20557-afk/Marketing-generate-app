"""'자료' 폴더의 사진(jpg, png)을 인스타그램용 1080x1080 정사각형으로 바꿔서 '완성' 폴더에 저장합니다.

- 사진 가운데를 기준으로 정사각형만큼 잘라낸 뒤 크기를 맞춥니다 (찌그러지지 않음).
- 원본 사진은 읽기만 하고 절대 바꾸지 않습니다.
- 저장 이름: 오늘날짜_01.jpg, 오늘날짜_02.jpg ...
  (같은 날 다시 실행해도 기존 파일을 덮어쓰지 않고 다음 번호로 이어서 저장합니다.)
"""

import re
from datetime import date, datetime
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

SIZE = 1080
BASE = Path(__file__).resolve().parent
SOURCE_DIR = BASE / "자료"
OUTPUT_DIR = BASE / "완성"
EXTENSIONS = {".jpg", ".jpeg", ".png"}

# 로고 설정
LOGO_NAMES = ["로고.jpg", "로고.png"]   # 앞에 있는 이름부터 찾는다
LOGO_FOLDERS = [BASE, SOURCE_DIR]
LOGO_WIDTH_RATIO = 0.15   # 사진 가로 폭의 15%
LOGO_MARGIN = 40          # 사진 가장자리에서 안쪽으로 40픽셀
LOGO_PADDING = 14         # 로고 주변 바탕 여백
LOGO_RADIUS = 12          # 바탕 모서리 둥글기
LOGO_GLASS = 0.62         # 바탕의 흰색 정도 (0=사진 그대로, 1=완전 흰색)

# 홍보 문구 설정
INFO_NAMES = ["가게정보.txt", "가게 정보.txt"]
CAPTION_FILE = "홍보문구.txt"
VERSIONS = ["감성형", "정보형", "이벤트형"]
STYLE_NAMES = ["내 말투.txt", "내말투.txt"]   # 사장님이 직접 쓴 글 (이모지 습관을 읽는 데 쓴다)
EMOJI_PATTERN = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF\u2B50\u2764]")
EMOJI_CHOICES = ["☕", "🌿", "🙂"]


def to_square(path):
    with Image.open(path) as img:
        # 휴대폰으로 찍은 사진이 옆으로 누워 보이지 않도록 방향을 바로잡는다
        img = ImageOps.exif_transpose(img)
        # 투명 배경(png)은 흰색 바탕 위에 올려서 jpg로 저장할 수 있게 한다
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.getchannel("A"))
            img = background
        else:
            img = img.convert("RGB")
        # 가운데 기준으로 정사각형 자르기 + 1080x1080으로 맞추기
        return ImageOps.fit(img, (SIZE, SIZE), Image.LANCZOS, centering=(0.5, 0.5))


def find_logo():
    """로고 파일을 찾는다. 없으면 None (이 경우 로고 넣기는 건너뛴다)."""
    for name in LOGO_NAMES:
        for folder in LOGO_FOLDERS:
            candidate = folder / name
            if candidate.is_file():
                return candidate
    return None


def load_logo(path):
    """로고를 열어서 주변의 빈 흰 여백을 잘라내고 정해진 크기로 줄인다."""
    with Image.open(path) as img:
        img = img.convert("RGBA")
        # 투명 부분은 흰색으로 바꿔서 한 가지 방식으로 다룬다
        flat = Image.new("RGB", img.size, (255, 255, 255))
        flat.paste(img, mask=img.getchannel("A"))
    # 흰색이 아닌 부분(= 실제 로고 그림)만 남기고 자른다
    diff = ImageChops.difference(flat, Image.new("RGB", flat.size, (255, 255, 255)))
    box = diff.convert("L").point(lambda v: 255 if v > 12 else 0).getbbox()
    if box:
        flat = flat.crop(box)
    width = round(SIZE * LOGO_WIDTH_RATIO)
    height = max(1, round(flat.height * width / flat.width))
    return flat.resize((width, height), Image.LANCZOS)


def add_logo(photo, logo):
    """사진 오른쪽 아래에 '젖빛 유리' 같은 바탕을 깔고 로고를 자연스럽게 올린다.

    바탕은 뒤의 사진이 흐릿하게 비치는 반투명 흰색이고, 로고의 흰 배경은
    '곱하기'로 합쳐서 사라지게 한다 (그래서 흰 사각형이 따로 튀지 않는다).
    """
    card_w = logo.width + LOGO_PADDING * 2
    card_h = logo.height + LOGO_PADDING * 2
    x = photo.width - LOGO_MARGIN - card_w
    y = photo.height - LOGO_MARGIN - card_h
    box = (x, y, x + card_w, y + card_h)

    # 뒤의 사진을 흐리게 + 흰색을 살짝 섞는다
    region = photo.crop(box).filter(ImageFilter.GaussianBlur(12))
    region = Image.blend(region, Image.new("RGB", region.size, (255, 255, 255)), LOGO_GLASS)
    # 로고를 올린다 (흰색 부분은 바탕 색 그대로 남는다)
    layer = Image.new("RGB", region.size, (255, 255, 255))
    layer.paste(logo, (LOGO_PADDING, LOGO_PADDING))
    region = ImageChops.multiply(region, layer)

    # 둥근 모서리로 오려서 붙인다
    mask = Image.new("L", region.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, card_w - 1, card_h - 1), LOGO_RADIUS, fill=255
    )
    result = photo.copy()
    result.paste(region, (x, y), mask)
    return result


def find_file(names):
    """BASE 폴더와 '자료' 폴더에서 이름이 맞는 첫 파일을 찾는다. 없으면 None."""
    for name in names:
        for folder in LOGO_FOLDERS:
            candidate = folder / name
            if candidate.is_file():
                return candidate
    return None


def has_final(word):
    """마지막 글자에 받침이 있으면 True (은/는, 이/가, 을/를을 고를 때 쓴다)."""
    last = word.strip()[-1:]
    return "가" <= last <= "힣" and (ord(last) - 0xAC00) % 28 != 0


SOFTEN_ENDINGS = [("넣음", "넣었습니다"), ("않음", "않습니다"), ("있음", "있습니다"),
                  ("없음", "없습니다"), ("함", "합니다")]


def soften(phrase):
    """'달지 않음' 같은 메모체 끝맺음을 사장님 말투(-습니다)인 '달지 않습니다'로 바꾼다."""
    phrase = phrase.strip().rstrip(".")
    m = re.fullmatch(r"(.+\S)\s+많음", phrase)
    if m:
        noun = m.group(1)
        return noun + ("이" if has_final(noun) else "가") + " 많습니다"
    for old, new in SOFTEN_ENDINGS:
        if phrase.endswith(old):
            return phrase[: -len(old)] + new
    return phrase


def parse_info(text):
    """'가게 정보.txt'를 읽어 이름·위치·특징·고객층·이번 주 홍보 목록으로 나눈다."""
    info = {"이름": "", "위치": "", "특징": [], "고객층": "", "홍보": []}
    in_promo = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("-"):
            if in_promo:
                info["홍보"].append(line.lstrip("-").strip())
            continue
        key, sep, value = line.replace("：", ":").partition(":")
        if not sep:
            continue
        key, value = key.strip(), value.strip()
        in_promo = False
        if key.endswith("이름"):
            info["이름"] = value
        elif key == "위치":
            info["위치"] = value
        elif "특징" in key:
            info["특징"] = [v.strip() for v in re.split(r"[,，]", value) if v.strip()]
        elif "고객" in key:
            info["고객층"] = value
        elif "홍보" in key:
            in_promo = True
            if value:
                info["홍보"].append(value)
    return info


EVENT_WORDS = ("할인", "이벤트", "증정", "무료", "쿠폰", "1+1", "적립", "행사")


def parse_promos(items):
    """홍보 목록을 신메뉴(menu), 혜택(event), 그 밖의 소식(others)으로 나눈다."""
    menu = event = None
    others = []
    for item in items:
        if event is None and any(w in item for w in EVENT_WORDS):
            event = item
            continue
        quoted = re.search(r"['\"‘“](.+?)['\"’”]", item)
        if menu is None and quoted:
            price = re.search(r"\d[\d,]*\s*원", item)
            # 숫자 사이의 쉼표(5,500)는 나누지 않는다
            parts = [p.strip() for p in re.split(r"(?<!\d),|,(?!\d)", item) if p.strip()]
            menu = {
                "이름": quoted.group(1),
                "가격": price.group(0).replace(" ", "") if price else "",
                "신메뉴": "신메뉴" in item,
                "설명": [soften(p) + "." for p in parts[1:]],
            }
            continue
        others.append(item)
    return menu, event, others


def join_sentences(*parts):
    return " ".join(p for p in parts if p)


def make_hashtags(info, menu, event):
    """지역명 + 업종 + 메뉴를 섞어 해시태그 10개를 만든다."""
    tags = []

    def add(word):
        tag = "#" + word.replace(" ", "").lstrip("#")
        if len(tag) > 1 and tag not in tags:
            tags.append(tag)

    words = info["위치"].split()
    for region in words[:2]:
        add(region + "카페")
    if len(words) > 2:
        add(words[2])
    sells_coffee = "커피" in info["이름"] or any("커피" in f for f in info["특징"])
    if words and sells_coffee:
        add(words[0] + "커피")
    for feat in info["특징"]:
        m = re.search(r"(\S+)\s*커피", feat)
        if m:
            add(m.group(1) + "커피")
        if "로스팅" in feat:
            add("로스터리")
    if menu:
        add(menu["이름"])
        if menu["신메뉴"]:
            add("신메뉴")
    if event:
        m = re.search(r"(\S+)\s+\d[\d,]*\s*원", event)
        if m and len(m.group(1)) >= 3:
            add(m.group(1))
    if "직장인" in info["고객층"]:
        add("직장인카페")
    for filler in ("동네카페", "카페추천", "오늘의커피", "카페스타그램", "커피스타그램",
                   "카페투어", "데일리카페", "일상", "소통", "맛집추천"):
        add(filler)
    return tags[:10]


def lines(*parts):
    """빈 문장은 빼고 한 줄에 한 문장씩 이어 붙인다."""
    return "\n".join(p for p in parts if p)


def para(*groups):
    """문단 사이에 빈 줄을 넣는다."""
    return "\n\n".join(g for g in groups if g)


def emoji_habit():
    """'내 말투.txt'에서 글 하나당 이모지를 평균 몇 개 쓰는지 읽는다. (0~3, 파일이 없으면 2)"""
    path = find_file(STYLE_NAMES)
    if not path:
        return 2
    text = path.read_text(encoding="utf-8-sig")
    posts = [p for p in re.split(r"\[글\s*\d+\]", text) if p.strip()] or [text]
    return min(3, round(len(EMOJI_PATTERN.findall(text)) / len(posts)))


def make_versions(info, menu, event, others):
    """감성형·정보형·이벤트형 문구를 사장님 말투(-습니다, 한 줄 한 문장)로 만든다."""
    shop = info["이름"]
    loc = info["위치"]
    feats = info["특징"]
    feat0 = feats[0] if feats else ""
    feat1 = soften(feats[1]) + "." if len(feats) > 1 else ""
    shop_topic = shop + particle(shop, "은", "는")

    n = emoji_habit()
    e = [" " + EMOJI_CHOICES[i] if i < n else "" for i in range(3)]

    new = bool(menu and menu["신메뉴"])
    name = menu["이름"] if menu else ""
    menu_name = f"'{name}'" if menu else ""
    price = menu["가격"] if menu else ""
    descs = menu["설명"] if menu else []

    emotional = para(
        lines(
            ("이번 주에 새 메뉴를 준비했습니다." if new else "이번 주 메뉴를 소개합니다.") + e[0] if menu else "",
            f"{menu_name}입니다." if menu else "",
            descs[0] if descs else "",
        ),
        lines(
            f"{shop_topic} {feat0} 가게입니다." if feat0 else "",
            feat1,
            "잠깐 쉬었다 가셔도 좋습니다." + e[1],
        ),
        f"{loc}에서 기다리겠습니다.{e[2]}" if loc else "",
    )

    if menu and price:
        menu_line = f"{'신메뉴 ' if new else ''}{menu_name}{particle(name, '은', '는')} {price}입니다.{e[0]}"
    elif menu:
        menu_line = f"{'신메뉴 ' if new else ''}{menu_name}{particle(name, '을', '를')} 준비했습니다.{e[0]}"
    else:
        menu_line = ""
    info_type = para(
        lines(f"{shop} 이번 주 소식입니다.", menu_line, *descs),
        lines(f"이번 주 혜택: {event}{e[1]}" if event else "", *[o.rstrip(".") + "." for o in others]),
        lines(feat1, f"위치는 {loc}입니다.{e[2]}" if loc else ""),
    )

    event_type = para(
        lines(
            ("이번 주 혜택을 알려드립니다." if event else "이번 주 소식을 알려드립니다.") + e[0],
            f"{event}입니다." if event else "",
        ),
        lines(
            f"{'신메뉴 ' if new else ''}{menu_name}{f'({price})' if price else ''}도 준비했습니다.{e[1]}" if menu else "",
            descs[0] if descs else "",
        ),
        lines(
            "오시기 전에 참고해 주세요." + e[2],
            f"{loc}, {shop}에서 기다리겠습니다." if loc else f"{shop}에서 기다리겠습니다.",
        ),
    )

    return {"감성형": emotional, "정보형": info_type, "이벤트형": event_type}


def particle(word, with_final, without_final):
    """받침 있는 말 뒤에는 with_final, 없는 말 뒤에는 without_final을 돌려준다."""
    return with_final if has_final(word) else without_final


def make_blog(info, menu, event, others):
    """네이버 블로그용 긴 글(1000자 안팎, 해시태그 없음)을 사장님 말투로 만든다. 제목과 본문을 돌려준다."""
    shop = info["이름"]
    loc = info["위치"]
    feats = info["특징"]
    customers = info["고객층"]
    feat0 = feats[0] if feats else ""
    feat1 = soften(feats[1]) + "." if len(feats) > 1 else ""
    shop_topic = shop + particle(shop, "은", "는")

    sections = [lines(
        f"안녕하세요, {shop}입니다.",
        "이번 주에 전해드릴 소식이 있어 글을 남깁니다.",
        "소식을 놓치지 않으시도록 이번 주 내용을 한곳에 정리했습니다.",
        "천천히 읽어 보시고 마음에 드는 것이 있으면 편하게 들러 주세요.",
    )]

    sections.append("■ 저희 가게를 소개합니다\n" + lines(
        f"{shop_topic} {loc}에 있는 가게입니다." if loc else "",
        f"저희는 {feat0}{particle(feat0, '을', '를')} 가장 중요하게 생각합니다." if feat0 else "",
        feat1,
        "찾아 주시는 분들이 편하게 머무실 수 있도록 신경 쓰고 있습니다." if feat1 else "",
        f"주로 찾아 주시는 분들은 {customers}입니다." if customers else "",
        "화려하지 않아도 한결같은 맛과 분위기를 지키려고 합니다.",
        "처음 오시는 분도, 자주 오시는 분도 부담 없이 들러 주세요.",
    ))

    if menu:
        name = menu["이름"]
        quoted = f"'{name}'"
        if menu["신메뉴"]:
            first = f"이번 주에 신메뉴 {quoted}{particle(name, '을', '를')} 준비했습니다."
        else:
            first = f"이번 주에는 {quoted}{particle(name, '을', '를')} 추천드립니다."
        sections.append(f"■ 이번 주 {'신메뉴' if menu['신메뉴'] else '메뉴'}, {quoted}\n" + lines(
            first,
            f"가격은 {menu['가격']}입니다." if menu["가격"] else "",
            *menu["설명"],
            "어떤 맛일지 궁금하셨던 분들은 이번 주에 한번 맛보세요.",
            "한 잔 드셔 보시고 어떠셨는지 편하게 이야기해 주세요.",
            "손님들의 한마디가 저희에게 큰 힘이 됩니다.",
        ))

    if event:
        sections.append("■ 이번 주 혜택\n" + lines(
            "이번 주 혜택은 다음과 같습니다.",
            f"▶ {event}",
            "이번 주에 방문해 주시는 손님들께 해당되는 혜택입니다.",
            "일정에 맞춰 들러 주세요.",
            "미리 알아 두시면 더 알뜰하게 이용하실 수 있습니다.",
        ))

    if others:
        sections.append("■ 그 밖의 소식\n" + lines(*[o.rstrip(".") + "." for o in others]))

    if loc:
        sections.append("■ 찾아오시는 곳\n" + lines(
            f"위치는 {loc}입니다.",
            "근처에 오실 일이 있으시면 잠깐 들러 쉬어 가세요.",
            "바쁜 일정 중에 짬이 나실 때 들르셔도 좋습니다.",
            f"{shop}에서 기다리고 있겠습니다.",
        ))

    summary = []
    if menu:
        price = f" {menu['가격']}" if menu["가격"] else ""
        summary.append(f"· {'신메뉴' if menu['신메뉴'] else '메뉴'}: '{menu['이름']}'{price}")
    if event:
        summary.append(f"· 혜택: {event}")
    if loc:
        summary.append(f"· 위치: {loc}")
    if len(summary) >= 2:
        sections.append("■ 이번 주 한눈에 보기\n" + "\n".join(summary))

    sections.append(lines(
        "긴 글 읽어 주셔서 고맙습니다.",
        "궁금한 점이 있으면 가게에서 편하게 물어봐 주세요.",
        "다음 소식도 정리되는 대로 다시 전해드리겠습니다.",
        "이번 주도 건강하게 보내세요.",
        f"{shop} 드림",
    ))
    return f"[{shop}] 이번 주 소식을 전해드립니다", "\n\n".join(sections)


def make_kakao(info, menu, event, others):
    """카카오톡 단골 공지용 3줄 이내 존댓말 글을 만든다."""
    shop = info["이름"]
    loc = info["위치"]
    lines = []
    if menu:
        name = menu["이름"]
        price = f"({menu['가격']})" if menu["가격"] else ""
        if menu["신메뉴"]:
            lines.append(f"안녕하세요, {shop}입니다. 이번 주 신메뉴 '{name}'{price}{particle(name, '을', '를')} 선보입니다.")
        else:
            lines.append(f"안녕하세요, {shop}입니다. 이번 주 '{name}'{price}{particle(name, '을', '를')} 추천드립니다.")
    else:
        lines.append(f"안녕하세요, {shop}입니다. 이번 주 소식을 전해드립니다.")
    if event:
        lines.append(f"이번 주 혜택: {event}")
    elif others:
        lines.append(others[0].rstrip("."))
    lines.append(f"{loc}에서 기다리겠습니다. 감사합니다." if loc else "편하게 들러 주세요. 감사합니다.")
    return "\n".join(lines[:3])


def new_run_dir():
    """'완성' 폴더 안에 이번 실행용 '날짜_시각' 새 폴더를 만든다. (같은 분에 또 실행하면 _2, _3 ...)"""
    OUTPUT_DIR.mkdir(exist_ok=True)
    name = datetime.now().strftime("%Y%m%d_%H%M")
    run_dir = OUTPUT_DIR / name
    n = 2
    while run_dir.exists():
        run_dir = OUTPUT_DIR / f"{name}_{n}"
        n += 1
    run_dir.mkdir()
    return run_dir


def write_captions(data, out_dir):
    out_dir.mkdir(exist_ok=True)
    bar = "=" * 30
    lines = [f"[홍보 문구] {date.today():%Y-%m-%d}", ""]
    lines += [bar, " 인스타그램용", bar, ""]
    for name in VERSIONS:
        lines += [f"■ {name}", data[name], ""]
    lines += ["■ 해시태그", " ".join(data["해시태그"]), ""]
    lines += [bar, " 네이버 블로그용", bar, "", f"제목: {data['블로그제목']}", "", data["블로그"], ""]
    lines += [bar, " 카카오톡 단골 공지용", bar, "", data["카카오"], ""]
    out = out_dir / CAPTION_FILE
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def make_captions(out_dir):
    """가게 정보를 읽어 홍보 문구를 만들고 out_dir 폴더에 저장한다. 문제가 있으면 건너뛴다."""
    info_path = find_file(INFO_NAMES)
    if not info_path:
        print("가게 정보 파일(가게 정보.txt)이 없어서 홍보 문구는 건너뛸게요.")
        return
    info = parse_info(info_path.read_text(encoding="utf-8-sig"))
    menu, event, others = parse_promos(info["홍보"])
    if not info["이름"] or not info["홍보"]:
        print("가게 정보에서 '가게 이름'이나 '이번 주 홍보할 것'을 읽지 못해서 홍보 문구는 건너뛸게요.")
        return

    data = make_versions(info, menu, event, others)
    data["해시태그"] = make_hashtags(info, menu, event)
    data["블로그제목"], data["블로그"] = make_blog(info, menu, event, others)
    data["카카오"] = make_kakao(info, menu, event, others)
    out = write_captions(data, out_dir)
    print(f"홍보 문구 저장 완료: {out.name}")


def main():
    if not SOURCE_DIR.is_dir():
        print("'자료' 폴더를 찾을 수 없어요.")
        return

    files = sorted(
        p for p in SOURCE_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in EXTENSIONS
    )
    if not files:
        print("'자료' 폴더에 jpg, png 사진이 없어요.")
        return

    run_dir = new_run_dir()
    today = date.today().strftime("%Y%m%d")

    # 로고 준비 (파일이 없거나 열 수 없으면 로고 없이 진행)
    logo_path = find_logo()
    logo = None
    if logo_path:
        try:
            logo = load_logo(logo_path)
            print(f"로고 사용: {logo_path.name}")
        except Exception as e:
            print(f"로고를 열 수 없어서 건너뛸게요 ({e})")
    else:
        print("로고 파일이 없어서 로고 넣기는 건너뛸게요.")

    number = 1
    for path in files:
        while (run_dir / f"{today}_{number:02d}.jpg").exists():
            number += 1
        out = run_dir / f"{today}_{number:02d}.jpg"
        try:
            photo = to_square(path)
            # 로고 파일 자체에는 로고를 또 얹지 않는다
            if logo and path.stem != "로고":
                photo = add_logo(photo, logo)
            photo.save(out, "JPEG", quality=95)
            print(f"완료: {path.name} -> {out.name}")
            number += 1
        except Exception as e:
            print(f"건너뜀: {path.name} ({e})")

    print()
    make_captions(run_dir)

    print(f"\n끝! '완성' 폴더 안의 '{run_dir.name}' 폴더를 확인해보세요.")


if __name__ == "__main__":
    main()
