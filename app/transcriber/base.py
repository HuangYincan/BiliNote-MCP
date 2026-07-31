from abc import ABC, abstractmethod

from app.models.transcriber_model import TranscriptResult


class Transcriber(ABC):
    @abstractmethod
    def transcript(self,file_path:str)->TranscriptResult:
        '''

        :param file_path:音频路径
        :return: 返回一个 TranscriptResult 类
        '''
        pass

    def on_finish(self,video_path:str,result: TranscriptResult)->None:
        '''
        当音频转录完成时调用
        :param video_path: 视频路径
        :param result: 识别结果
        :return:
        '''
        pass