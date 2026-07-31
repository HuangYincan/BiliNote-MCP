import os
from app.utils.logger import get_logger
logger = get_logger(__name__)

def cleanup_temp_files(data):
    logger.info(f"starting cleanup temp files ：{data['file_path']}")
    file_path = data['file_path']
    if not os.path.exists(file_path):
        logger.warning(f"路径不存在：{file_path}")
        return

    dir_path = os.path.dirname(file_path)
    base_name = os.path.basename(file_path)
    video_id, _ = os.path.splitext(base_name)

    logger.info(f"开始清理 video_id={video_id} 所有相关文件")

    for file in os.listdir(dir_path):
        if file.startswith(video_id):
            full_path = os.path.join(dir_path, file)
            try:
                os.remove(full_path)
                logger.info(f"删除文件：{full_path}")
            except Exception as e:
                logger.error(f"删除失败：{full_path}，原因：{e}")
