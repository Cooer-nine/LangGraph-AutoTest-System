"""
全局配置管理
"""
from pathlib import Path

# ============================================
# 项目路径
# ============================================
PROJECT_ROOT = Path(__file__).parent.parent.resolve()

# 加载 .env 文件（优先 .env，其次 .env.example）
try:
    from dotenv import load_dotenv
    for env_name in [".env", ".env.example"]:
        env_path = PROJECT_ROOT / env_name
        if env_path.exists():
            load_dotenv(env_path)
            print(f"[settings] 已加载: {env_path}")
            break
        else:
            print(f"[settings] 未找到: {env_path}")
except ImportError:
    print("[settings] python-dotenv 未安装")

DATA_DIR = PROJECT_ROOT / "data"
SCREENSHOT_DIR = DATA_DIR / "screenshots"
LOG_DIR = DATA_DIR / "logs"
CHROMA_DIR = DATA_DIR / "chroma_db"
REPORT_DIR = DATA_DIR / "reports"

# 确保目录存在
for d in [DATA_DIR, SCREENSHOT_DIR, LOG_DIR, CHROMA_DIR, REPORT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ============================================
# 日志配置
# ============================================
LOG_CONFIG = {
    "level": "DEBUG",
    "rotation": "10 MB",
    "retention": "7 days",
    "format": "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}",
}
