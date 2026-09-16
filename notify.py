"""Send one WeChat template notification; never print credentials or raw HTTP errors."""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo
from render import validate


def request_json(url, payload=None):
    raw = None if payload is None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(url, data=raw, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        # Request URLs contain access tokens. Never include exception strings.
        raise RuntimeError('Request failed; delivery may be uncertain. Check WeChat before retrying.') from None


def build_payload(data, page_base, openid, template_id):
    day, total = validate(data)
    return {
        'touser': openid,
        'template_id': template_id,
        'url': page_base.rstrip('/') + '/' + day.isoformat() + '.html',
        'data': {
            'date': {'value': day.isoformat()},
            'summary': {'value': f'{len(data["sections"])} 个新闻板块，共 {total} 条精选'},
            'remark': {'value': '点击阅读日报，页面顶部可下载 Word 文档'},
        },
    }


def main():
    required = ['WECHAT_APP_ID', 'WECHAT_APP_SECRET', 'WECHAT_OPEN_ID', 'WECHAT_TEMPLATE_ID', 'PAGES_URL']
    missing = [key for key in required if not os.environ.get(key)]
    if missing:
        raise ValueError('Missing settings: ' + ', '.join(missing))
    files = sorted(Path('digests').glob('????-??-??.json'))
    if not files:
        raise ValueError('No digest available')
    data = json.loads(files[-1].read_text(encoding='utf-8'))
    now = datetime.now(ZoneInfo('America/New_York'))
    generated = datetime.fromisoformat(data['generated_at'])
    if data['date'] != now.date().isoformat() or not timedelta(0) <= now - generated <= timedelta(hours=6):
        raise ValueError('Refusing to send an old or future digest')
    payload = build_payload(data, os.environ['PAGES_URL'], os.environ['WECHAT_OPEN_ID'], os.environ['WECHAT_TEMPLATE_ID'])
    # Only contact the actual Pages host for the public report check.
    page = urllib.parse.urlsplit(payload['url'])
    if page.scheme != 'https' or not page.hostname or not page.hostname.endswith('.github.io'):
        raise ValueError('PAGES_URL must be the HTTPS GitHub Pages address')
    with urllib.request.urlopen(payload['url'], timeout=30) as response:
        if data['date'] not in response.read().decode('utf-8'):
            raise ValueError('Published digest is not ready')
    word_url = payload['url'].removesuffix('.html') + '.docx'
    with urllib.request.urlopen(word_url, timeout=30) as response:
        if response.read(4) != b'PK\x03\x04':
            raise ValueError('Published Word document is not ready')
    params = urllib.parse.urlencode({'grant_type': 'client_credential', 'appid': os.environ['WECHAT_APP_ID'], 'secret': os.environ['WECHAT_APP_SECRET']})
    result = request_json('https://api.weixin.qq.com/cgi-bin/token?' + params)
    if not result.get('access_token'):
        raise RuntimeError('WeChat authorization failed; error code ' + str(result.get('errcode', 'unknown')))
    endpoint = 'https://api.weixin.qq.com/cgi-bin/message/template/send?' + urllib.parse.urlencode({'access_token': result['access_token']})
    result = request_json(endpoint, payload)
    if result.get('errcode') != 0:
        raise RuntimeError('WeChat rejected notification; error code ' + str(result.get('errcode', 'unknown')))
    print('WeChat accepted the notification. Confirm receipt on the phone for the first test.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Only our explicitly safe messages reach logs.
        if isinstance(exc, (ValueError, RuntimeError)):
            print(str(exc), file=sys.stderr)
        else:
            print('Notification failed: ' + type(exc).__name__, file=sys.stderr)
        sys.exit(1)
