from app.downloaders.bilibili_downloader import BilibiliDownloader
from app.downloaders.douyin_downloader import DouyinDownloader
from app.downloaders.kuaishou_downloader import KuaiShouDownloader
from app.downloaders.local_downloader import LocalDownloader
from app.downloaders.youtube_downloader import YoutubeDownloader

SUPPORT_PLATFORM_MAP = {
    'youtube':YoutubeDownloader(),
    'bilibili':BilibiliDownloader(),
    'tiktok':DouyinDownloader(),
    'kuaishou':KuaiShouDownloader(),
    'douyin':DouyinDownloader(),
    'local':LocalDownloader()
}