"""Regular Python lists: shared by threads, isolated between processes."""
import multiprocessing as mp
import sys
import threading

items = []


def change_in_thread():
    items.append('thread')
    print('Inside thread:', items, flush=True)


def change_in_process():
    items.append('process')
    print('Inside process:', items, flush=True)


def main():
    if sys.platform != 'linux':
        raise SystemExit('Run this example in Ubuntu through SSH.')
    print('Parent before:', items)
    thread = threading.Thread(target=change_in_thread)
    thread.start()
    thread.join()
    print('Parent after thread:', items)
    process = mp.get_context('fork').Process(target=change_in_process)
    process.start()
    process.join()
    if process.exitcode != 0:
        raise RuntimeError(f'Child process failed: exit code {process.exitcode}')
    print('Parent after process:', items)


if __name__ == '__main__':
    main()
