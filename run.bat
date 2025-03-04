@echo off
call :load_env
python manage.py migrate
echo yes | python manage.py collectstatic
python manage.py runserver
goto :eof

:load_env
setlocal enabledelayedexpansion
for /f "tokens=1,2 delims==" %%a in (.env) do (
    set %%a=%%b
)
endlocal & setlocal
for /f "tokens=1,2 delims==" %%a in (.env) do (
    set %%a=!%%b!
)
goto :eof
