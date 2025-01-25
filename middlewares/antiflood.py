from telebot import BaseMiddleware, CancelUpdate

class AntiFloodMiddleware(BaseMiddleware):
    def __init__(self, time_limit, message_limit, bot) -> None:
        self.last_time = {}
        self.message_count = {}
        self.time_limit = time_limit
        self.message_limit = message_limit
        self.update_types = ['message']
        self.bot = bot
        self.waiting_users = set()  # Множество для отслеживания пользователей, которые уже получили сообщение об ожидании

    def pre_process(self, message, data):
        user_id = message.from_user.id

        # Инициализация для нового пользователя
        if user_id not in self.last_time:
            self.last_time[user_id] = message.date
            self.message_count[user_id] = 0

        # Проверка временного лимита
        if message.date - self.last_time[user_id] < self.time_limit:
            # Увеличение счетчика сообщений
            self.message_count[user_id] += 1

            # Проверка лимита по количеству сообщений
            if self.message_count[user_id] > self.message_limit:
                # Проверка, отправлялось ли уже сообщение об ожидании
                if user_id not in self.waiting_users:
                    self.bot.send_message(
                        message.chat.id,
                        f"Вы превысили лимит сообщений. Подождите {self.time_limit} секунд."
                    )
                    self.waiting_users.add(user_id)  # Добавляем пользователя в множество
                return CancelUpdate()

        else:
            # Если время истекло, сбрасываем счетчик и состояние ожидания
            self.last_time[user_id] = message.date
            self.message_count[user_id] = 1
            self.waiting_users.discard(user_id)  # Убираем пользователя из множества, так как он может снова писать

    def post_process(self, message, data, exception):
        pass
