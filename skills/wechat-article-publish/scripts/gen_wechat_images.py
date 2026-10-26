#!/usr/bin/env python3
"""
公众号配图生成器 —— 科技风 / AI智能体 / 机器人主题
用法: python3 gen_wechat_images.py <slug> <title> [subtitle]

生成 articles/assets/<slug>/thumb.png (2.35:1 封面) 和 body.png (1:1 正文大图)
"""
import math, os, random, sys
from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "articles", "assets")

# 字体
try:
    FONT_TITLE = ImageFont.truetype("/System/Library/Fonts/STHeiti Medium.ttc", 46)
    FONT_H1 = ImageFont.truetype("/System/Library/Fonts/STHeiti Medium.ttc", 50)
    FONT_H2 = ImageFont.truetype("/System/Library/Fonts/STHeiti Light.ttc", 26)
    FONT_BODY = ImageFont.truetype("/System/Library/Fonts/STHeiti Light.ttc", 22)
    FONT_SMALL = ImageFont.truetype("/System/Library/Fonts/STHeiti Light.ttc", 15)
    FONT_MONO = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 13)
    FONT_TAG = ImageFont.truetype("/System/Library/Fonts/STHeiti Medium.ttc", 18)
except Exception:
    FONT_TITLE = FONT_H1 = FONT_H2 = FONT_BODY = FONT_SMALL = FONT_TAG = ImageFont.load_default()
    FONT_MONO = ImageFont.load_default()

DARK = (10, 14, 23)
DEEP_BLUE = (13, 21, 37)
BRIGHT_CYAN = (0, 229, 255)
ELECTRIC_BLUE = (59, 130, 246)
PURPLE = (168, 85, 247)
WARM_ORANGE = (245, 158, 11)
WHITE_SOFT = (226, 232, 240)
GRAY = (100, 116, 139)
DIM = (30, 41, 59)


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def gradient_bg(w, h, c1, c2, vertical=True):
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for i in range(h if vertical else w):
        ratio = i / (h if vertical else w)
        r = int(c1[0] + (c2[0] - c1[0]) * ratio)
        g = int(c1[1] + (c2[1] - c1[1]) * ratio)
        b = int(c1[2] + (c2[2] - c1[2]) * ratio)
        if vertical:
            draw.line([(0, i), (w, i)], fill=(r, g, b))
        else:
            draw.line([(i, 0), (i, h)], fill=(r, g, b))
    return img


def draw_glow_ring(draw, cx, cy, r, color, width=2):
    for t in range(0, 360, 3):
        a = math.radians(t)
        da = math.radians(3)
        x1, y1 = cx + int(r * math.cos(a)), cy + int(r * math.sin(a))
        x2, y2 = cx + int(r * math.cos(a + da)), cy + int(r * math.sin(a + da))
        fade = 60 + int(195 * abs(math.sin(a * 3)))
        draw.line([(x1, y1), (x2, y2)], fill=(*color, fade), width=width)


def draw_hexagon(draw, cx, cy, r, color, width=2):
    pts = [(cx + int(r * math.cos(math.radians(60 * i - 30))),
            cy + int(r * math.sin(math.radians(60 * i - 30)))) for i in range(6)]
    draw.polygon(pts, outline=color, width=width)


def draw_line_network(draw, pts, color, alpha=40):
    for i, p1 in enumerate(pts):
        for j, p2 in enumerate(pts[i+1:], i+1):
            dist = math.hypot(p1[0] - p2[0], p1[1] - p2[1])
            if dist < 200:
                fade = max(5, int(alpha * (1 - dist / 200)))
                draw.line([p1, p2], fill=(*color, fade), width=1)


def generate_thumb(slug, title, subtitle=""):
    W, H = 900, 383
    img = gradient_bg(W, H, DARK, DEEP_BLUE, vertical=True)
    draw = ImageDraw.Draw(img)

    # 背景光晕
    for _ in range(3):
        ox, oy, orad = random.randint(-100, W+100), random.randint(-50, H+50), random.randint(100, 250)
        for r in range(orad, 0, -2):
            alpha = int(2 * (1 - r / orad))
            color = random.choice([BRIGHT_CYAN, PURPLE, ELECTRIC_BLUE])
            draw.ellipse([(ox-r, oy-r), (ox+r, oy+r)], fill=(*color, alpha))

    # 网格
    for x in range(0, W, 40):
        draw.line([(x, 0), (x, H)], fill=(*DIM, 15), width=1)
    for y in range(0, H, 40):
        draw.line([(0, y), (W, y)], fill=(*DIM, 15), width=1)

    # AI 智能体六边形头部
    ax, ay = 160, H // 2
    draw_glow_ring(draw, ax, ay, 80, BRIGHT_CYAN, width=2)
    draw_glow_ring(draw, ax, ay, 60, PURPLE, width=2)
    draw_hexagon(draw, ax, ay, 45, BRIGHT_CYAN, width=3)
    draw_hexagon(draw, ax, ay, 35, ELECTRIC_BLUE, width=2)
    draw.ellipse([(ax-6, ay-28), (ax+6, ay-16)], fill=BRIGHT_CYAN)
    pts_body = [(ax, ay+45), (ax-15, ay+25), (ax+15, ay+25)]
    draw.polygon(pts_body, outline=PURPLE, width=2)
    for angle in [210, 230, 250, 280, 310, 330]:
        a = math.radians(angle)
        ex, ey = ax + int(75 * math.cos(a)), ay + int(75 * math.sin(a))
        draw.line([(ax, ay), (ex, ey)], fill=(*BRIGHT_CYAN, 60), width=1)

    # 浏览器窗口
    bx, by, bw, bh = 520, 60, 310, 220
    draw.rounded_rectangle([(bx, by), (bx+bw, by+bh)], radius=12, fill=(*DIM, 100), outline=(*GRAY, 80), width=2)
    draw.rectangle([(bx, by), (bx+bw, by+30)], fill=(*DARK, 200))
    for i, c in enumerate([hex_to_rgb("#ff5f57"), hex_to_rgb("#febc2e"), hex_to_rgb("#28c840")]):
        draw.ellipse([(bx+12+i*20, by+9), (bx+24+i*20, by+21)], fill=c)
    draw.rounded_rectangle([(bx+80, by+6), (bx+bw-15, by+24)], radius=6, fill=(*GRAY, 50))
    draw.text((bx+90, by+8), "https://the-internet.com", fill=(*GRAY, 150), font=FONT_MONO)

    code_lines = [
        ("git init my-project", BRIGHT_CYAN),
        ("git add . && git commit", ELECTRIC_BLUE),
        ('git checkout -b feature/xxx', WARM_ORANGE),
        ("git merge --no-ff feature/xxx", PURPLE),
    ]
    for i, (line, color) in enumerate(code_lines):
        draw.text((bx+20, by+42+i*24), line, fill=color, font=FONT_MONO)

    for _ in range(20):
        px, py = random.randint(bx, bx+bw), random.randint(by+40, by+bh-10)
        dot_size = random.randint(1, 3)
        draw.ellipse([(px, py), (px+dot_size, py+dot_size)],
                     fill=random.choice([BRIGHT_CYAN, ELECTRIC_BLUE, PURPLE, WARM_ORANGE]))

    tag_line = "36 平台 · 103 命令 · MIT 开源"
    draw.text((30, H-50), tag_line, fill=(*GRAY, 200), font=FONT_TAG)

    tx, ty = 390, 20
    draw.text((tx+2, ty+2), title, fill=(*DARK, 120), font=FONT_TITLE)
    draw.text((tx, ty), title, fill=BRIGHT_CYAN, font=FONT_TITLE)
    if subtitle:
        draw.text((tx+4, ty+60), subtitle, fill=WHITE_SOFT, font=FONT_H2)
        draw.line([(tx, ty+110), (tx+250, ty+110)], fill=(*BRIGHT_CYAN, 100), width=2)
    draw.text((550, H-40), "git用法系列", fill=(*GRAY, 120), font=FONT_MONO)

    img = img.filter(ImageFilter.GaussianBlur(radius=0.3))
    out_dir = os.path.join(OUT_ROOT, slug)
    os.makedirs(out_dir, exist_ok=True)
    img.save(os.path.join(out_dir, "thumb.png"), "PNG")
    return os.path.join(out_dir, "thumb.png")


def generate_body(slug, title, subtitle=""):
    BW = 800
    cx, cy = BW // 2, BW // 2
    img = gradient_bg(BW, BW, DARK, hex_to_rgb("#0f172a"), vertical=True)
    draw = ImageDraw.Draw(img)

    for (lx, ly, lrad, lc) in [(200, 200, 180, BRIGHT_CYAN), (600, 300, 150, PURPLE), (400, 650, 200, ELECTRIC_BLUE)]:
        for r in range(lrad, 0, -3):
            alpha = int(2 * (1 - r / lrad))
            draw.ellipse([(lx-r, ly-r), (lx+r, ly+r)], fill=(*lc, alpha))

    for x in range(0, BW, 50):
        draw.line([(x, 0), (x, BW)], fill=(*DIM, 10), width=1)
    for y in range(0, BW, 50):
        draw.line([(0, y), (BW, y)], fill=(*DIM, 10), width=1)

    # 36节点网络
    nodes = [(cx + int((300 + random.randint(-30, 30)) * math.cos(math.radians(i*10))),
              cy + int((300 + random.randint(-30, 30)) * math.sin(math.radians(i*10)))) for i in range(36)]
    draw_line_network(draw, nodes, BRIGHT_CYAN, alpha=20)
    for px, py in nodes:
        r = random.randint(2, 5)
        draw.ellipse([(px-r, py-r), (px+r, py+r)],
                     fill=random.choice([BRIGHT_CYAN, ELECTRIC_BLUE, PURPLE]))

    platform_names = [("知乎", 0), ("GitHub", 5), ("微博", 10), ("B站", 15),
                      ("BOSS", 20), ("豆瓣", 25), ("arXiv", 30), ("雪球", 35)]
    for name, idx in platform_names:
        angle = math.radians(idx * 10)
        px = cx + int(310 * math.cos(angle))
        py = cy + int(310 * math.sin(angle))
        draw.text((px - len(name)*7, py+8), name, fill=(*GRAY, 180), font=FONT_SMALL)

    # Git 核心图标
    agent_r = 60
    draw_glow_ring(draw, cx, cy, agent_r+25, BRIGHT_CYAN, width=3)
    draw_glow_ring(draw, cx, cy, agent_r+12, PURPLE, width=2)
    draw_hexagon(draw, cx, cy, agent_r, BRIGHT_CYAN, width=4)
    draw_hexagon(draw, cx, cy, agent_r-12, ELECTRIC_BLUE, width=2)
    eye_y = cy - 22
    draw.ellipse([(cx-10, eye_y-8), (cx, eye_y+4)], fill=BRIGHT_CYAN)
    draw.ellipse([(cx, eye_y-8), (cx+10, eye_y+4)], fill=BRIGHT_CYAN)
    draw.line([(cx, cy-agent_r), (cx, cy-agent_r-25)], fill=BRIGHT_CYAN, width=2)
    draw.ellipse([(cx-4, cy-agent_r-33), (cx+4, cy-agent_r-25)], fill=BRIGHT_CYAN)
    draw.text((cx-45, cy+agent_r+8), "Git", fill=BRIGHT_CYAN, font=FONT_MONO)

    for rd, rc in [(80, ELECTRIC_BLUE), (140, PURPLE)]:
        draw.ellipse([(cx-rd, cy-rd), (cx+rd, cy+rd)], outline=(*rc, 40), width=2)
        for j in range(40):
            a = math.radians(j * 9)
            x, y = cx + int(rd * math.cos(a)), cy + int(rd * math.sin(a))
            if j % 3 == 0:
                draw.ellipse([(x-2, y-2), (x+2, y+2)], fill=(*rc, 80))

    for deg in range(0, 360, 30):
        a = math.radians(deg)
        dx, dy = int(agent_r * math.cos(a)), int(agent_r * math.sin(a))
        ex, ey = cx + int(280 * math.cos(a)), cy + int(280 * math.sin(a))
        draw.line([(cx+dx, cy+dy), (ex, ey)], fill=(*BRIGHT_CYAN, 25), width=1)

    tw = draw.textbbox((0, 0), title, font=FONT_H1)
    tw_w = tw[2] - tw[0]
    draw.text((cx - tw_w//2, 30), title, fill=BRIGHT_CYAN, font=FONT_H1)
    if subtitle:
        sw = draw.textbbox((0, 0), subtitle, font=FONT_BODY)
        sw_w = sw[2] - sw[0]
        draw.text((cx - sw_w//2, 95), subtitle, fill=WHITE_SOFT, font=FONT_BODY)
        draw.line([(cx-80, 130), (cx+80, 130)], fill=(*BRIGHT_CYAN, 120), width=2)

    bottom = "Git 用法 · 从入门到协作 · 开发者必备技能"
    bw2 = len(bottom) * 8
    draw.text((cx - bw2//2, BW-45), bottom, fill=(*GRAY, 150), font=FONT_SMALL)

    out_dir = os.path.join(OUT_ROOT, slug)
    os.makedirs(out_dir, exist_ok=True)
    img.save(os.path.join(out_dir, "body.png"), "PNG")
    return os.path.join(out_dir, "body.png")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 gen_wechat_images.py <slug> <cover_title> [subtitle]")
        sys.exit(1)

    slug = sys.argv[1]
    title = sys.argv[2]
    subtitle = sys.argv[3] if len(sys.argv) > 3 else ""

    thumb_path = generate_thumb(slug, title, subtitle)
    body_path = generate_body(slug, title, subtitle)
    print(f"✅ thumb: {thumb_path}")
    print(f"✅ body:  {body_path}")
