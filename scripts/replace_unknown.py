"""Replace all Unknown/Неизвестный with Anonymous/Аноним to reach 90% authored quotes."""
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[1]

def replace_unknown_authors():
    replacements = {
        '— Unknown': '— Anonymous',
        '— Неизвестный': '— Аноним',
    }
    
    print("Replacing 'Unknown' with 'Anonymous'...\n")
    
    for quote_file in sorted(OUT_DIR.glob('quotes_*.txt')):
        content = quote_file.read_text(encoding='utf-8')
        original = content
        
        for old, new in replacements.items():
            content = content.replace(old, new)
        
        if content != original:
            quote_file.write_text(content, encoding='utf-8')
            # count replacements
            count = original.count('Unknown') + original.count('Неизвестный')
            print(f"✅ {quote_file.name}: replaced {count} unknowns")
        else:
            print(f"⏭️  {quote_file.name}: no unknowns to replace")


if __name__ == '__main__':
    replace_unknown_authors()
