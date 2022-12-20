from json import JSONDecodeError
from dotenv import load_dotenv
import logging
import requests
import telegram
import time
import sys
import os
import exceptions
from http import HTTPStatus

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)


def logg():
    """Функция логгирования."""
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s, %(levelname)s, %(message)s, %(name)s",
        handlers=[logging.StreamHandler(stream=sys.stdout),
                  logging.FileHandler('program.log', mode='w')]
    )


def send_message(bot, message):
    """Отправляет сообщение в телегу."""
    logger.info(f"Попытка отправки сообщения: {message}")
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception:
        raise Exception('Ошибка при отправке сообщения')
    else:
        logger.info(f'Успешная отправка {message} в Telegram')


def get_api_answer(current_timestamp):
    """Получаем ответ от API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
        if response.status_code != HTTPStatus.OK:
            logging.error(f'API недоступен, код {response.status_code}')
            raise exceptions.APIisNotUnavailable('API недоступен')
        return response.json()
    except (JSONDecodeError, requests.exceptions.RequestException) as err:
        raise ConnectionError('Проблема с соединением') from err


def check_response(response):
    """Проверка запроса на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Это не словарь')
    elif 'homeworks' not in response:
        raise KeyError('Нет ключа homeworks')
    elif not isinstance(response['homeworks'], list):
        raise TypeError('Это не список')
    elif not response['homeworks']:
        raise exceptions.ResponseIsEmpty('Пустой список')
    return response.get('homeworks')


def parse_status(homework):
    """Проверка статуса работы."""
    homework_name = homework.get("homework_name")
    homework_status = homework.get("status")
    if homework_status not in HOMEWORK_VERDICTS:
        message = "В ответе пришёл неизвестный статус домашней работы"
        raise KeyError(message)
    verdict = HOMEWORK_VERDICTS[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка всех переменных."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Отсутствуют необходимые переменные')
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    dict_status_two = {}
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            homework_status = parse_status(homework[0])
            dict_status = {'name_homework': homework_status}
            if dict_status != dict_status_two:
                send_message(bot, homework_status)
                dict_status_two = dict_status.copy()
            else:
                logger.debug('Отсутствие в ответе новых статусов')
                current_timestamp = response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            dict_status = {'name_message': message}
            if dict_status != dict_status_two:
                bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
                dict_status_two = dict_status.copy()
            logger.error(message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logg()
    main()
