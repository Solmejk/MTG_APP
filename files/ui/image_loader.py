"""ImageLoader: the app-wide singleton for fetching/decoding/rounding
card and profile images off the main thread. ImageTile and
CardThumbnailDelegate both submit() to it; it never blocks the UI, and
can be paused (e.g. while the user is typing a search) to avoid
saturating the thread pool with images that are about to scroll away.
"""

from pathlib import Path
from PySide6.QtCore import (
    Qt, QObject, QRunnable, QThreadPool, Signal, Slot, QRectF,
)
from PySide6.QtGui import QImage, QPainter, QPainterPath

from image_cache import get_image_path


class _TaskSignals(QObject):
    """Signals can only live on QObject, not QRunnable. Wrap them."""
    ready = Signal(object, QImage)   # (token, image)
    failed = Signal(object)          # (token,)


class _ImageLoadTask(QRunnable):
    """
    Worker task: fetch image from cache or web, decode, scale, round.
    Runs entirely off the main thread until emitting the result via signal.
    """

    def __init__(self, token, url: str, cache_name: str,
                 width: int, height: int, radius: int):
        """token: opaque value the caller uses to identify which tile
        this result belongs to (passed back unchanged in ready/failed).
        url: image URL to fetch. cache_name: on-disk cache key (see
        image_cache.get_image_path). width/height/radius: target size and
        corner rounding for the decoded image."""
        super().__init__()
        self.token = token  # caller identifies which tile to update
        self.url = url
        self.cache_name = cache_name
        self.width = width
        self.height = height
        self.radius = radius
        self.signals = _TaskSignals()
        # QThreadPool auto-deletes QRunnables the instant run() returns — from
        # the worker thread, before the queued ready/failed signal has been
        # delivered on the main thread. That races the task's own destruction
        # against delivery of its own signal (use-after-free). Keep it alive
        # manually; ImageLoader drops its reference once the signal fires.
        self.setAutoDelete(False)

    @Slot()
    def run(self):
        """Entry point QThreadPool calls on the worker thread: fetches
        (or reads from cache), decodes, scales, and rounds the image,
        then emits signals.ready(token, image) — or signals.failed(token)
        if any step fails."""
        try:
            # 1. Fetch (or get cached) — this may do HTTP
            path = get_image_path(self.url, self.cache_name)
            if not path:
                self.signals.failed.emit(self.token)
                return

            # 2. Decode as QImage (NOT QPixmap — QPixmap is main-thread only)
            image = QImage(str(path))
            if image.isNull():
                self.signals.failed.emit(self.token)
                return

            # 3. Scale
            scaled = image.scaled(
                self.width, self.height,
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )

            # 4. Round corners — paint into a transparent target
            result = QImage(scaled.size(), QImage.Format_ARGB32_Premultiplied)
            result.fill(Qt.transparent)

            painter = QPainter(result)
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setRenderHint(QPainter.SmoothPixmapTransform)

            path_obj = QPainterPath()
            path_obj.addRoundedRect(
                QRectF(0, 0, scaled.width(), scaled.height()),
                self.radius, self.radius,
            )
            painter.setClipPath(path_obj)
            painter.drawImage(0, 0, scaled)
            painter.end()

            self.signals.ready.emit(self.token, result)
        except Exception:
            self.signals.failed.emit(self.token)


class ImageLoader:
    """App-wide singleton (use ImageLoader.instance()) queueing image
    fetch/decode work onto a shared 6-thread pool."""

    _instance = None

    def __init__(self):
        """Not called directly — use ImageLoader.instance()."""
        self._pool = QThreadPool.globalInstance()
        self._pool.setMaxThreadCount(6)
        self._paused = False
        self._pending = []  # tasks held back while paused
        # Tasks have autoDelete disabled (see _ImageLoadTask) to avoid a
        # use-after-free race against their own queued signal delivery. We
        # never discard them, since attempting to release them right after
        # their signal fires just reintroduces the same race (a plain Python
        # callable can't be queued to the main thread — Qt runs it directly
        # on the worker thread, deleting the task mid-emit). The retained
        # memory is trivial relative to a card collection's size.
        self._inflight = []

    @classmethod
    def instance(cls):
        """Returns the shared ImageLoader, creating it on first call."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def pause(self):
        """Stops starting new submit()ted tasks (they queue in
        self._pending) until resume() is called. Doesn't affect tasks
        already running."""
        self._paused = True

    def resume(self):
        """Re-enables starting new tasks and immediately starts everything
        that was queued while paused."""
        self._paused = False
        # Flush whatever was held back
        pending, self._pending = self._pending, []
        for task in pending:
            self._pool.start(task)

    def submit(self, token, url, cache_name, width, height, radius, on_ready, on_failed=None):
        """Queues an image fetch/decode. token/url/cache_name/width/
        height/radius: see _ImageLoadTask. on_ready(token, QImage): called
        on the main thread when the image is ready. on_failed(token):
        called on the main thread if the fetch/decode fails; optional."""
        task = _ImageLoadTask(token, url, cache_name, width, height, radius)
        self._inflight.append(task)

        task.signals.ready.connect(on_ready)
        if on_failed:
            task.signals.failed.connect(on_failed)

        if self._paused:
            self._pending.append(task)
        else:
            self._pool.start(task)
