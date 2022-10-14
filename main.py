import datetime
from dataclasses import dataclass
import os
from dotenv import load_dotenv
import requests
from bs4 import BeautifulSoup
from gcsa.google_calendar import GoogleCalendar
from gcsa.event import Event
from gcsa.reminders import PopupReminder


load_dotenv()
USERNAME = os.getenv('LOGIN')
print(USERNAME)
PASSWORD = os.getenv('PASSWORD')
LOGIN_URL = 'https://e.muiv.ru/login/index.php'
SCHEDULE_URL = 'https://e.muiv.ru/local/student_timetable/view.php'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/105.0.0.0 Safari/537.36'
START_DATE = datetime.date.today()
END_DATE = datetime.datetime.now() + datetime.timedelta(days=21)
ID = os.getenv('ID')
ADDRESS = os.getenv('ADDRESS')


@dataclass
class Lesson():
    start_time: datetime.datetime
    end_time: datetime.datetime
    name: str
    room: str
    type: str
    teacher: str


def create_payload(login_token):
    return {
        'anchor': '',
        'logintoken': login_token,
        'username':  USERNAME,
        'password': PASSWORD,
    }


def create_session():
    session = requests.session()
    session.headers['User-Agent'] = USER_AGENT
    initial_requests = session.get(LOGIN_URL)
    initial_bs = BeautifulSoup(initial_requests.content, features='lxml')
    login_token_str = initial_bs.find_all('input', {'name': 'logintoken'})
    if len(login_token_str) != 1:
        raise Exception('login token not founded, PLZ DO SOMETHINGS')
    login_token = login_token_str[0].attrs['value']
    payload = create_payload(login_token)
    main_page = session.post(LOGIN_URL, data=payload)
    main_page_bs = BeautifulSoup(main_page.content, features='lxml')
    errors = main_page_bs.find_all('div', class_='loginerrors')
    if len(errors) > 0:
        for err in errors:
            print(err.prettify())
        raise Exception('LOGIN ERROR')
    return session


def time_from_string(time, date):
    time = datetime.datetime.strptime(time, '%H:%M').time()
    return datetime.datetime.combine(date, time)


def get_schedule():
    session = create_session()
    schedule_response = session.get(SCHEDULE_URL)
    schedule_soup = BeautifulSoup(schedule_response.text, features='lxml')
    schedule_table = schedule_soup.find_all('div', class_='studtimetable')[0]
    date = None
    lessons = []
    for tag in schedule_table.children:
        if 'ttdate' in tag.get('class'):
            raw_date = tag.string
            date = datetime.datetime.strptime(raw_date, '%d.%m.%Y').date()
        if 'table' in tag.get('class'):
            if date is None:
                raise Exception('Mb some date for lessons?')
            for lesson_data in tag.children:
                if 'head' in lesson_data.get('class'):
                    continue
                lessons_element = []
                for i in lesson_data.children:
                    lessons_element.append(i.string.strip())
                raw_start_time, raw_end_time = lessons_element[0].split('-')
                start_time = time_from_string(raw_start_time, date)
                end_time = time_from_string(raw_end_time, date)
                name = lessons_element[1]
                room = lessons_element[2]
                type_ = lessons_element[3]
                teacher = lessons_element[4]
                lessons.append(Lesson(
                    start_time,
                    end_time,
                    name,
                    room,
                    type_,
                    teacher

                ))
    return lessons


def create_events_list():
    lessons = get_schedule()
    event_date = lessons[0].start_time - datetime.timedelta(days=1)
    events_list = []
    for lesson in lessons:
        if lesson.start_time < datetime.datetime.now():
            continue
        reminder_time = None
        if lesson.start_time - event_date >= datetime.timedelta(hours=3):
            reminder_time = [PopupReminder(minutes_before_start=80),
                             PopupReminder(minutes_before_start=60)
                             ]
        elif lesson.start_time - event_date >= datetime.timedelta(minutes=30):
            reminder_time = PopupReminder(minutes_before_start=10)
        event_date = lesson.end_time
        event = Event(
            lesson.name,
            start=lesson.start_time,
            end=lesson.end_time,
            description=f'{lesson.teacher}\n{lesson.type}, {lesson.room}',
            reminders=reminder_time,
            location=ADDRESS,
        )
        events_list.append(event)
    return events_list


def update_events():
    # TODO information about update events (deleted, updated, added)
    gc = GoogleCalendar()
    new_events_list = create_events_list()
    old_events_list = gc.get_events(
        calendar_id=ID, time_min=datetime.datetime.now())
    for event in old_events_list:
        gc.delete_event(event, calendar_id=ID)
    for event in new_events_list:
        gc.add_event(event, calendar_id=ID)


def main():
    update_events()


if __name__ == '__main__':
    main()
