# GitHub и Jenkins на двух машинах

Это схема блока Б на оценку «хорошо». Конфигурация подготовлена; Jenkins ещё не установлен и реальный двухмашинный прогон не выполнен.

## Машины

1. Linux VM ARM64 с Jenkins, Git, Bash, Docker Engine, Compose plugin и OpenSSH client. Метка узла Jenkins: `mtg-build`. Для небольшой лаборатории Jenkins и исполнитель могут работать на одной выделенной VM. Доступ к Docker нужен пользователю, выполняющему pipeline.
2. Другая Linux VM ARM64 с Docker Engine, Compose plugin, SSH server, Bash и curl. На ней работают API, PostgreSQL, Prometheus и Grafana. Образ не собирается: загружается через SSH командой docker load.

Одинаковая архитектура CPU обязательна для текущей сборки. Две VM на одном Mac допускаются заданием. Два контейнера на одном хосте не являются подтверждением двух разных машин.

## Репозиторий и задача Jenkins

Создать одну задачу Pipeline с именем `mtg-shop`, Definition → Pipeline script from SCM, SCM → Git, URL → https://github.com/Uya13/mtg-shop.git, Branch → */main, Script Path → Jenkinsfile.
Для закрытого репозитория добавить отдельные credentials чтения GitHub: например SSH username with private key с пользователем git и GitHub deploy key без права записи. Тогда URL будет git@github.com:Uya13/mtg-shop.git. Проверить SSH host key GitHub по официальной документации; проверку хоста не отключать.

Нужны плагины Pipeline, Git, Credentials Binding и Timestamper. Создать метку узла `mtg-build`. Все стадии используют один workspace на первой VM. Для этой конфигурации использовать только одну задачу mtg-shop; отключены параллельные запуски. Опрос SCM раз в пять минут позволяет запускать pipeline после изменений без публичного webhook.

## Секреты Jenkins

В Credentials добавить три Secret file с точными ID:

| ID | Содержимое файла |
|---|---|
| mtg-ssh-key | Приватный ключ отдельной пары SSH для доступа ко второй VM |
| mtg-known-hosts | Проверенный ключ хоста второй VM в формате known_hosts |
| mtg-deploy-env | Файл .env с POSTGRES_PASSWORD, GRAFANA_ADMIN_PASSWORD и портами |

Публичную часть ключа деплоя добавить пользователю второй VM в authorized_keys. Credentials GitHub для чтения кода — отдельные от credentials SSH для деплоя. Не использовать приватный ключ загрузки проекта в GitLab.
Не хранить секреты в репозитории. Пользователь второй VM должен иметь доступ к Docker. Файл окружения имеет права 600.

Пример структуры .env, значения заменить случайными паролями:

```dotenv
POSTGRES_PASSWORD=replace-with-random-password
GRAFANA_ADMIN_PASSWORD=replace-with-another-password
APP_PORT=8000
PROMETHEUS_PORT=9090
GRAFANA_PORT=3000
```

Пароли первоначально применяются при создании БД PostgreSQL и Grafana. Изменение переменной при сохранённом томе не меняет существующий пароль.

## Запуск

Первый Build Now создаёт параметры задачи. Для следующего Build with Parameters указать DEPLOY_HOST (адрес второй VM) и DEPLOY_USER. Адрес без протокола и порта. Перед запуском проверить SSH-связность VM.

Check запускает линтер и тесты с отдельным PostgreSQL. Любая ошибка останавливает следующие стадии. Тестовые контейнеры очищаются в post always.
Build собирает образ mtg-shop:<GIT_COMMIT> и сохраняет image.tar в workspace.
Deploy через Jenkins Credentials вызывает scripts/deploy.sh, передаёт образ и конфигурации на вторую VM, ожидает healthy и делает smoke-запрос /health. Архив образа удаляется после запуска.

Параметры DEPLOY_HOST и DEPLOY_USER нужно сохранить в настройках задачи как значения по умолчанию после первичной настройки, чтобы автоматические запуски при опросе SCM имели правильный адрес. Не менять их в Jenkinsfile на секретные значения.

## Доступ и защита

Порты приложений привязаны к loopback второй VM. Для просмотра открыть SSH-туннель со своего Mac:

```bash
ssh -L 8000:127.0.0.1:8000 -L 3000:127.0.0.1:3000 -L 9090:127.0.0.1:9090 student@second-vm
```

Показать две VM, журнал Jenkins с тремя успешными стадиями, Swagger, операции склада и Grafana. Затем внести небольшое изменение кода и продемонстрировать его автоматический деплой.

Документация: https://www.jenkins.io/doc/book/pipeline/jenkinsfile/
