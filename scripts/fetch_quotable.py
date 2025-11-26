"""Fetch quotes from quotable.io and append to local files.
This script fetches English quotes for the themes: life, love, motivation, wisdom
and appends them to the corresponding `quotes_<theme>_en.txt` files.

It will try to fetch up to `target_per_file` quotes for each file while avoiding duplicates.
"""
import requests
from pathlib import Path
import time
import random

API_BASE = 'https://api.quotable.io'
TARGET_PER_FILE = 250
OUT_DIR = Path(__file__).resolve().parents[1]

THEME_TAGS = {
    'life': 'life',
    'love': 'love',
    'motivation': 'inspirational',
    'wisdom': 'wisdom',
}


def load_existing(path: Path):
    if not path.exists():
        return set()
    lines = [l.strip() for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]
    quotes = set()
    for ln in lines:
        # naive extract of the quote text inside quotes
        if ln.startswith('"'):
            end = ln.rfind('"')
            if end > 0:
                quotes.add(ln[1:end])
    return quotes


def fetch_quotes(tag, skip, limit=20):
    # use pagination, skip is page*limit
    params = {'tags': tag, 'limit': limit, 'page': skip}
    resp = requests.get(f'{API_BASE}/quotes', params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data.get('results', []), data.get('totalPages', 1)


def main():
    for theme, tag in THEME_TAGS.items():
        out_path = OUT_DIR / f'quotes_{theme}_en.txt'
        existing = load_existing(out_path)
        needed = TARGET_PER_FILE
        added = 0
        page = 1
        seen_ids = set()
        print(f'Processing {out_path} — existing quotes: {len(existing)}')
        while added < needed:
            try:
                results, total_pages = fetch_quotes(tag, page, limit=20)
            except Exception as e:
                print('Fetch error:', e)
                time.sleep(2)
                continue
            if not results:
                break
            for item in results:
                q = item.get('content')
                author = item.get('author') or 'Anonymous'
                if not q or q in existing:
                    continue
                line = f'"{q}" — {author}'
                out_path.write_text('\n'.join(list(out_path.read_text(encoding="utf-8").splitlines()) + [line]), encoding='utf-8')
                existing.add(q)
                added += 1
                print(f'  + added ({added}/{needed}): {q[:60]}... — {author}')
                if added >= needed:
                    break
            page += 1
            if page > total_pages:
                # shuffle and retry from first page with different limit to get more variation
                page = 1
                time.sleep(1 + random.random())
        print(f'Finished {out_path}: added {added} quotes')


if __name__ == '__main__':
    main()
