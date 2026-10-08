"""Linux/CPython benchmark. Preparation is excluded; worker lifecycle is included."""
import argparse
import csv
import multiprocessing as mp
import platform
import statistics
import subprocess
import sys
import threading
import time
from array import array
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent
NUMBERS = array('q')
WORKERS = 4
REPEATS = 3
CONTEXT = mp.get_context('fork') if sys.platform == 'linux' else None


def sum_range(bounds):
    start, stop = bounds
    total = 0
    for index in range(start, stop):
        total += NUMBERS[index]
    return total


def cpu_single(bounds):
    return sum_range((0, len(NUMBERS)))


def cpu_threads(bounds):
    results = [None] * WORKERS

    def worker(index, part):
        results[index] = sum_range(part)

    threads = [threading.Thread(target=worker, args=(i, part))
               for i, part in enumerate(bounds)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    return sum(results)


def cpu_processes(bounds):
    # Linux fork inherits the read-only array; only index pairs are sent to workers.
    # No live benchmark threads remain when fork is called.
    pool = CONTEXT.Pool(WORKERS)
    try:
        results = pool.map(sum_range, bounds, chunksize=1)
        pool.close()
        pool.join()
    except BaseException:
        pool.terminate()
        pool.join()
        raise
    return sum(results)


def download(url):
    with urlopen(url, timeout=15) as response:
        return len(response.read())


def net_single(urls):
    return [download(url) for url in urls]


def net_threads(urls):
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        return list(pool.map(download, urls))


def net_processes(urls):
    with ProcessPoolExecutor(max_workers=WORKERS, mp_context=CONTEXT) as pool:
        return list(pool.map(download, urls, chunksize=1))


def measure_group(task, methods, argument, expected, cores):
    times = {name: [] for name, _, _ in methods}
    for repeat in range(REPEATS):
        # Rotate method order, so the same method is not always first.
        ordered = methods[repeat:] + methods[:repeat]
        for name, _, function in ordered:
            start = time.perf_counter()
            result = function(argument)
            elapsed = time.perf_counter() - start
            if result != expected:
                raise RuntimeError(f'{task}/{name}: result differs from reference')
            times[name].append(elapsed)
            print(f'{task:7s} | {name:20s} | run {repeat + 1}: {elapsed:.6f}s | OK', flush=True)
    baseline = statistics.median(times[methods[0][0]])
    rows = []
    for name, workers, _ in methods:
        samples = times[name]
        median = statistics.median(samples)
        rows.append({
            'task': task, 'method': name, 'workers': workers,
            'nproc': cores, 'repeats': REPEATS,
            'run1_s': samples[0], 'run2_s': samples[1], 'run3_s': samples[2],
            'median_s': median, 'speedup': baseline / median,
            'result': expected if task == 'CPU' else sum(expected),
        })
    return rows


def save_results(rows, task, metadata):
    folder = ROOT / 'results'
    folder.mkdir(exist_ok=True)
    csv_path = folder / f'{task}_results.csv'
    md_path = folder / f'{task}_results.md'
    with csv_path.open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    lines = [f'# Результаты: {task}', '', *metadata, '',
             '| Задача | Метод | Исполнители | nproc | Повторы | 1, с | 2, с | 3, с | Медиана, с | Ускорение |',
             '|---|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in rows:
        lines.append(
            f"| {row['task']} | {row['method']} | {row['workers']} | {row['nproc']} "
            f"| {row['repeats']} | {row['run1_s']:.6f} | {row['run2_s']:.6f} "
            f"| {row['run3_s']:.6f} | {row['median_s']:.6f} | {row['speedup']:.2f}x |")
    md_path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n' + '\n'.join(lines), flush=True)
    print(f'\nSaved: {csv_path.relative_to(ROOT)}, {md_path.relative_to(ROOT)}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('task', choices=['cpu', 'network'])
    parser.add_argument('--numbers', type=Path, default=ROOT / 'data' / 'numbers.txt')
    parser.add_argument('--urls', type=Path, default=ROOT / 'data' / 'urls.txt')
    parser.add_argument('--network-note', default='Local ThreadingHTTPServer; delay=0.2s per response')
    args = parser.parse_args()
    if sys.platform != 'linux' or platform.python_implementation() != 'CPython':
        parser.error('Use CPython in Ubuntu through SSH, not the macOS terminal locally.')
    cores = int(subprocess.check_output(['nproc'], text=True).strip())
    metadata = [f'- CPython: {platform.python_version()}; ОС: {platform.platform()}',
                f'- Архитектура: {platform.machine()}; nproc: {cores}; повторы: {REPEATS}.',
                '- Процессы: fork. Запуск, передача результатов и завершение исполнителей включены в замер.']
    if args.task == 'cpu':
        print('Loading numbers before timing...', flush=True)
        with args.numbers.open(encoding='utf-8') as file:
            NUMBERS.extend(int(line) for line in file)
        if not NUMBERS:
            raise ValueError('numbers.txt is empty')
        if len(NUMBERS) != 10_000_000:
            print(f'WARNING: expected 10,000,000 integers; found {len(NUMBERS):,}.', flush=True)
        n = len(NUMBERS)
        bounds = [(n * i // WORKERS, n * (i + 1) // WORKERS) for i in range(WORKERS)]
        expected = sum(NUMBERS)  # Correctness reference and warm-up, outside timing.
        metadata += [f'- Чисел: {n:,}; контрольная сумма: {expected}.',
                     '- Чтение файла, преобразование строк, разбиение и контрольная сумма исключены из замера.',
                     '- Во всех методах: одинаковый Python-цикл сложения; массив array(q), только чтение.']
        print(f'Numbers: {n:,}; reference sum: {expected}', flush=True)
        methods = [('single', 1, cpu_single), ('threading', WORKERS, cpu_threads),
                   ('multiprocessing', WORKERS, cpu_processes)]
        rows = measure_group('CPU', methods, bounds, expected, cores)
    else:
        urls = [line.strip() for line in args.urls.read_text(encoding='utf-8').splitlines()
                if line.strip()]
        if len(urls) != 20:
            raise ValueError(f'Expected exactly 20 URLs; found {len(urls)}')
        expected = net_single(urls)  # Validation/warm-up, outside timing.
        metadata += [f'- URL: {len(urls)}; байт за запуск: {sum(expected)}.',
                     f'- Сетевая среда (задана пользователем): {args.network_note}.',
                     '- URL загружены заранее; замер включает HTTP-запросы и полное чтение ответов.',
                     '- Один предварительный последовательный проход для проверки ответов исключён из замеров.']
        methods = [('sequential', 1, net_single), ('ThreadPoolExecutor', WORKERS, net_threads),
                   ('ProcessPoolExecutor', WORKERS, net_processes)]
        rows = measure_group('NETWORK', methods, urls, expected, cores)
    save_results(rows, args.task, metadata)


if __name__ == '__main__':
    main()
