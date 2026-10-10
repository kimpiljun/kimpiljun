"""합성 문서로 파싱/통계만 검증. 실제 분석 자료에 합치지 않는다."""
import unittest
from pipeline import compare_periods, contains, deduplicate, extract_article, keyword_rows


def doc(n, text, day='2026-03-01', source='test'):
    return {'id': str(n), 'url': f'https://example.org/{n}', 'text': text,
            'title': '테스트 문서', 'source': source, 'published_at': day}


class PipelineTests(unittest.TestCase):
    def test_date_and_body_exclude_navigation(self):
        html = '<header>2026.10.11 PDRN</header><h2>제목</h2><script type="application/ld+json">{"headline":"실제 제목","datePublished":"2025-02-03T12:00:00+09:00"}</script><div id="body">' + ('보습 관련 기사. ' * 30) + '</div>'
        row = extract_article(html.encode(), 'https://example.org/1', {'id': 'test', 'role': 'corpus', 'title_selector': 'h2', 'body_selector': '#body'})
        self.assertEqual(row['published_at'], '2025-02-03')
        self.assertNotIn('PDRN', row['text'])
        self.assertEqual(row['title'], '실제 제목')

    def test_undated_rejected(self):
        with self.assertRaisesRegex(ValueError, 'publication_date'):
            extract_article(b'<h2>no date</h2>', 'https://example.org/1', {'title_selector': 'h2', 'body_selector': 'article'})

    def test_unicode_alias(self):
        self.assertTrue(contains('피부 장벽과 ＰＤＲＮ', ['pdrn']))
        self.assertTrue(contains('피부 장벽', ['피부장벽']))

    def test_repeated_mentions_count_once(self):
        row = keyword_rows([doc(1, 'PDRN PDRN'), doc(2, '보습')], {'PDRN': ['pdrn']})[0]
        self.assertEqual(row['document_count'], 1)
        self.assertEqual(row['share_pct'], 50)

    def test_deduplication(self):
        unique, duplicates = deduplicate([doc(1, '같은 본문'), doc(2, '같은  본문'), doc(3, '다른 본문')])
        self.assertEqual(len(unique), 2)
        self.assertEqual(len(duplicates), 1)

    def test_missing_baseline(self):
        row = compare_periods([doc(1, '보습')], {'보습': ['보습']}, 2026, '2026-10-11', 30)[0]
        self.assertIsNone(row['previous_share_pct'])
        self.assertIsNone(row['change_pp'])
        self.assertEqual(row['status'], 'insufficient_sample')

    def test_same_period_and_separate_source(self):
        data = [doc(1, '보습', '2025-02-01'), doc(2, '기타', '2025-02-02'), doc(3, '보습', '2025-12-01'), doc(4, '보습', '2026-02-01'), doc(5, '보습', source='other')]
        row = next(r for r in compare_periods(data, {'보습': ['보습']}, 2026, '2026-10-11', 1) if r['source'] == 'test')
        self.assertEqual(row['previous_n'], 2)
        self.assertEqual(row['current_n'], 1)
        self.assertEqual(row['change_pp'], 50)


if __name__ == '__main__':
    unittest.main()
