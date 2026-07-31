# exceptions/biz_exception.py

class BizException(Exception):
    def __init__(self, code: int, message: str = "业务异常"):
        self.code = code
        self.message = message