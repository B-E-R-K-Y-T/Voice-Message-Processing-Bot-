import asyncio
import threading
import time
import logging
from asyncio import QueueFull
from copy import copy
from io import BytesIO
from queue import Empty

import telebot
from telebot.types import Message

from config import (
    API_TOKEN,
    file_schedule_tasks,
    stop_app_lock,
    StopApp,
    MAX_PROCESS_FILES,
    files_convert_queue,
    bot_lock,
    MAX_FILE_SIZE, LIMIT_MESSAGES, INTERVAL_LIMIT_MESSAGES, MAX_SIZE_FILE_TO_TRANSCRIBE,
)
from middlewares.antiflood import AntiFloodMiddleware
from util import put_file_to_convert, file_task_runner, transcribe_audio, convert_to_wav

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)

bot = telebot.TeleBot(API_TOKEN, use_class_middlewares=True)


@bot.message_handler(commands=["start"])
def send_welcome(message: Message):
    welcome_text = (
        "Привет! Я бот, который обрабатывает ваши голосовые сообщения.\n"
        "Отправьте мне ваше голосовое сообщение, и я верну его вам в обработанном виде."
    )
    bot.send_message(chat_id=message.chat.id, text=welcome_text)
    logging.info(f"Sent welcome message to {message.from_user.id}")


@bot.message_handler(commands=["help"])
def send_help(message: Message):
    help_text = (
        "Я могу помочь вам в обработке голосовых сообщений.\n"
        "Вот что вы можете сделать:\n"
        "1. Отправьте голосовое сообщение, и я попробую его обработать.\n"
        "2. Для дальнейшей помощи вы можете нажать /help."
    )
    bot.send_message(chat_id=message.chat.id, text=help_text)
    logging.info(f"Sent help message to {message.from_user.id}")


@bot.message_handler(content_types=["voice"])
def handle_voice(message: Message):
    logging.info(f"Received voice message from {message.from_user.id}")

    file_info = bot.get_file(message.voice.file_id)

    answer_message = bot.reply_to(
        message=message, text="Запрос принят. Пожалуйста, подождите..."
    )

    if file_info.file_size > MAX_FILE_SIZE:
        bot.edit_message_text(
            text=f"Ваш файл слишком большой! Пожалуйста, отправьте файл меньше {MAX_FILE_SIZE / 1024 ** 2} МБ.",
            chat_id=answer_message.chat.id,
            message_id=answer_message.message_id
        )
        logging.info(f"File too big: {file_info.file_path}")
        return

    file_process_coro = put_file_to_convert(file_info, message)

    while True:
        try:
            file_schedule_tasks.put_nowait(file_process_coro)
            break
        except QueueFull:
            logging.warning("Queue is full, scheduling file for later.")
            time.sleep(2)

    bot.edit_message_text(
        text="Ваш файл взят в работу! Пожалуйста, подождите...",
        chat_id=answer_message.chat.id,
        message_id=answer_message.message_id
    )

    logging.info(f"File scheduled for conversion: {file_info.file_path}")


def file_converter():
    while True:
        with stop_app_lock:
            if StopApp.stop_app:
                logging.info("Stopping file converter thread.")
                return

        time.sleep(1)

        for _ in range(MAX_PROCESS_FILES):
            try:
                file, message = files_convert_queue.get_nowait()
            except Empty:
                continue

            logging.info(
                f"Starting to download file: {file.file_path} for user: {message.from_user.id}"
            )

            with bot_lock:
                downloaded_file = bot.download_file(file.file_path)

            voice_file = BytesIO(downloaded_file)
            voice_file.seek(0)  # Перемещаем указатель в начало файла

            transcript = "<Слишком большой размер файла для расшифровки>"

            if file.file_size < MAX_SIZE_FILE_TO_TRANSCRIBE:
                transcript = transcribe_audio(convert_to_wav(copy(voice_file)))

            if len(transcript) > 700:
                tail = "..."
                transcript = transcript[:700 - len(tail)] + tail

            caption = f"Голосовое сообщение от {message.from_user.first_name}\n\nРасшифровка: '{transcript}'"

            with bot_lock:
                bot.send_audio(
                    chat_id=message.chat.id,
                    audio=voice_file,
                    caption=caption
                )

            logging.info(f"File sent back to user: {message.chat.id}.")


async def main():
    file_converter_thread = threading.Thread(target=file_converter)
    file_converter_thread.start()
    logging.info("File converter thread started.")

    task_runner = asyncio.create_task(file_task_runner())
    logging.info("Task runner started.")

    bot.setup_middleware(AntiFloodMiddleware(time_limit=INTERVAL_LIMIT_MESSAGES, message_limit=LIMIT_MESSAGES, bot=bot))

    bot_thread = threading.Thread(target=bot.polling)
    bot_thread.start()
    logging.info("Bot polling started.")

    try:
        await task_runner
    except asyncio.CancelledError:
        logging.info("Task runner cancelled.")

    bot_thread.join(timeout=1)
    logging.info("Bot stopped.")

    with stop_app_lock:
        StopApp.stop_app = True

    file_converter_thread.join(timeout=1)

    logging.info("File converter thread stopped.")

if __name__ == "__main__":
    asyncio.run(main())
