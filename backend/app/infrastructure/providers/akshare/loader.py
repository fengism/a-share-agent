"""AkShare 第三方库的延迟加载入口。"""


class LazyAkshare:
    def __getattr__(self, name: str):
        import akshare

        return getattr(akshare, name)


ak = LazyAkshare()
