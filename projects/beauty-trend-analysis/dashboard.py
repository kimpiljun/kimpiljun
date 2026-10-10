"""외부 서버 없이 열리는 인터랙티브 HTML 결과 화면 생성."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import webbrowser

from pipeline import ROOT, contains, load_config, read_jsonl, deduplicate


def build_dashboard():
    config = load_config()
    raw = read_jsonl(ROOT / 'data/articles.jsonl')
    records, _ = deduplicate(raw)
    documents = []
    for row in records:
        text = row['title'] + ' ' + row['text']
        documents.append({key: row[key] for key in ['id', 'title', 'source', 'role', 'url', 'published_at']} |
                         {'keywords': [key for key, aliases in config['keywords'].items() if contains(text, aliases)],
                          'anua': contains(text, config['brands']['아누아'])})
    payload = json.dumps({'documents': documents, 'keywords': list(config['keywords']),
                          'generated': datetime.now().strftime('%Y-%m-%d %H:%M'),
                          'raw_count': len(raw)}, ensure_ascii=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    template = (ROOT / 'dashboard_template.html').read_text(encoding='utf-8')
    output = ROOT / 'outputs/대시보드.html'
    output.parent.mkdir(exist_ok=True)
    output.write_text(template.replace('__DATA_JSON__', payload), encoding='utf-8')
    print(f'화면 생성 완료: {output}', flush=True)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--open', action='store_true', help='생성 후 기본 브라우저에서 열기')
    args = parser.parse_args()
    output = build_dashboard()
    if args.open:
        webbrowser.open(output.as_uri())
