import enum


class DownloadQuality(str, enum.Enum):
    fast = "fast"
    medium = "medium"
    slow = "slow"
