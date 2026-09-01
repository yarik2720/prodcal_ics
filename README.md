# Как использовать?

Ссылка на подписной календарь: https://yarik2720.github.io/prodcal_ics/prodcal.ics

Данные о рабочих и нерабочих днях загружаются в формате XML с
[xmlcalendar.github.io](https://xmlcalendar.github.io/). Календарь рассчитан на пятидневную
рабочую неделю в России и содержит названия государственных праздников, а также
отдельные события для сокращённых рабочих дней.

## Как поднять у себя на сервере

1. Установить необходимые модули для Python:
```
$ pip3 install -r requirements.txt
```
1. Настроить автообновление календаря:
```
$ crontab -l
0 1 * * * python3 /home/ubuntu/prodcal_ics.py --start-year=2018 -o /home/ubuntu/www/prodcal.ics
```
1. Отдавать файл любым сервером prodcal.ics (например, nginx)

## Разработка

https://icalendar.org/validator.html
