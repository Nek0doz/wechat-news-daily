"""Validate source-backed digest JSON and render escaped, static HTML."""
import argparse
import html
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

LEGACY_SECTIONS = ['世界新闻', '中国新闻', '深圳新闻', 'CS2 游戏资讯']
SECTIONS = ['世界新闻', '美国新闻', '宾夕法尼亚州新闻', 'State College 新闻', '中国新闻', '深圳新闻', 'CS2 游戏资讯']


def validate(data):
    day = date.fromisoformat(data['date'])
    generated = datetime.fromisoformat(data['generated_at'])
    if generated.tzinfo is None:
        raise ValueError('generated_at must include timezone')
    names = [s['name'] for s in data['sections']]
    legacy_archive = day <= date(2026, 9, 16) and names == LEGACY_SECTIONS
    if names != SECTIONS and not legacy_archive:
        raise ValueError('Exactly seven ordered sections are required')
    seen = set()
    total = 0
    for section in data['sections']:
        items = section['items']
        if not isinstance(items, list) or len(items) > 3:
            raise ValueError('At most three items per section')
        if not items and not section.get('note'):
            raise ValueError('Empty sections need an explanatory note')
        for item in items:
            for key, maximum in [('summary', 220), ('source', 80)]:
                if not isinstance(item[key], str) or not 1 <= len(item[key].strip()) <= maximum:
                    raise ValueError(f'Invalid {key}')
            u = urlsplit(item['url'])
            if u.scheme != 'https' or not u.netloc or u.username or u.password:
                raise ValueError('Use HTTPS source links without credentials')
            canonical = u._replace(fragment='').geturl()
            if canonical in seen:
                raise ValueError('Duplicate source link')
            seen.add(canonical)
            stamp = item['published_at']
            if len(stamp) == 10:
                # A source exposing only the date must not acquire an invented clock time.
                offset = item.get('published_timezone', '')
                if not offset:
                    raise ValueError('Date-only sources need a source timezone offset')
                midnight = datetime.fromisoformat(stamp + 'T00:00:00' + offset)
                if midnight.tzinfo is None or midnight.date() != generated.astimezone(midnight.tzinfo).date():
                    raise ValueError('Date-only sources must be from the current source-local day')
            else:
                published = datetime.fromisoformat(stamp)
                if published.tzinfo is None or not generated - timedelta(hours=24) <= published <= generated:
                    raise ValueError('Source publication must be within the preceding 24 hours')
            total += 1
    if not total:
        raise ValueError('No verified articles: do not publish an empty digest')
    return day, total


def render(data):
    day, count = validate(data)
    esc = html.escape
    sections = []
    for section in data['sections']:
        articles = ''.join(
            '<article><p>' + esc(i['summary']) + '</p><a href="' + esc(i['url'], quote=True)
            + '" target="_blank" rel="noopener noreferrer">' + esc(i['source'])
            + ' · 阅读原文 ↗</a></article>' for i in section['items'])
        note = '<p class="note">' + esc(section['note']) + '</p>' if section.get('note') else ''
        sections.append('<section><h2>' + esc(section['name']) + '</h2>' + articles + note + '</section>')
    return ('''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>每日新闻 · ''' + day.isoformat() + '''</title>
<style>
:root{color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f6f4ef;color:#182a32;font-family:system-ui,"Microsoft YaHei",sans-serif;line-height:1.8}
main{max-width:760px;margin:auto;padding:42px 22px}header{border-bottom:2px solid #182a32;padding-bottom:24px}
.eyebrow{font-size:12px;letter-spacing:3px;color:#617078}h1{font-size:36px;line-height:1.3;margin:12px 0}header p,footer,.note{color:#617078;font-size:13px}
section{padding-top:24px}h2{font-size:20px;margin:0 0 12px}article{background:white;padding:18px 22px;margin:10px 0;border:1px solid #e5e6e1;border-radius:10px}
article p{margin:0 0 10px;font-size:16px}a{color:#006d70;text-decoration:none;font-size:13px}a:hover{text-decoration:underline}footer{margin-top:32px;padding-top:16px;border-top:1px solid #ddd}
@media(max-width:480px){main{padding:26px 16px}h1{font-size:30px}article{padding:16px}}
</style><main><header><div class="eyebrow">DAILY NEWS BRIEF</div><h1>每日新闻</h1><p>'''
    + day.isoformat() + ' · 纽约日期 · ' + str(count) + ' 条精选</p></header>' + ''.join(sections) + '''
<footer>概要由 AI 根据所列来源整理；详情以原文为准。<br>覆盖生成前 24 小时，未更新的板块不以旧闻填充。</footer></main></html>''')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input-dir', default='digests')
    parser.add_argument('--output-dir', default='site')
    args = parser.parse_args()
    files = sorted(Path(args.input_dir).glob('????-??-??.json'))
    if not files:
        raise ValueError('No daily digest has been supplied')
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    for path in files:
        data = json.loads(path.read_text(encoding='utf-8'))
        if path.stem != data['date']:
            raise ValueError('Filename must equal digest date')
        page = render(data)
        (out / (path.stem + '.html')).write_text(page, encoding='utf-8')
    (out / 'index.html').write_text(page, encoding='utf-8')
    (out / '.nojekyll').touch()
    print('Validated and rendered', len(files), 'daily digest(s)')


if __name__ == '__main__':
    main()
