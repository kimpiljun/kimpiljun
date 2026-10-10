"""글꼴 폭을 검사해 여백이 확보된 README 도식 PNG 생성.

python docs/render_workflow.py [--font /path/to/korean-font.ttf]
Pillow 필요. Windows 기본값: 맑은 고딕.
"""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--font', default='C:/Windows/Fonts/malgun.ttf')
args = parser.parse_args()
scale = 2
image = Image.new('RGB', (1040 * scale, 1620 * scale), '#f4f7f4')
draw = ImageDraw.Draw(image)
title_font = ImageFont.truetype(args.font, 29 * scale)
body_font = ImageFont.truetype(args.font, 24 * scale)
heading_font = ImageFont.truetype(args.font, 34 * scale)


def label(x, y, text, font, color):
    draw.text((x * scale, y * scale), text, font=font, fill=color, anchor='mm')


def box(x, y, width, title, detail, planned=False):
    height = 98
    bounds = tuple(int(v * scale) for v in (x, y, x + width, y + height))
    draw.rounded_rectangle(bounds, radius=12 * scale,
                           fill='#fff7e8' if planned else '#ffffff',
                           outline='#bd963f' if planned else '#7b9a8f', width=2 * scale)
    for text, font, offset, color in [(title, title_font, 31, '#173c32'), (detail, body_font, 68, '#526c63')]:
        # 실제 글꼴 경계로 좌우 여백을 보장한다.
        text_bounds = draw.textbbox((0, 0), text, font=font)
        if text_bounds[2] - text_bounds[0] > (width - 56) * scale:
            raise ValueError(f'박스 폭보다 긴 문구: {text}')
        if text_bounds[3] - text_bounds[1] > 35 * scale:
            raise ValueError(f'줄 높이보다 큰 문구: {text}')
        label(x + width / 2, y + offset, text, font, color)


def connector(points, arrow=True):
    pts = [(int(x * scale), int(y * scale)) for x, y in points]
    draw.line(pts, fill='#7b9087', width=2 * scale)
    if arrow:
        x, y = points[-1]
        draw.polygon([(x * scale, y * scale), ((x - 6) * scale, (y - 10) * scale),
                      ((x + 6) * scale, (y - 10) * scale)], fill='#7b9087')


label(520, 46, '데이터 처리와 분석 순서', heading_font, '#173c32')
steps = [
    ('수집 대상 확인', '공개 목록 · 지정 URL'),
    ('수집 정책 확인', 'robots · 요청 간격'),
    ('기사 정보 추출', '제목 · 게시일 · 본문'),
    ('수집 범위 필터', '기간 · 관련어'),
    ('중복 제거', 'URL · 동일 본문'),
    ('수집 범위 점검', '출처별 · 월별'),
]
for i, (title, detail) in enumerate(steps):
    y = 95 + i * 125
    box(260, y, 520, title, detail)
    if i < len(steps) - 1:
        connector([(520, y + 98), (520, y + 125)])

connector([(520, 818), (520, 836), (270, 836), (270, 860)])
connector([(520, 836), (770, 836), (770, 860)])
box(50, 860, 440, '표현 탐색', 'TF-IDF')
box(550, 860, 440, '개념 집계', '유사어 사전')
connector([(770, 958), (770, 985)])
box(550, 985, 440, '언급 비중 비교', '월별 · 전년 동기간')
connector([(270, 958), (270, 1100), (520, 1100)], arrow=False)
connector([(770, 1083), (770, 1100), (520, 1100), (520, 1130)])
box(260, 1130, 520, '근거 수동 검토', '원문 · 문맥 확인')
connector([(520, 1228), (520, 1260)])
box(260, 1260, 520, '핵심 키워드 선정', '후속 단계', planned=True)
connector([(520, 1358), (520, 1390)])
box(260, 1390, 520, '제품 · 리뷰 심층 조사', '아누아 · 경쟁 제품', planned=True)
label(520, 1540, '노란 박스: 자료 확장·검토 후 진행할 단계', body_font, '#6e653e')
output = Path(__file__).with_name('analysis_workflow.png')
image.save(output, optimize=True)
print(f'Saved: {output}')
