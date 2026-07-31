import enum


class ProviderErrorEnum(enum.Enum):
    CONNECTION_TEST_FAILED = (200101, "供应商连接测试失败")
    SAVE_FAILED = (200102, "供应商保存失败")
    CREATE_FAILED = (200103, "供应商创建失败")
    NOT_FOUND = (200104, "供应商不存在/未保存")
    WRONG_PARAMETER = (200105, "API / API 地址不正确")
    UNKNOW_ERROR = (200106, "未知错误")

    def __init__(self, code, message):
        self.code = code
        self.message = message

class NoteErrorEnum(enum.Enum):
    PLATFORM_NOT_SUPPORTED = (300101 ,"选择的平台不受支持")

    def __init__(self, code, message):
        self.code = code
        self.message = message