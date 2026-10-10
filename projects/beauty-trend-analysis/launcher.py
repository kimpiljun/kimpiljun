"""더블클릭 실행기의 메뉴와 진행 상태."""
import subprocess
import sys
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(*args):
    subprocess.run([sys.executable, '-u', '-X', 'utf8', str(ROOT / 'pipeline.py'), *args], cwd=ROOT, check=True)


def main():
    print('\n  뷰티 트렌드 · 아누아 리서치\n', flush=True)
    print('  1. 저장된 데이터 분석 후 결과 화면 열기 (기본)')
    print('  2. 새 기사 수집 → 분석 → 결과 화면 열기')
    print('  0. 종료\n')
    while True:
        choice = input('번호를 입력하세요 [Enter = 1]: ').strip() or '1'
        if choice in {'0', '1', '2'}:
            break
        print('0, 1, 2 중에서 선택해주세요.')
    if choice == '0':
        return
    if choice == '1' and not (ROOT / 'data/articles.jsonl').exists():
        print('\n저장된 데이터가 없습니다. start.bat을 다시 실행해 2번으로 먼저 수집해주세요.')
        input('\nEnter를 누르면 종료합니다. ')
        return
    if choice == '2':
        print('\n[1/3] 공개 기사 수집 중 · 최소 2초 간격 · 저장된 URL은 건너뜁니다.\n', flush=True)
        run('crawl', '--pages', '2', '--limit', '20', '--start', '2025-01-01', '--end', '2026-10-11')
    print('\n[2/3] 저장된 자료 분석 중...\n', flush=True)
    run('analyze', '--year', '2026', '--cutoff', '2026-10-11')
    print('\n[3/3] 브라우저 결과 화면 생성 중...\n', flush=True)
    from dashboard import build_dashboard
    output = build_dashboard()
    opened = webbrowser.open(output.as_uri())
    print('\n완료! 브라우저에서 차트와 기사 목록을 확인하세요.' if opened else '\nHTML 파일을 직접 더블클릭해서 열어주세요.')
    print(f'파일 위치: {output}')
    input('\nEnter를 누르면 실행 창이 닫힙니다. ')


if __name__ == '__main__':
    try:
        main()
    except (OSError, subprocess.CalledProcessError, ImportError, ValueError) as exc:
        print(f'\n실행 오류: {exc}\nREADME.md의 설치 방법과 위 오류 내용을 확인해주세요.')
        input('\nEnter를 누르면 종료합니다. ')
        sys.exit(1)
