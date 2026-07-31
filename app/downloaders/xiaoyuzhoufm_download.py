from typing import Union, Optional

import requests

from app.downloaders.base import Downloader
from app.enmus.note_enums import DownloadQuality
from app.models.audio_model import AudioDownloadResult

url='https://www.xiaoyuzhoufm.com/_next/data/5Pvt_oGntgdyBD_XgwBaB/podcast/62382c1103bea1ebfffa1c00.json?id=62382c1103bea1ebfffa1c00'
header ={
    'user-agent':'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36'
}

response = requests.get(url, headers=header)
print(response.json())

class Xiaoyuzhoufm_download(Downloader):
    def download(
        self,
        video_url: str,
        output_dir: Union[str, None] = None,
        quality: DownloadQuality = "fast",
        need_video:Optional[bool]=False
    ) -> AudioDownloadResult:
        pass