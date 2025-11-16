from datastructures import ProxyConfig
import multiprocessing
from worker import worker


def main():
    config = ProxyConfig.from_env()
    print(config)
    # Create worker processes that will each create their own socket
    # with SO_REUSEPORT
    workers = []
    for i in range(config.num_workers):
        worker_process = multiprocessing.Process(
            target=worker, args=(i, config)
        )
        worker_process.start()
        workers.append(worker_process)

    for worker_process in workers:
        worker_process.join()


if __name__ == "__main__":
    main()
