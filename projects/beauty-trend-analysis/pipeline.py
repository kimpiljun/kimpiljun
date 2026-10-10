"""국내 뷰티 기사 수집 -> 텍스트 탐색/기간 비교 -> 브랜드 근거 추출.

각 명령의 사용법: python pipeline.py --help
분석 결과는 수집된 문서의 담론이며 판매량/효능 검증이 아니다.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time
import unicodedata
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qs
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
import pandas as pd
import requests
from sklearn.feature_extraction.text import TfidfVectorizer

ROOT = Path(__file__).resolve().parent
UA = 'BeautyResearchPortfolio/0.1'


def load_config():
    return json.loads((ROOT / 'config.json').read_text(encoding='utf-8'))


def compact(text):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text).lower())


def contains(text, aliases):
    # 한국어 조사 결합을 허용하기 위한 부분 문자열 매칭. 다의어 오탐은 수동 검토한다.
    text = compact(text)
    return any(compact(alias) in text for alias in aliases)


def read_jsonl(path):
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')


def csv(path, rows, columns):
    pd.DataFrame(rows, columns=columns).to_csv(path, index=False, encoding='utf-8-sig')


def canonical(url):
    p = urlsplit(url)
    if p.path == '/news/article.html' and 'no' in parse_qs(p.query):
        return urlunsplit((p.scheme, p.netloc, p.path, 'no=' + parse_qs(p.query)['no'][0], ''))
    return urlunsplit((p.scheme, p.netloc, p.path, p.query, ''))


def json_nodes(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from json_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from json_nodes(child)


def extract_article(content, url, source):
    soup = BeautifulSoup(content, 'html.parser')
    metadata = {}
    for script in soup.find_all('script', type='application/ld+json'):
        try:
            nodes = json_nodes(json.loads(script.get_text()))
            metadata = next((n for n in nodes if n.get('datePublished') and n.get('headline')), metadata)
        except (ValueError, TypeError):
            continue
    title_node = soup.select_one(source['title_selector'])
    title = metadata.get('headline') or (title_node.get_text(' ', strip=True) if title_node else '')
    published = str(metadata.get('datePublished', ''))[:10]
    try:
        date.fromisoformat(published)
    except ValueError:
        raise ValueError('missing_or_invalid_publication_date')
    blocks = soup.select(source['body_selector'])
    for block in blocks:
        for unwanted in block.select('script, style, nav, form, .related-posts'):
            unwanted.decompose()
    body = '\n'.join(b.get_text(' ', strip=True) for b in blocks)
    if not title or len(body) < 150:
        raise ValueError('missing_or_short_article_body')
    return {
        'id': hashlib.sha256(canonical(url).encode()).hexdigest()[:16],
        'source': source['id'], 'role': source['role'], 'url': canonical(url),
        'title': title, 'published_at': published, 'text': body,
        'collected_at': datetime.now(timezone.utc).isoformat(),
        'body_sha256': hashlib.sha256(compact(body).encode()).hexdigest(),
        'extraction_scope': 'article_body' if source['role'] == 'corpus' else 'public_sections_only',
    }


class Fetcher:
    def __init__(self, delay, log_path):
        self.session = requests.Session()
        self.session.headers['User-Agent'] = UA
        self.delay = max(1.0, delay)
        self.last_request = 0.0
        self.rules = {}
        self.log_path = log_path

    def log(self, url, status, detail=''):
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open('a', encoding='utf-8') as f:
            f.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(), 'url': url,
                                'status': status, 'detail': detail}, ensure_ascii=False) + '\n')

    def request(self, url):
        time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
        self.last_request = time.monotonic()
        response = self.session.get(url, timeout=25, allow_redirects=False)
        self.log(url, response.status_code)
        # 리디렉션은 정책 확인 없이 따라가지 않는다. 설정에 최종 URL을 사용한다.
        if response.status_code != 200:
            raise ValueError(f'http_{response.status_code}')
        return response

    def get(self, url):
        parts = urlsplit(url)
        origin = f'{parts.scheme}://{parts.netloc}'
        if origin not in self.rules:
            self.rules[origin] = None
            robots_url = origin + '/robots.txt'
            response = self.request(robots_url)
            raw = response.content.decode('utf-8', errors='replace')
            if not re.search(r'^\s*User-agent\s*:', raw, re.I | re.M):
                raise ValueError('robots_policy_unavailable')
            parser = RobotFileParser(robots_url)
            parser.parse(raw.splitlines())
            self.rules[origin] = parser
        rule = self.rules[origin]
        if rule is None or not rule.can_fetch(UA, url):
            raise ValueError('robots_denied_or_unavailable')
        self.delay = max(self.delay, rule.crawl_delay(UA) or rule.crawl_delay('*') or 0)
        return self.request(url).content


def crawl(args):
    config = load_config()
    folder = ROOT / 'data'
    fetcher = Fetcher(config['delay_seconds'], folder / 'crawl_log.jsonl')
    destination = folder / 'articles.jsonl'
    records = read_jsonl(destination)
    seen = {r['url'] for r in records}
    start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    if start > end or args.pages < 1 or args.limit < 1 or args.page_start < 1:
        raise ValueError('기간/페이지/수집 개수를 확인하세요.')
    for source in config['sources']:
        if args.source != 'all' and source['id'] != args.source:
            continue
        urls = list(source.get('seeds', []))
        try:
            if source.get('listing'):
                for page in range(args.page_start, args.page_start + args.pages):
                    listing = source['listing'].format(page=page)
                    soup = BeautifulSoup(fetcher.get(listing), 'html.parser')
                    for anchor in soup.select('a[href]'):
                        url = canonical(urljoin(listing, anchor['href']))
                        if urlsplit(url).netloc == urlsplit(source['origin']).netloc and re.search(source['article_pattern'], url):
                            urls.append(url)
        except (requests.RequestException, ValueError) as exc:
            fetcher.log(source['origin'], 'listing_failed', str(exc))
        attempts = 0
        for url in dict.fromkeys(urls):
            if url in seen:
                continue
            if attempts >= args.limit:
                break
            attempts += 1
            try:
                content = fetcher.get(url)
                article = extract_article(content, url, source)
                published = date.fromisoformat(article['published_at'])
                if not start <= published <= end:
                    fetcher.log(url, 'excluded', 'outside_date_window')
                    continue
                relevant = contains(article['title'] + ' ' + article['text'], config['relevance_terms'])
                article['relevant'] = relevant
                if not relevant:
                    fetcher.log(url, 'excluded', 'no_relevance_term')
                    continue
                records.append(article)
                seen.add(url)
                write_jsonl(destination, records)  # 중단되어도 이미 수집한 문서 보존
                fetcher.log(url, 'saved', article['id'])
                print(f"saved {source['id']} {article['published_at']} {article['title'][:65]}")
            except (requests.RequestException, ValueError) as exc:
                fetcher.log(url, 'failed', str(exc))
    print(f'Total stored documents: {len(records)}; log: {folder / "crawl_log.jsonl"}')


def deduplicate(records):
    seen_urls, seen_bodies, unique, duplicates = set(), set(), [], []
    for row in sorted(records, key=lambda r: (r['published_at'], r['url'])):
        digest = hashlib.sha256(compact(row['text']).encode()).hexdigest()
        url = canonical(row['url'])
        if url in seen_urls or digest in seen_bodies:
            duplicates.append({'id': row['id'], 'url': row['url'], 'reason': 'same_url_or_exact_body'})
            continue
        seen_urls.add(url)
        seen_bodies.add(digest)
        unique.append(row)
    return unique, duplicates


def keyword_rows(records, keywords):
    totals = Counter((r['source'], r['published_at'][:7]) for r in records)
    counts = Counter()
    for r in records:
        for keyword, aliases in keywords.items():
            if contains(r['title'] + ' ' + r['text'], aliases):
                counts[r['source'], r['published_at'][:7], keyword] += 1
    return [{'source': source, 'month': month, 'keyword': key, 'document_count': counts[source, month, key],
             'total_documents': total, 'share_pct': 100 * counts[source, month, key] / total}
            for (source, month), total in sorted(totals.items()) for key in keywords]


def compare_periods(records, keywords, year, cutoff, minimum):
    end = date.fromisoformat(cutoff)
    if end.year != year:
        raise ValueError('--cutoff은 --year와 같은 연도여야 합니다.')
    previous_end = end.replace(year=year - 1, day=min(end.day, 28)) if end.month == 2 and end.day == 29 else end.replace(year=year - 1)
    result = []
    for source in sorted({r['source'] for r in records}):
        periods = [[r for r in records if r['source'] == source and date(y, 1, 1) <= date.fromisoformat(r['published_at']) <= stop]
                   for y, stop in [(year - 1, previous_end), (year, end)]]
        previous, current = periods
        for keyword, aliases in keywords.items():
            hits = [sum(contains(r['title'] + ' ' + r['text'], aliases) for r in group) for group in periods]
            shares = [100 * n / len(group) if group else None for n, group in zip(hits, periods)]
            result.append({'source': source, 'keyword': keyword, 'previous_n': len(previous), 'current_n': len(current),
                           'previous_hits': hits[0], 'current_hits': hits[1], 'previous_share_pct': shares[0],
                           'current_share_pct': shares[1], 'change_pp': shares[1] - shares[0] if None not in shares else None,
                           'status': 'coverage_review_required' if min(len(previous), len(current)) >= minimum else 'insufficient_sample'})
    return result


def analyze(args):
    config = load_config()
    raw = read_jsonl(ROOT / 'data/articles.jsonl')
    if not raw:
        raise ValueError('수집 데이터가 없습니다. crawl 명령을 먼저 실행하세요.')
    records, duplicates = deduplicate(raw)
    # 화해의 목적 선택 표본은 전체 기사 모집단과 섞지 않는다.
    corpus = [r for r in records if r['role'] == 'corpus' and r['published_at'] <= args.cutoff]
    out = ROOT / 'outputs'
    out.mkdir(exist_ok=True)
    write_jsonl(out / 'clean_articles.jsonl', records)
    csv(out / 'duplicates.csv', duplicates, ['id', 'url', 'reason'])
    monthly = keyword_rows(corpus, config['keywords'])
    csv(out / 'keyword_monthly.csv', monthly, ['source', 'month', 'keyword', 'document_count', 'total_documents', 'share_pct'])
    comparison = compare_periods(corpus, config['keywords'], args.year, args.cutoff, args.min_docs)
    csv(out / 'period_comparison.csv', comparison, ['source', 'keyword', 'previous_n', 'current_n', 'previous_hits', 'current_hits', 'previous_share_pct', 'current_share_pct', 'change_pp', 'status'])
    terms = []
    if corpus:
        vectorizer = TfidfVectorizer(token_pattern=r'(?u)\b[가-힣a-zA-Z][가-힣a-zA-Z0-9]{1,}\b',
                                     stop_words=config['stopwords'], ngram_range=(1, 2), min_df=1 if len(corpus) < 5 else 2)
        try:
            matrix = vectorizer.fit_transform(r['title'] + ' ' + r['text'] for r in corpus)
            vocabulary = vectorizer.get_feature_names_out()
            scores, frequency = matrix.mean(axis=0).A1, (matrix > 0).sum(axis=0).A1
            terms = sorted([{'term': t, 'mean_tfidf': float(s), 'document_count': int(n)} for t, s, n in zip(vocabulary, scores, frequency)],
                           key=lambda r: r['mean_tfidf'], reverse=True)[:150]
        except ValueError as exc:
            if 'empty vocabulary' not in str(exc) and 'After pruning' not in str(exc):
                raise
    csv(out / 'discovered_terms.csv', terms, ['term', 'mean_tfidf', 'document_count'])
    evidence = []
    brand_rows = []
    for r in records:
        if r['published_at'] > args.cutoff:
            continue
        text = r['title'] + ' ' + r['text']
        hits = [k for k, aliases in config['keywords'].items() if contains(text, aliases)]
        for keyword in hits:
            sentence = next((s for s in re.split(r'(?<=[.!?])\s+|\n', text) if contains(s, config['keywords'][keyword])), '')
            evidence.append({'id': r['id'], 'source': r['source'], 'role': r['role'], 'date': r['published_at'],
                             'keyword': keyword, 'title': r['title'], 'evidence_excerpt': sentence[:200], 'url': r['url'], 'manual_review': ''})
        for brand, aliases in config['brands'].items():
            if contains(text, aliases):
                brand_rows.append({'brand': brand, 'id': r['id'], 'date': r['published_at'], 'title': r['title'],
                                   'keywords': '|'.join(hits), 'url': r['url'], 'product_to_investigate': '', 'research_note': ''})
    csv(out / 'keyword_evidence.csv', evidence, ['id', 'source', 'role', 'date', 'keyword', 'title', 'evidence_excerpt', 'url', 'manual_review'])
    csv(out / 'brand_drilldown.csv', brand_rows, ['brand', 'id', 'date', 'title', 'keywords', 'url', 'product_to_investigate', 'research_note'])
    coverage = Counter((r['source'], r['published_at'][:7], r['role']) for r in records)
    csv(out / 'coverage.csv', [{'source': k[0], 'month': k[1], 'role': k[2], 'documents': v} for k, v in sorted(coverage.items())], ['source', 'month', 'role', 'documents'])
    chart = ''
    if monthly:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib import font_manager
        fonts = {font.name for font in font_manager.fontManager.ttflist}
        for font in ['Malgun Gothic', 'NanumGothic', 'AppleGothic']:
            if font in fonts:
                plt.rcParams['font.family'] = font
                break
        plt.rcParams['axes.unicode_minus'] = False
        df = pd.DataFrame(monthly)
        source = sorted(df.source.unique())[0]
        subset = df[df.source == source]
        summary = subset.groupby('keyword')[['document_count', 'total_documents']].sum()
        shares = (100 * summary.document_count / summary.total_documents).sort_values().tail(12)
        fig, ax = plt.subplots(figsize=(9, 6))
        shares.plot.barh(ax=ax, color='#36877d')
        ax.set_xlabel('수집 문서 중 언급 비중 (%)')
        ax.set_title(f'{source} 수집 표본의 키워드 분포 (시장 점유율 아님)')
        fig.tight_layout()
        fig.savefig(out / 'keyword_share.png', dpi=160)
        plt.close(fig)
        chart = '\n![키워드 분포](keyword_share.png)\n'
    warning = '표본 부족: 전년 동기간 비교 및 2026년 핵심 트렌드 확정 불가.'
    if comparison and all(r['status'] != 'insufficient_sample' for r in comparison):
        warning = '최소 문서 수 충족. 기간별 수집 범위·기사 유형·출처 편향 검토 전에는 트렌드를 확정하지 않는다.'
    report = f'''# 뷰티 텍스트 분석 — 수집 표본 점검

- 분석 기준일: {args.cutoff}
- 원본 {len(raw)}건 / 중복 제거 후 {len(records)}건 / 분석 기준일 내 기사 모집단 {len(corpus)}건
- 동일 URL·동일 본문 중복 {len(duplicates)}건 제외. 유사 보도자료 재전재는 추가 수동 검토 필요.
- 아누아 관련 문서 {len(brand_rows)}건. 0건이면 미수집 상태이며 브랜드 관련성이 없다는 뜻이 아니다.
- **{warning}**

## 결과 읽기
1. coverage.csv: 월별·출처별 표본의 공백부터 확인한다.
2. discovered_terms.csv: TF-IDF로 사전에 없는 표현을 탐색한다. 한국어 형태소 분석이 아닌 단어/2단어 기반 기초 분석이다.
3. keyword_monthly.csv: 사람이 만든 개념 사전의 문서 언급 비중이다. 서로 다른 성분과 효능을 같은 유형으로 해석하지 않는다.
4. period_comparison.csv: 전년 1월 1일~같은 월일 대비 올해 비중 차이(%p). 0건인 기간은 0%가 아니라 결측이다.
5. keyword_evidence.csv: 원문 링크로 의미와 오탐을 검토한다. 광고·재전재도 확인한다.
6. brand_drilldown.csv: 트렌드 후보와 연결되는 아누아 제품을 선정하고 심층 조사한다.

## 해석 한계
현재 수집은 제한된 목록 페이지 표본이다. 기간 필터만으로 해당 기간 전체 기사를 수집한 것은 아니다.
화해는 목적 선택된 공개 리포트 일부로, 비교 통계에서 제외하고 별도 맥락 자료로 사용한다.
기사 언급은 소비자 수요·판매량·임상 효능의 증거가 아니다. TF-IDF는 증가율이나 중요도의 객관적 순위가 아니다.
자동으로 핵심 키워드 1개를 확정하지 않는다. 기간·출처·원문 검토 및 소비자 지표 교차 확인이 필요하다.
리뷰는 아직 수집하지 않았다. review-code 명령은 사용자가 확보한 리뷰 JSONL의 평가 속성 분류만 지원한다.
원문과 짧은 근거 발췌는 내부 검증용이다. 포트폴리오에는 집계와 출처 위주로 제시한다.
{chart}
'''
    (out / '분석결과.md').write_text(report, encoding='utf-8')
    print(report[:550])
    print(f'Outputs: {out}')


def review_code(args):
    """실제 확보한 리뷰만 입력. 키워드로 감성을 자동 단정하지 않고 검토표 생성."""
    records = read_jsonl(Path(args.input))
    if not records:
        raise ValueError('입력 리뷰가 없거나 파일을 찾을 수 없습니다.')
    aspects = {'보습': ['보습', '촉촉', '건조', '수분'], '진정': ['진정', '붉은', '홍조'],
               '사용감': ['끈적', '흡수', '밀림', '제형', '산뜻'], '자극 경험': ['따가', '자극', '트러블'],
               '가격': ['가격', '비싸', '저렴', '가성비'], '용기': ['용기', '스포이드', '펌프'], '재구매': ['재구매', '또살']}
    seen, rows = set(), []
    for row in records:
        required = ['source', 'review_id', 'product_id', 'text', 'url', 'published_at']
        if any(not row.get(k) for k in required):
            raise ValueError(f'리뷰 필수 항목: {required}')
        date.fromisoformat(row['published_at'])
        key = (row['source'], row['product_id'], row['review_id'])
        if key in seen:
            continue
        seen.add(key)
        matches = [name for name, aliases in aspects.items() if contains(row['text'], aliases)] or ['미분류']
        for aspect in matches:
            rows.append({k: row[k] for k in required} | {'aspect': aspect, 'sentiment_manual': '', 'evidence_manual': '', 'reviewed': False})
    out = ROOT / 'outputs'
    out.mkdir(exist_ok=True)
    csv(out / 'review_coding.csv', rows, required + ['aspect', 'sentiment_manual', 'evidence_manual', 'reviewed'])
    print(f'{len(seen)}개 리뷰의 속성 검토표 생성. 감성은 원문을 읽고 수동 코딩하세요.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    c = sub.add_parser('crawl', help='robots 확인 후 공개 기사 소량 수집; 로그/재실행 지원')
    c.add_argument('--source', choices=['all'] + [s['id'] for s in load_config()['sources']], default='all')
    c.add_argument('--page-start', type=int, default=1)
    c.add_argument('--pages', type=int, default=2)
    c.add_argument('--limit', type=int, default=20, help='출처별 최대 상세 페이지 요청 수')
    c.add_argument('--start', default='2025-01-01')
    c.add_argument('--end', default=date.today().isoformat())
    c.set_defaults(func=crawl)
    a = sub.add_parser('analyze', help='기사 텍스트 탐색, 동기간 비교, 브랜드 조사표 생성')
    a.add_argument('--year', type=int, default=2026)
    a.add_argument('--cutoff', default='2026-10-11')
    a.add_argument('--min-docs', type=int, default=30, help='통계적 보장이 아닌 최소 표본 경고 기준')
    a.set_defaults(func=analyze)
    r = sub.add_parser('review-code', help='별도로 확보한 리뷰 JSONL을 속성별 검토표로 변환')
    r.add_argument('--input', required=True)
    r.set_defaults(func=review_code)
    args = parser.parse_args()
    try:
        args.func(args)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Error: {exc}\n')


if __name__ == '__main__':
    main()
