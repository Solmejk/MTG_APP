from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class _WorkerSignals(QObject):
    finished = Signal(object)  # result of fn()
    failed = Signal(str)


class BackgroundTask(QRunnable):
    """Runs fn() on a QThreadPool worker thread, reports back via signals.

    autoDelete is disabled: QThreadPool deletes QRunnables the instant run()
    returns, from the worker thread, which races the queued finished/failed
    signal's delivery to the main thread and crashes (use-after-free — see
    ImageLoader). Callers must keep a reference to the task alive; pass
    keep_alive_list to run_in_background to do that automatically.
    """

    def __init__(self, fn):
        super().__init__()
        self.fn = fn
        self.signals = _WorkerSignals()
        self.setAutoDelete(False)

    @Slot()
    def run(self):
        try:
            result = self.fn()
        except Exception as e:
            self.signals.failed.emit(str(e))
        else:
            self.signals.finished.emit(result)


def run_in_background(fn, keep_alive_list, on_finished=None, on_failed=None):
    """Submit fn to the shared QThreadPool.

    keep_alive_list: a list the caller owns, holding task references for the
    caller's lifetime (required — see BackgroundTask for why).
    on_finished/on_failed should be bound methods of a QObject (e.g. a
    QWidget), not plain functions/lambdas — only those get correctly queued
    onto the main thread for cross-thread signal delivery.
    """
    task = BackgroundTask(fn)
    keep_alive_list.append(task)
    if on_finished:
        task.signals.finished.connect(on_finished)
    if on_failed:
        task.signals.failed.connect(on_failed)
    QThreadPool.globalInstance().start(task)
    return task
