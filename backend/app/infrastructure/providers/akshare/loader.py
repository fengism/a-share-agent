"""AkShare 第三方库的延迟加载入口。"""

import os


class LazyAkshare:
    def __getattr__(self, name: str):
        os.environ.setdefault("TQDM_DISABLE", "1")
        import akshare

        return getattr(akshare, name)


ak = LazyAkshare()
