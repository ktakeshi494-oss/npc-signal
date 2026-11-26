# Круглосуточный хостинг NPC Signal

Исследование на 26 ноября 2026.

## Финальное состояние (задеплоено 26.11.2026, ~16:30–16:45 МСК)

- Репозиторий: https://github.com/ktakeshi494-oss/npc-signal (public, аккаунт ktakeshi494-oss).
- Сайт (Pages, ветка `gh-pages`, корень): https://ktakeshi494-oss.github.io/npc-signal/ (index, terms, journal.html, journal.json — 200).
- Workflow `runtime`: cron `3,8,13,...,58 * * * *` (каждые 5 минут) + ручной запуск. Сессия getUpdates 180 с.
- Секреты Actions: TELEGRAM_BOT_TOKEN, STATE_KEY, PM_FREE_CHANNEL_ID, PM_ADMIN_CHAT_IDS. Переменная: PM_SITE_URL. Workflow permissions: read and write.
- Ветка `state`: зашифрованная база (AES-256-CBC). Начальное состояние (владелец 315286590, 1 пользователь, сигналы) восстановлено проверено расшифровкой.
- STATE_KEY хранится на box: `/workspace/bot-business/polymarket/.state_key` (mode 600, в .gitignore) и в Actions secrets. Потеряете оба — база не восстановится.
- Процессы на box (loop_bot, loop_collector, loop_publisher, bot.py) остановлены, чтобы не было двух поллеров getUpdates. НЕ запускать `start_all.sh` и `health_check.sh --restart`, пока Actions включены.
- Исправление при деплое: пуши в `state`/`gh-pages` из свежих `git init` каталогов не получали креды от checkout, поэтому в `runtime.sh` добавлена `gh_push` с `GITHUB_TOKEN` (передаётся в env workflow).
- Откат на box: остановить workflow (`gh workflow disable runtime -R ktakeshi494-oss/npc-signal`), расшифровать `state` в `data/pmsignals.sqlite`, `./start_all.sh`.


Box, на котором сейчас крутятся процессы, для 24/7 не годится: при простое агента процессы замирают, хотя uptime не сбрасывается.

## Рекомендация

**GitHub Actions по расписанию в публичном репозитории `npc-signal`.**

Это единственный вариант за $0, без карты, без новых платформ и без регистрации чего-либо кроме уже запланированного GitHub-аккаунта. Стандартные runners в публичных репозиториях [бесплатны и без лимита минут](https://docs.github.com/en/actions/concepts/billing-and-usage). Код, сайт и журнал живут в одном репозитории. Секреты — в Actions secrets. Состояние (SQLite с подписчиками и платежами) хранится **только в зашифрованном виде** в ветке `state`.

Это компромисс, не полноценный всегда включённый сервер. См. ограничения ниже. Настоящий always-on (мгновенные ответы Pro) без карты из РФ сейчас по сути недоступен.

Код уже подготовлен и проверен локально:

- `.github/workflows/runtime.yml` — cron каждые 5 минут и ручной запуск
- `scripts/runtime.sh` — один цикл: расшифровать базу → сборщик → короткая сессия бота → зашифровать базу → обновить `state` и `gh-pages`
- `scripts/state_crypt.sh` — AES-256-CBC, PBKDF2, 200000 итераций, ключ из секрета `STATE_KEY`
- `bot.py --session-seconds N` или переменная `PM_SESSION_SECONDS` — аккуратный выход из polling
- `scripts/pack_public_repo.sh` — собирает дерево для публичного репозитория без секретов и базы

Текущие процессы на box **не останавливались**.

## Ограничения этого варианта

1. **Задержка ответа бота.** Минимальный шаг cron у Actions — 5 минут ([документация](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax)). Сессия `getUpdates` длится ~3 минуты. В лучшем случае покупатель ждёт от нескольких секунд до ~5 минут. На практике расписание GitHub часто опаздывает на десятки минут, иногда на часы, отдельные запуски могут быть пропущены при высокой нагрузке. **Pro перестаёт быть «мгновенным».** Бесплатный канал с задержкой 30 минут тоже сдвигается на величину опоздания cron.
2. **Условия GitHub.** Для GitHub-hosted runners нельзя использовать Actions для деятельности, не связанной с разработкой, тестом, деплоем или публикацией ПО репозитория, и нельзя использовать их «как часть serverless-приложения» ([доп. условия, ред. 27.08.2026](https://docs.github.com/en/site-policy/github-terms/github-terms-for-additional-products-and-features)). Публикация журнала и сайта ближе к разрешённому. Постоянный Telegram-бот как продакшен-сервис — серая зона и **риск, что GitHub отключит workflow или репозиторий**. Это временная схема, не «навсегда».
3. **Один процесс.** Одновременно выполняется только один tick (concurrency). Максимум джобы у hosted runners — 6 часов, мы ставим 10 минут.
4. **Публичный репозиторий.** Код и зашифрованный снимок базы видны всем. Сырую базу и токены в git класть нельзя. Ключ шифрования хранится только в Actions secrets. Ветка `state` без ключа бесполезна, но ключ нельзя светить в логах и в чате.
5. **Правило 60 дней.** В публичном репозитории расписание отключается, если 60 дней не было активности репозитория ([документация](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows)). Наши пуши в `state` и `gh-pages` должны это сбрасывать; если workflow всё же встанет (`disabled_inactivity`), его нужно снова включить во вкладке Actions.
6. **Первый перенос базы.** Чтобы не потерять владельца (chat_id 315286590), пользователей и уже выпущенные сигналы, перед первым запуском в Actions нужно зашифровать копию живой базы и один раз запушить ветку `state`. Команды есть в шагах ниже. Делать это только в момент деплоя, не раньше.

## Сравнение вариантов (ноябрь 2026)

| Площадка | Бесплатный тариф | Карта | Из РФ | Подходит? |
|---|---|---|---|---|
| **GitHub Actions** (публичный репозиторий) | Стандартные runners без лимита минут; у приватного — только [включенные $12 compute/мес](https://docs.github.com/en/billing/reference/product-usage-included). Cron не чаще 5 мин, джоба до 6 ч. | Нет | Да (аккаунт уже создаётся) | **Да, как старт.** См. ограничения. Приватный репозиторий для 5-минутных сессий не потянуть: это десятки тысяч минут в месяц. |
| **Cloudflare Workers + Cron + D1** | [100k запросов/день, 10 мс CPU на запрос и на cron, 50 подизапросов, 5 cron на аккаунт](https://developers.cloudflare.com/workers/platform/limits/). D1: [5M чтений/день, 100k записей/день, 5 ГБ, 10 баз](https://developers.cloudflare.com/d1/platform/pricing/). Для Free карта не нужна. | Нет для Free | Регистрация по email доступна; оплата Paid российскими картами обычно не проходит | Нет как первый шаг: нужна новая регистрация, переписывать Python на JS, 10 мс CPU и 50 subrequests не хватит сборщику Polymarket. Позже можно рассмотреть webhook для мгновенных ответов бота, а сборщик оставить на Actions. |
| **Oracle Cloud Always Free** | [2 OCPU / 12 ГБ Ampere A1 или 2 AMD Micro, 200 ГБ диска, бессрочно](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm). Простой VM могут забрать. | Да, для проверки личности; prepaid/virtual не принимают | **Нет:** [Oracle свернула операции в РФ и не принимает новые заказы](https://www.oracle.com/corporate/conflict-in-ukraine/russia/) | Нет. |
| **Fly.io** | [$1 без карты на 7 дней; $5/мес после привязки карты](https://docs.fly.io/about/free-plan). До 3 Machines, том до 5 ГБ. Самый дешёвый always-on — около $2.19/30 дней за shared-cpu-1x 256 МБ. Если $5 кончатся, аккаунт уходит в Pay As You Go и считается **вся** пачка. | Нужна для постоянного $5; российские карты через Stripe, как правило, не проходят | Сайт открывается; для постоянного тарифа нужна иностранная карта | Только если появится иностранная карта. Новый аккаунт. |
| **Render** | [750 часов/мес, засыпает через 15 мин без HTTP](https://render.com/docs/free). Диск и фоновые workers — только платно. Free Postgres истекает через 30 дней. SQLite на Free теряется при засыпании. Always-on от $7/мес. | Для Free нет | Сайт доступен | Нет для polling-бота и постоянной SQLite. |
| **Deno Deploy** | [$0: 1M запросов, 10 cron, KV 1 ГБ](https://deno.com/deploy/pricing). Полные лимиты обычно после привязки карты. Простой через 20–30 с, webhook будит. | Часто нужна для полного Free | Неясно, карта РФ скорее не пройдёт | **Нельзя:** сервис [закрывается в апреле 2027](https://docs.deno.com/deploy/pricing_and_limits/). Плюс переписывать бота. |
| **PythonAnywhere** | У новых бесплатных аккаунтов (после 15.01.2026, в EU с 8.01) [нет scheduled и always-on задач](https://help.pythonanywhere.com/pages/FreeAccountsFeatures/), 100 CPU-секунд, 512 МБ диска, веб-приложение на 1 месяц. | Для always-on — платный тариф | Сервис доступен | Нет. |

## Что нужно сделать, когда появится новый GitHub-аккаунт

Регистрацию на `v5yn9jr3@mail.grokbot.com` делает основной бот. Деплой пока не делается. Когда аккаунт будет готов:

1. Создать **публичный** репозиторий `npc-signal` (без лицензии и без авто-README, чтобы проще сделать первый push).
2. Положить в него только содержимое, которое собирает `scripts/pack_public_repo.sh`. Никаких `.env.secret`, `OWNER_CLAIM_CODE.txt`, `data/`, `logs/`, `venv/`.
3. В репозитории: Settings → Secrets and variables → Actions → Secrets, добавить:
   - `TELEGRAM_BOT_TOKEN` — токен бота
   - `STATE_KEY` — длинный случайный ключ, например `openssl rand -base64 32`. Сохранить копию в хранилище паролей. Без него базу не восстановить.
   - `PM_FREE_CHANNEL_ID` — `-1005968095718`
   - `PM_ADMIN_CHAT_IDS` — `315286590`
4. Settings → Variables → Actions: `PM_SITE_URL` = `https://<логин>.github.io/npc-signal`
5. Settings → Pages: Source = **Deploy from a branch**, ветка `gh-pages`, папка `/ (root)`. Ветка появится после первого успешного workflow.
6. Settings → Actions → General: разрешить GitHub Actions, Workflow permissions = **Read and write** (чтобы `GITHUB_TOKEN` мог пушить `state` и `gh-pages`).
7. Перед самым первым запуском — перенести живую базу (см. ниже).
8. Actions → workflow `runtime` → **Run workflow**. Проверить, что tick зелёный, сайт открывается, бот отвечает на `/start` (с задержкой cron).
9. После того как сайт жив, ссылка на журнал в боте появится сама через `PM_SITE_URL`.

Владимиру на этом этапе ничего нажимать не обязательно. Имеет смысл только предупредить: ответы бота станут с паузой, и если GitHub отключит Actions, бот снова замолчит.

## Права токена

Сам workflow ходит в репозиторий через встроенный `GITHUB_TOKEN`. В `runtime.yml` ему достаточно `contents: write` (пуш веток `state` и `gh-pages`). Отдельно Actions, Secrets или Pages для этого токена не нужны.

Если понадобится fine-grained PAT, чтобы запушить код с box или настроить репозиторий по API (не для секретов в чате), ограничить его **только** репозиторием `npc-signal`:

| Право | Зачем |
|---|---|
| **Contents: Read and write** | Клонировать и пушить код, ветки `state` и `gh-pages` |
| **Workflows: Read and write** | Обязательно, чтобы пушить файлы из `.github/workflows/` |
| **Metadata: Read** | Выдаётся автоматически |
| **Pages: Write** | Только если включать Pages через API; в интерфейсе не нужно |
| **Administration** | Обычно не нужно |
| **Actions: Read** | Не обязательно для первого пуша; `GITHUB_TOKEN` в самом workflow уже настроен |
| **Secrets** | **Не давать** PAT. Секреты прописывать руками в Settings → Secrets. Так токен не сможет их прочитать обратно |

Classic PAT с широким `repo` лучше не выпускать.

## Перенос живой базы (только в момент деплоя)

На box, не коммитя сырой файл в `main`:

```bash
cd /workspace/bot-business/polymarket
# ключ — тот же, что будет в Actions secrets
cp -a data/pmsignals.sqlite /tmp/pmsignals.snapshot.sqlite
sqlite3 /tmp/pmsignals.snapshot.sqlite "PRAGMA wal_checkpoint(TRUNCATE);"
./scripts/state_crypt.sh encrypt /tmp/pmsignals.snapshot.sqlite /tmp/pmsignals.sqlite.enc
# дальше: ветка state в репозитории npc-signal, один файл pmsignals.sqlite.enc, и push
rm -f /tmp/pmsignals.snapshot.sqlite /tmp/pmsignals.sqlite.enc
```

Пока деплоя нет, это не запускалось: ключа ещё нет, и шифрованный снимок никуда не отправлялся.

## Как устроен tick

1. Скачать `pmsignals.sqlite.enc` из ветки `state` и расшифровать.
2. `run_cycle.py` — рынки, сигналы, оценка за 7 дней, `site/journal.html`.
3. `bot.py --session-seconds 180` — polling, доставка Pro и (с задержкой) в канал `@ainpcsignal`.
4. Checkpoint WAL, шифрование, force-push одного коммита в `state`.
5. Force-push статики (`index.html`, `terms.html`, `journal.html`, `journal.json`, `style.css`) в `gh-pages`.

Наложение tick'ов запрещено, чтобы не порвать базу.

## Что проверено локально (26.11.2026, деплоя не было)

- `session_seconds` в `bot.py`: аргумент и переменная окружения читаются верно.
- `tests/test_state_crypt.py`: шифрование/расшифровка, отказ в неверном ключе и в коротком ключе.
- Временный bare-git: пуш ветки `state`, восстановление, в расшифрованной базе то же значение. Заголовок шифртекста — `Salted__` (формат OpenSSL), не SQLite.
- Процессы на box не останавливались и на момент проверки были живы.

Намеренно **не** запускался второй `bot.py` с боевым токеном: два polling-процесса конфликтуют в Telegram.
