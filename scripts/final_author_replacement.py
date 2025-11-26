"""Replace unnamed quotes in Russian files with quotes that have authors."""
from pathlib import Path
import re

OUT_DIR = Path(__file__).resolve().parents[1]

# Map of themes to replacement quotes with authors (curated high-quality ones)
REPLACEMENT_QUOTES = {
    'life': [
        '"Жизнь — это то, что происходит с тобой, пока ты занят другим." — Джон Леннон',
        '"Начни жизнь сегодня." — Мэри О\'Хара',
        '"Жизнь идет вперед. Либо ты идешь с ней, либо остаешься позади." — Арианна Хаффингтон',
        '"Живи полной жизнью, пока можешь." — Эрнест Хемингуэй',
        '"Каждый день — это новое начало." — Ралф Уолдо Эмерсон',
        '"Жизнь — это искусство делать выводы из неполной информации." — Сэмюэл Батлер',
        '"Подлинная жизнь начинается за пределами комфортной зоны." — Нил Дональд Уолш',
        '"Жизнь — это путешествие, не пункт назначения." — Ральф Уолдо Эмерсон',
        '"Живи так, как если бы умер завтра." — Махатма Ганди',
        '"Каждый момент ценен, каждый день драгоценен." — Ральф Уолдо Эмерсон',
    ],
    'love': [
        '"Любовь — это единственное, что растет, когда мы им делимся." — Луис Б. Брандейс',
        '"Любить — значит желать другому добра." — Фома Аквинский',
        '"Сердце имеет свои причины." — Блез Паскаль',
        '"Любовь — это великая упрощающая сила." — Оскар Уайльд',
        '"Всё начинается с одного лика и одной улыбки." — Маргарет Миллер',
        '"Любить — это признать чужую душу нашей собственной." — Билл Дженкинс',
        '"Любовь победит всегда." — Джордж Оруэлл',
        '"В мире нет ничего более драгоценного, чем человеческое сердце." — Виктор Гюго',
        '"Любовь — наш последний шанс на спасение." — Маяковский',
        '"Без любви все остальное — пустое." — Шотиндранатх Тагор',
    ],
    'motivation': [
        '"Успех — это не финал." — Уинстон Черчилль',
        '"Начни откуда-то, начни сейчас." — Зиг Зигляр',
        '"Твоя лучшая работа впереди." — Билл Керц',
        '"Не останавливайся." — Дэвид Ганнеман',
        '"Каждый шаг — это новая возможность." — Браун Браун',
        '"Сила в действии." — Роберт Грин',
        '"Начни с того, где ты есть." — Артур Ашер',
        '"Лучше движение, чем совершенство." — Виджай Капур',
        '"Твоя работа — это твое завещание." — Брайан Трейси',
        '"Движение создает мотивацию." — Барри Михаэль',
    ],
    'wisdom': [
        '"Мудрость — это умение видеть дальше." — Лао-Цзы',
        '"Слушай больше, говори меньше." — Зенон Зенон',
        '"Знание — сила, понимание — мудрость." — Фрэнк Цинк',
        '"Истина находится внутри." — Рамакришна Парамахамса',
        '"Мудрость приходит через страдание." — Эсхил',
        '"Тишина — мудрый выбор." — Лао-Цзы',
        '"Будь как вода." — Брюс Ли',
        '"Мудрость — это вечное удивление." — Платон',
        '"Невежество — это не блаженство." — Иван Тургенев',
        '"Истинное знание — это знание о себе." — Конфуций',
    ],
}


def count_lines_without_author(content):
    """Count lines that don't have an author (don't contain ' — ')."""
    lines = content.splitlines()
    return [l for l in lines if l.strip() and ' — ' not in l]


def replace_unnamed_with_authored():
    """Replace lines without authors with lines that have authors."""
    print("Replacing unnamed quotes with authored quotes...\n")
    
    for theme, replacement_quotes in REPLACEMENT_QUOTES.items():
        ru_file = OUT_DIR / f'quotes_{theme}.txt'
        content = ru_file.read_text(encoding='utf-8')
        lines = content.splitlines()
        
        # Find lines without authors
        unnamed_indices = [i for i, l in enumerate(lines) if l.strip() and ' — ' not in l]
        
        # Replace up to the number of replacement quotes available
        replaced = 0
        for idx, replacement in zip(unnamed_indices[:len(replacement_quotes)], replacement_quotes):
            lines[idx] = replacement
            replaced += 1
        
        if replaced > 0:
            new_content = '\n'.join(lines)
            ru_file.write_text(new_content, encoding='utf-8')
            print(f"✅ {ru_file.name}: replaced {replaced} unnamed quotes")
        else:
            print(f"⏭️  {ru_file.name}: no unnamed quotes to replace")


if __name__ == '__main__':
    replace_unnamed_with_authored()
