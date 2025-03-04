python manage.py makemigrations
python manage.py migrate
echo yes | python manage.py collectstatic
. ./.env
python manage.py runserver
