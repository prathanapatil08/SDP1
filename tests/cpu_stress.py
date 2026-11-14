import multiprocessing
import time
from datetime import datetime

def cpu_worker(duration):
    end_time = time.time() + duration

    while time.time() < end_time:
        sum(i * i for i in range(10000))

if __name__ == "__main__":
    print("CPU simulation started:", datetime.now())

    processes = []

    for _ in range(2):
        process = multiprocessing.Process(
            target=cpu_worker,
            args=(30,)
        )
        process.start()
        processes.append(process)

    for process in processes:
        process.join()

    print("CPU simulation ended:", datetime.now())