import os
import threading
from multiprocessing import Queue
from asyncio import Queue as AsyncQueue

from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

API_TOKEN = os.getenv("API_TOKEN")

MAX_PROCESS_FILES = int(os.getenv("MAX_PROCESS_FILES"))
MAX_SCHEDULE_PROCESS_FILES = int(os.getenv("MAX_SCHEDULE_PROCESS_FILES"))
MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE")) * 1024 ** 2
LIMIT_MESSAGES = int(os.getenv("LIMIT_MESSAGES"))
INTERVAL_LIMIT_MESSAGES = int(os.getenv("INTERVAL_LIMIT_MESSAGES"))
MAX_SIZE_FILE_TO_TRANSCRIBE = float(os.getenv("MAX_SIZE_FILE_TO_TRANSCRIBE")) * 1024 ** 2

files_convert_queue = Queue(maxsize=MAX_PROCESS_FILES)
file_schedule_tasks = AsyncQueue(maxsize=MAX_SCHEDULE_PROCESS_FILES)
bot_lock = threading.Lock()
stop_app_lock = threading.Lock()


class StopApp:
    stop_app = False
