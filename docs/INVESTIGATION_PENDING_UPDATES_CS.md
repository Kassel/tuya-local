# Evidence opravy práce s čekajícími změnami

Oprava vychází z logu a stop testů referenčního forku 2026-10-30 13:19–13:22 CET; osobní logy a klíče nejsou součástí repozitáře.

Postupný test (7 světel, 2000 ms): 5 retry po chybě refresh, žádný KeyError, maximální trvání zachované akce 0,266 s. Rychlý test (7 světel, 500 ms): 4 retry refresh, 63 KeyError pro DPS24 a 27 pro DPS21, 30 hlášení Failed to update device state, 7 selhání prvního kroku vyjednání session, maximální trvání akce 24,313 s. Oba skripty formálně dokončeny, koncový report všech světel červený; fyzický stav těmito daty není doložen.

Před opravou: 9 nových regresních případů selhalo; odstraňování položky vyvolávalo tři odeslání, souběžně nahrazený požadavek byl chybně označen sent, dva čekající odesílatelé odeslali starou hodnotu dvakrát, chybový návrat byl ignorován a programové výjimky se opakovaly místo předání volajícímu.

Po opravě cílená sada tests/test_device.py: 62 passed (14,55 s). Čtyři další případy zahrnují skutečné pracovní vlákno, přestavbu požadavku před opakováním, chybu 900 při CONTROL a zrušení čekající úlohy. Kompletní sada: 468 passed, 83,72 s. Ruff check, import order a format check úspěšné. Yamllint skončil úspěšně s dřívějším upozorněním na odsazení komentáře v nezměněném marpou_ceiling_lamp_ledlight.yaml:3.

Přesné pořadí událostí v produkčním logu není prokázáno, protože obsahuje zkrácené výjimky bez tracebacku. Reprodukční testy prokazují konkrétní nebezpečný přístup ve stejném kódu. Oprava zachovává dosavadní limity příjmu DPS a příjem heartbeat/status, neřeší veškeré vlastnictví socketu ani selhání rtw88.
