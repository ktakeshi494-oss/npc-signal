# Polymarket ToS / API: что разрешено и как сформулирован продукт
Прочитано 26.11.2026: Terms of Use polymarket.com (Effective August 11, 2026, сохранены в tos/tos.txt), docs: Geographic Restrictions, Rate Limits, Data API v2 overview, Builder Program (tos/*.md).

## Что говорят условия
1. **Restricted Persons (торговля запрещена):** US, UK, France, Germany, Italy, Poland, Russia, Singapore, Australia, Belgium, Ontario/Quebec/BC/Alberta, Taiwan, Thailand, Netherlands, NZ, Hungary, Ireland, Slovakia, Slovenia и др. При этом: «If you are in a Restricted Jurisdiction, you are only permitted to use the Content Features» → чтение информации (Content Features) разрешено даже из РФ, запрещена торговля (Technology Features/Platform). Наш сервис торговлю не использует, ордера не ставит.
2. **Data clause:** запрещено пользоваться Data (в т.ч. через API, в raw/derived/aggregated виде), если ты Capital Market Client (брокеры, маркет-мейкеры, хедж-фонды, prop-фирмы, банки, биржи, финтех) или market data distributor; запрещено продавать/перераспределять Data таким клиентам без письменного согласия. Продажа ритейл-трейдерам прямо не запрещена.
3. **Запрет скрейпинга** «robots, crawlers… to scrape… from the Site, Interface or Features» и «any manual process to monitor or copy… for any unauthorized purpose». Публичные Gamma/Data API документированы, без ключа («All data routes are public»), с опубликованными лимитами; OpenAPI спецификация Data API под MIT. Мы используем только их, не парсим сайт.
4. **«Sublicense, sell, or otherwise distribute the Interfaces or Features, or any portion thereof»** — мы не перепродаём интерфейс/данные как есть, а продаём собственные производные алерты и выборку. Это серая зона (пункт 2 подразумевает, что коммерческое использование для ритейла допустимо, но прямого разрешения нет).
5. **Не советы:** ToS сами подчёркивают «not investment advice» — мы тоже.
6. **Товарный знак:** имя Polymarket в бренде не используем.

## Вывод: продукт возможен, с ограничениями (встроены в код и тексты)
- Только публичные документированные API, вежливые лимиты (≈30–60 запросов за цикл против лимитов в сотни/10 с), обработка 429/Retry-After, User-Agent с контактом. Никакого скрейпинга страниц.
- Продаём только физлицам для личного использования; запрещаем Capital Market Clients и data-реселлеров (terms §3c, §5), запрет перепродажи алертов.
- Не продаём резидентам РФ (282-ФЗ) и лицам из санкционных регионов; предупреждаем, что торговля на Polymarket запрещена во многих странах, и запрещаем обход VPN.
- Нет ссылок-рефералок, нет «копируй ставку», нет торговли за пользователя, нет советов; формулировки только фактические («large trade», «price move»), никаких «insider» обвинений.
- Бренд «Prediction Pulse», дисклеймер «not affiliated with Polymarket».
- **Остаточный риск:** формулировки п.3–4 широкие; Polymarket может в любой момент закрыть доступ к API или потребовать прекратить. Рекомендую до масштабирования написать им (builders/press) и спросить разрешение на ритейл-алерты; это шаг, требующий одобрения Владимира.
- Kalshi в MVP НЕ подключён: их условия API я не проверял. Добавлять только после проверки.
