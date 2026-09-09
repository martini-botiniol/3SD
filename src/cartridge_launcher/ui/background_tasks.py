"""Worker results are applied only by Tk's main thread, never by workers."""
from concurrent.futures import ThreadPoolExecutor
import queue
import logging


class BackgroundTasks:
    def __init__(self, root):
        self.root = root
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="3sd-devices")
        self.assetPool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="3sd-covers")
        self.searchPool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="3sd-search")
        self.actionPool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="3sd-steam")
        self.results = queue.Queue()
        self.closed = False
        self.pending = set()
        root.bind("<Destroy>", self._destroy, add="+")
        root.after(50, self._drain)

    def submit(self, key, work, done, failed):
        if self.closed or key in self.pending:
            return False
        self.pending.add(key)
        category = key[0] if isinstance(key, tuple) else key
        pool = {"cover": self.assetPool, "search": self.searchPool, "steam": self.actionPool}.get(category, self.pool)
        future = pool.submit(work)
        future.add_done_callback(lambda completed: self.results.put((key, completed, done, failed)))
        return True

    def _drain(self):
        while not self.results.empty():
            key, future, done, failed = self.results.get_nowait()
            self.pending.discard(key)
            try:
                try:
                    value = future.result()
                except Exception as exc:
                    failed(exc)
                else:
                    done(value)
            except Exception:
                logging.getLogger("3SD").exception("No se pudo actualizar la interfaz")
        if not self.closed:
            self.root.after(50, self._drain)

    def _destroy(self, event):
        if event.widget == self.root:
            self.closed = True
            for pool in (self.pool, self.assetPool, self.searchPool, self.actionPool):
                pool.shutdown(wait=False, cancel_futures=True)
