import re
from pathlib import Path

QUOTE_LINE_RE = re.compile(r'^"(.+)"\s*—\s*(.+)\s*$')
UNKNOWN_AUTHORS = {'Unknown', 'Неизвестный', 'Unknown Author', 'Автор неизвестен'}

def analyze_file(path: Path):
    lines = [l.strip() for l in path.read_text(encoding='utf-8').splitlines() if l.strip()]
    total = len(lines)
    with_author = 0
    unknown = 0
    parsed = []
    for ln in lines:
        m = QUOTE_LINE_RE.match(ln)
        if m:
            author = m.group(2).strip()
            if author in UNKNOWN_AUTHORS:
                unknown += 1
            else:
                with_author += 1
            parsed.append((m.group(1).strip(), author))
        else:
            # treat as unknown if doesn't match expected format
            unknown += 1
            parsed.append((ln, None))
    return {
        'path': str(path),
        'total': total,
        'with_author': with_author,
        'unknown': unknown,
        'percent_with_author': (with_author / total * 100) if total else 0,
    }


def analyze_all(folder: Path):
    results = []
    for p in sorted(folder.glob('quotes_*.txt')):
        results.append(analyze_file(p))
    return results


if __name__ == '__main__':
    import json, sys
    folder = Path(__file__).resolve().parents[1]
    res = analyze_all(folder)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    # also print a short table
    for r in res:
        print(f"{Path(r['path']).name}: {r['total']} total, {r['with_author']} with author ({r['percent_with_author']:.1f}%)")
