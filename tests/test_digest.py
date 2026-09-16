import copy
import unittest
from render import SECTIONS, LEGACY_SECTIONS, render, validate
from notify import build_payload


def fixture():
    return {'date': '2026-09-16', 'generated_at': '2026-09-16T09:00:00-04:00', 'sections': [
        {'name': name, 'items': [{'summary': '测试概要，包含 <script> 和引号。', 'source': '测试来源',
          'url': 'https://example.org/' + str(i), 'published_at': '2026-09-16T08:00:00-04:00'}]}
        for i, name in enumerate(SECTIONS)]}


class DigestTests(unittest.TestCase):
    def test_html_escapes_untrusted_content(self):
        page = render(fixture())
        self.assertNotIn('<script>', page)
        self.assertIn('&lt;script&gt;', page)

    def test_rejects_stale_and_future_articles(self):
        for stamp in ['2026-09-14T08:00:00-04:00', '2026-09-17T08:00:00-04:00']:
            data = fixture(); data['sections'][0]['items'][0]['published_at'] = stamp
            with self.assertRaises(ValueError): validate(data)

    def test_rejects_unsafe_and_duplicate_urls(self):
        for url in ['javascript:alert(1)', 'https://secret@example.org/a', 'https://example.org/1']:
            data = fixture(); data['sections'][0]['items'][0]['url'] = url
            with self.assertRaises(ValueError): validate(data)

    def test_empty_section_requires_disclosure(self):
        data = fixture(); data['sections'][0]['items'] = []
        with self.assertRaises(ValueError): validate(data)
        data['sections'][0]['note'] = '过去24小时未找到可核实的重要更新。'
        validate(data)

    def test_notification_points_to_immutable_dated_page(self):
        payload = build_payload(fixture(), 'https://example.github.io/news/', 'recipient', 'template')
        self.assertEqual(payload['url'], 'https://example.github.io/news/2026-09-16.html')
        self.assertEqual(set(payload['data']), {'date', 'summary', 'remark'})
        self.assertEqual(payload['data']['summary']['value'], '7 个新闻板块，共 7 条精选')

    def test_seven_section_migration_keeps_archives_readable(self):
        data = fixture()
        page = render(data)
        for name in ['美国新闻', '宾夕法尼亚州新闻', 'State College 新闻']:
            self.assertIn('<h2>' + name + '</h2>', page)
        by_name = {s['name']: s for s in data['sections']}
        data['sections'] = [by_name[name] for name in LEGACY_SECTIONS]
        self.assertEqual(validate(data)[1], 4)
        data['date'] = '2026-09-17'
        data['generated_at'] = '2026-09-17T07:00:00-04:00'
        with self.assertRaisesRegex(ValueError, 'seven ordered sections'):
            validate(data)
        data['sections'] = [by_name[name] for name in SECTIONS]
        self.assertEqual(validate(data)[1], 7)
        data['sections'][1], data['sections'][2] = data['sections'][2], data['sections'][1]
        with self.assertRaisesRegex(ValueError, 'seven ordered sections'):
            validate(data)

    def test_date_only_source_does_not_invent_clock_time(self):
        data = fixture(); item = data['sections'][0]['items'][0]
        item['published_at'] = '2026-09-16'
        with self.assertRaises(ValueError): validate(data)
        item['published_timezone'] = '+08:00'
        validate(data)
        item['published_at'] = '2026-09-15'
        with self.assertRaises(ValueError): validate(data)


if __name__ == '__main__': unittest.main()
