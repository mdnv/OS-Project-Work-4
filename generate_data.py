"""Create input files once, outside all measurements."""
from pathlib import Path
import argparse

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--count', type=int, default=10_000_000)
    args = parser.parse_args()
    if args.count <= 0:
        parser.error('--count must be positive')
    data = ROOT / 'data'
    www = ROOT / 'www'
    data.mkdir(exist_ok=True)
    www.mkdir(exist_ok=True)
    with (data / 'numbers.txt').open('w', encoding='utf-8') as file:
        for start in range(1, args.count + 1, 100_000):
            stop = min(start + 100_000, args.count + 1)
            file.writelines(f'{value}\n' for value in range(start, stop))
    for index in range(1, 21):
        (www / f'file{index:02d}.txt').write_bytes(b'x' * 4096)
    (data / 'urls.txt').write_text(
        ''.join(f'http://127.0.0.1:8000/file{i:02d}.txt\n' for i in range(1, 21)),
        encoding='utf-8',
    )
    print(f'Created: data/numbers.txt; integers: {args.count:,}')
    print(f'Expected sum for generated data: {args.count * (args.count + 1) // 2}')
    print('Created: data/urls.txt (20 URLs), www/ (20 files, 4096 bytes each)')


if __name__ == '__main__':
    main()
