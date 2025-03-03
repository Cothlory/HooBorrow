[![Review Assignment Due Date](https://classroom.github.com/assets/deadline-readme-button-22041afd0340ce965d47ae6ef1cefeee28c7c493a6346c4f15d667ab976d596c.svg)](https://classroom.github.com/a/hLqvXyMi)

### Run the server

Recommended using [conda](https://www.anaconda.com/download/success):
```sh
conda create --name hooborrow python=3.13
conda activate hooborrow
```
In the root directory, run:
```sh
python -m install requirements.txt
python manage.py migrate
python manage.py collectstatic
python manage.py runserver
```
