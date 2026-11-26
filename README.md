# NPC Signal — MVP (Polymarket alerts + crypto subscription)
Статус: рабочий MVP на box. **Ничего не опубликовано, бот не создан, аккаунты не регистрировались.**

## Состав
| Путь | Что это |
|---|---|
| `pmsignals/collector.py` | Сборщик публичного API Polymarket (Gamma + Data API v2) → SQLite `data/pmsignals.sqlite` (рынки, снапшоты цен, крупные сделки) |
| `pmsignals/signals.py` | Сигналы: 🐋 крупные сделки ≥$25K, 📈 движение цены ≥10 п.п. за ~2ч (рынки ≥$100K/сутки), 📊 всплеск объёма ≥3× среднего, 🔥 новые рынки ≥$250K за 24ч. Фильтры шума: без 5/15-мин «Up or Down», без цен у 0/1, кулдаун 12ч, квоты (≤8 за цикл) |
| `pmsignals/verify.py` | Автопроверка каждого сигнала через 7 дней (continued / reversed / flat) |
| `pmsignals/journal.py` | Экспорт публичного журнала `site/journal.html` + `journal.json` (только сигналы старше задержки free) |
| `pmsignals/payments.py` | Проверка оплаты по tx hash через бесплатные публичные эксплореры/RPC: BTC (mempool.space, запасной blockstream), ETH/BSC (publicnode RPC: ETH, BNB, USDT, USDC), Tron (TronGrid: USDT TRC-20), Solana (RPC: SOL, USDT, USDC), TON (toncenter v3: TON, USDT). Уникальная сумма на каждый счёт, хеш одноразовый, подтверждения, окно 72ч |
| `bot.py` | Telegram-бот (python-telegram-bot 21): подтверждение условий, тарифы, счёт, приём tx hash, автопроверка, мгновенная доставка Pro, отложенный (30 мин) бесплатный канал, админ `/grant`, `/stats` |
| `run_cycle.py` | Один цикл: сбор → сигналы → проверка 7 дней → журнал |
| `site/` | Лендинг `index.html`, `terms.html`, шаблон журнала, `style.css` (под GitHub Pages) |
| `COMPLIANCE.md` | Разбор ToS Polymarket и как продукт им соответствует |
| `examples/` | Реальный вывод: `run_cycle_output.txt`, `journal_demo.html/.pdf/.json`, `verify_demo.txt`, `payments_live_test.txt` |
| `tests/` | Живые тесты платёжных проверок на реальных транзакциях mainnet |

## Цена (обоснование)
$5/неделя, $12/месяц, $99/год. Конкуренты: Polywhaler $9 и $29/мес; Provyan $5/нед, $15/мес; ArbiFrogBot $4/нед, $12/мес; Squelch $19/мес; TrendIQ $30/мес. Мы новые и без истории → входим в нижнюю середину ($12), недельный пропуск $5 снижает барьер первой покупки. Комиссии сетей: для $5 рекомендуем USDT на Tron/TON/Solana/BSC.

## Запуск (после «да» владельца)
```bash
cd /workspace/bot-business/polymarket
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python run_cycle.py --print                 # проверка сборщика
export TELEGRAM_BOT_TOKEN=...                          # от @BotFather (никогда не коммитить)
export PM_FREE_CHANNEL_ID=@your_free_channel           # бот — админ канала
export PM_ADMIN_CHAT_IDS=<chat_id владельца>
PM_RUN_COLLECTOR_IN_BOT=1 ./venv/bin/python bot.py     # бот + сбор каждые 10 мин
```
Или cron: `*/10 * * * * cd /workspace/bot-business/polymarket && ./venv/bin/python run_cycle.py >> data/cycle.log 2>&1`
Тесты оплат: `./venv/bin/python tests/test_payments_live.py && ./venv/bin/python tests/test_native_live.py`

Плейсхолдеры перед публикацией: `BOT_USERNAME_PLACEHOLDER` (site/index.html), `SITE_URL_PLACEHOLDER` (bot.py).

## Что нужно от Владимира
1. Создать бота в @BotFather (2 мин) и передать токен через защищённое поле, не в чат. Создать публичный канал для бесплатных алертов и добавить бота админом.
2. «Да» на публикацию лендинга и журнала на GitHub Pages (новый репозиторий).
3. «Да» на запуск бота 24/7 (сейчас box; для надёжности позже бесплатный хостинг).
4. Решение по налогам с крипто-дохода (продажи только нерезидентам РФ).
5. Опционально: письмо в Polymarket с вопросом о разрешении (см. COMPLIANCE.md).

## Ограничения MVP
- На реальных транзакциях mainnet проверены 9 из 12 способов: USDT (ERC-20, BEP-20, TRC-20, Solana, TON), BTC, ETH, BNB, TON. USDC (ETH, Solana) и нативный SOL используют тот же код, но живой транзакцией не проверялись.
- TON: покупатель может прислать хеш своей транзакции — сверяем hash / in_msg hash / trace_id; если кошелёк покажет другой формат, сработает `/grant` после ручной проверки.
- Бесплатные публичные RPC иногда недоступны — бот отвечает «попробуйте через минуту»; адреса RPC переопределяются через env.
- Kalshi не подключён (условия не проверены).

## 24/7 hosting (GitHub Actions)

The box is not reliable overnight. The intended free host is GitHub Actions on the public `npc-signal` repository (business GitHub account). Short `getUpdates` sessions run every 5 minutes; the SQLite file is stored encrypted on the `state` branch; the journal is published to `gh-pages`.

This is a compromise: replies can lag, and it sits in a grey area of GitHub's Actions terms. Details, limits, and the exact setup steps are in [HOSTING.md](HOSTING.md). Nothing from that plan has been deployed yet.
