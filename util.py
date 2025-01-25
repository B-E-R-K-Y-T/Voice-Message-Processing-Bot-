import asyncio
from queue import Full
from asyncio import QueueEmpty
from typing import NamedTuple
import logging

from telebot.types import File, Message

from config import StopApp, stop_app_lock, file_schedule_tasks, files_queue

# Настройка логирования
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[logging.StreamHandler()])

class ChatData(NamedTuple):
    file: File
    message: Message

async def file_task_runner():
    while True:
        with stop_app_lock:
            if StopApp.stop_app:
                logging.info('file_task_runner stopping.')
                break

        await asyncio.sleep(0.1)

        tasks = []

        try:
            while not file_schedule_tasks.empty():
                task = file_schedule_tasks.get_nowait()
                tasks.append(task)
                logging.info(f'Task added to processing: {task}')
        except QueueEmpty:
            continue

        if tasks:
            await asyncio.gather(*tasks)

async def put_file_to_convert(file_info: File, message: Message):
    while True:
        with stop_app_lock:
            if StopApp.stop_app:
                logging.info('put_file_to_convert stopping.')
                break

        try:
            files_queue.put(
                ChatData(
                    file=file_info,
                    message=message
                )
            )
            logging.info(f'File added to queue for conversion: {file_info.file_path} from message: {message.message_id}')
            break
        except Full:
            logging.warning('Queue is full, waiting to retry...')
            await asyncio.sleep(0.1)
