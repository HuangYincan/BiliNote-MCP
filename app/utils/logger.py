import logging
import os
import sys
from pathlib import Path

# 日志目录：落在 VIDEONOTE_DATA_DIR/logs（由 videonote_mcp.config 设置），避免依赖 CWD
LOG_DIR = Path(os.environ.get("VIDEONOTE_DATA_DIR", ".")) / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 日志格式
formatter = logging.Formatter(
    fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# 控制台输出：必须走 stderr —— MCP stdio 传输使用 stdout 承载 JSON-RPC，绝不能污染
console_handler = logging.StreamHandler(sys.stderr)
console_handler.setFormatter(formatter)

# 文件输出
file_handler = logging.FileHandler(LOG_DIR / "app.log", encoding="utf-8")
file_handler.setFormatter(formatter)

# 获取日志器

def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        logger.propagate = False
    return logger
