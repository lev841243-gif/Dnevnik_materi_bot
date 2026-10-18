# Telegram-бот «Дневник Спокойного Материнства»

Две ветки в главном меню (инлайн-кнопки): дневник малыша (опрос из 6 вопросов,
в конце сводка «Запись для врача») и «Мой ресурс» (текст с техниками самопомощи).

Без базы данных и внешних сервисов. Ответы и Telegram ID на диск не пишутся
и в логи не попадают. Состояние диалога хранится только в оперативной памяти и
удаляется сразу после итоговой сводки или по команде /cancel.
Напоминаний нет.

## Запуск

1. Создайте бота у @BotFather и получите токен.
2. Установите зависимости (нужен Python 3.10+):

   ```
   python -m venv venv
   source venv/bin/activate        # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Задайте токен и запустите:

   ```
   export BOT_TOKEN="ваш_токен"    # Windows PowerShell: $env:BOT_TOKEN="ваш_токен"
   python bot.py
   ```

## Тексты

Все тексты лежат в `texts.py`: приветствие с дисклеймером, 6 вопросов, подписи
для сводки, текст ветки «Мой ресурс». Они взяты из ТЗ заказчика дословно.
Менять код не нужно, достаточно заменить значения и перезапустить бота.

## Деплой на VPS (systemd)

`/etc/systemd/system/tgbot.service`:

```
[Unit]
Description=Telegram bot
After=network-online.target

[Service]
WorkingDirectory=/opt/tgbot
Environment=BOT_TOKEN=ваш_токен
ExecStart=/opt/tgbot/venv/bin/python bot.py
Restart=always
User=tgbot

[Install]
WantedBy=multi-user.target
```

```
systemctl daemon-reload && systemctl enable --now tgbot
```

## Ограничения

- При перезапуске бота незавершённые опросы сбрасываются (это следствие хранения в памяти).
- Telegram передаёт ID пользователя с каждым сообщением, поэтому на время диалога он есть в памяти процесса. После завершения диалога запись удаляется.
- Максимальная длина одного ответа: 500 символов (константа `MAX_ANSWER_LEN` в `bot.py`).
