from qimview.utils.utils      import deep_getsizeof
from qimview.utils.ThreadPool import ThreadPool
from qimview.utils.qt_imports import QtWidgets

from collections import deque
from typing import List, TypeVar, Optional, Generic, Any, Tuple

TId    = TypeVar("TId")
TValue = TypeVar("TValue")
TExtra = TypeVar("TExtra")

class BaseCache(Generic[TId, TValue, TExtra]):
    def __init__(self, name : str =""):
        # Python list and deque are thread-safe
        self.cache      : deque[Tuple[TId, TValue, Optional[TExtra]]] = deque()
        self.cache_list : List[TId]                                   = []
        self.cache_size : int                                         = 0
        # Max size in Mb
        self.max_cache_size : int                              = 2000
        self.verbose        : bool                             = False
        self.cache_unit     : int                              = 1024*1024 # Megabyte
        self.thread_pool    : ThreadPool                       = ThreadPool()
        self.memory_bar     : Optional[QtWidgets.QProgressBar] = None
        self._name          : str                              = name
        # Avoid changing progressbar inside a thread so no need for mutex

    def set_memory_bar(self, progress_bar:QtWidgets.QProgressBar) -> None:
        self.memory_bar = progress_bar
        self.memory_bar.setRange(0, self.max_cache_size)
        self.memory_bar.setFormat("%v Mb")

    def reset(self) -> None:
        self.cache = deque()
        self.cache_list = []
        self.cache_size = 0

    def set_max_cache_size(self, size : int) -> None:
        self.max_cache_size = size
        self.check_size_limit()
        if self.memory_bar is not None:
            self.memory_bar.setRange(0, self.max_cache_size)

    def print_log(self, message : str) -> None:
        if self.verbose:
            print(message)

    def search(self, id : TId) -> Optional[TValue]:
        res = None
        if id in self.cache_list:
            pos = self.cache_list.index(id)
            # print(f"pos {pos} len(cache) {len(self.cache)}")
            try:
                res = self.cache[pos][1]
            except Exception as e:
                print(f" Error in getting cache data: {e}")
                self.print_log(f" *** Cache {self._name}: search() cache_list {len(self.cache_list)} cache {len(self.cache)}")
                res = None
        return res

    def append(self, id : TId, value: TValue, extra: Optional[TExtra] = None, check_size=True) -> None:
        """
        :param id: cache element identifier
        :param value: cache value, typically numpy array of the image
        :param extra: additional data in the cache
        :return:
        """
        # update cache
        self.print_log(f"added size {deep_getsizeof([id, value, extra], set())}")
        self.cache.append((id, value, extra))
        self.cache_list.append(id)
        self.print_log(f" *** Cache {self._name}: append() cache_list {len(self.cache_list)} cache {len(self.cache)}")
        if check_size:
            self.check_size_limit()

    def get_cache_size(self) -> int:
        size = deep_getsizeof(self.cache, set())
        return size
    
    def update_progress(self):
        if self.memory_bar is not None:
            new_progress_value = int(self.cache_size/self.cache_unit+0.5)
            if new_progress_value != self.memory_bar.value():
                self.memory_bar.setValue(new_progress_value)

    def check_size_limit(self, update_progress : bool = False) -> None:
        self.print_log(" *** Cache: check_size_limit()")
        cache_size = self.get_cache_size()
        while cache_size >= self.max_cache_size * self.cache_unit:
            self.cache.popleft()
            self.cache_list.pop(0)
            self.print_log(" *** Cache: pop ")
            cache_size = self.get_cache_size()
        self.print_log(f" *** Cache::append() {self._name} {cache_size/self.cache_unit} Mb; size {len(self.cache)}")
        self.cache_size = cache_size
        if update_progress:
            self.update_progress()
