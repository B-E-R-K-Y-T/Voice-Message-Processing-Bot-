import asyncio
import json
from io import BytesIO
from queue import Full
from asyncio import QueueEmpty
from typing import NamedTuple
import logging

from telebot.types import File, Message
from vosk import Model, KaldiRecognizer
import soundfile as sf

from config import StopApp, stop_app_lock, file_schedule_tasks, files_convert_queue

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

MODEL_PATH = "model/vosk-model-small-ru-0.22"
model = Model(MODEL_PATH)

class ChatData(NamedTuple):
    file: File
    message: Message

def convert_to_wav(input_file):
    audio_data, sample_rate = sf.read(input_file)

    audio_buffer = BytesIO()
    sf.write(audio_buffer, audio_data, sample_rate, format='WAV')
    audio_buffer.seek(0)

    return audio_buffer


def transcribe_audio(audio_data):
    rec = KaldiRecognizer(model, 48000)  # Для фонового изображение
    audio_data.seek(0)

    rec.AcceptWaveform(audio_data.read())
    result = rec.Result()

    try:
        text = json.loads(result).get('text', '')
        return text
    except json.JSONDecodeError:
        return "Не удалось распознать речь."


async def file_task_runner():
    while True:
        with stop_app_lock:
            if StopApp.stop_app:
                logging.info("file_task_runner stopping.")
                return

        await asyncio.sleep(1)

        tasks = []

        try:
            while not file_schedule_tasks.empty():
                task = file_schedule_tasks.get_nowait()
                tasks.append(task)
                logging.info(f"Task added to processing: {task}")
        except QueueEmpty:
            continue

        if tasks:
            await asyncio.gather(*tasks)


async def put_file_to_convert(file_info: File, message: Message):
    while True:
        with stop_app_lock:
            if StopApp.stop_app:
                logging.info("put_file_to_convert stopping.")
                return

        try:
            files_convert_queue.put(
                ChatData(
                    file=file_info,
                    message=message
                )
            )
            logging.info(
                f"File added to queue for conversion: {file_info.file_path} from message: {message.message_id}"
            )
            break
        except Full:
            logging.warning("Queue is full, waiting to retry...")
            await asyncio.sleep(1)
