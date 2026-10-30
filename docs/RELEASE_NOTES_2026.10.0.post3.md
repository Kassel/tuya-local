# 2026.10.0.post3 — provozní obnova DPS přes jedinou přijímací smyčku

Předběžné vydání pro fyzické ověření. Navazuje na opravu čekajících povelů v post2.

## Problém a výsledné chování

Při provozní obnově DPS mohl prázdný ACK předchozího CONTROL vyvolat chybu 902 a zavření funkčního spojení přibližně 11–13 ms po dotazu. PCAP spolu s debug logem potvrdil, že skutečné stavové reporty přicházely až za 31–85 ms a klient je po zavření odmítal resetem.

U přímých zařízení s refresh_dpids a persistentním spojením nyní obnovování pouze odešle UPDATEDPS. Následná data zpracovává běžná přijímací smyčka, která ignoruje prázdné ACK a postupně publikuje skutečné DPS reporty. Rozdělené reporty sloučí pro označení dokončeného full poll. Odesílání dotazu nečeká pod komunikačním zámkem na celou stavovou odpověď.

Příjem, heartbeat a změny persistence pro tato zařízení používají stejný API zámek jako odesílání a vyjednávání session. Tím nemají současně manipulovat s jedním socketem. Idle příjem kontroluje připravenost socketu a nezavádí nový krátký socket timeout, který by mohl zahodit rozdělený TCP rámec. TinyTuya zpracuje vždy nejvýše jednu zprávu bez vnitřního opakování příjmu prázdného ACK.

Chybějící/částečná odpověď sama nevyvolává chybu 902 a restart. Při dalším pravidelném intervalu se odešle nový dotaz; neúplná obnova se zaznamená na DEBUG úrovni. Skutečné chyby přenosu zůstávají předmětem stávající obnovy spojení.

## Zachované chování

- Původní bounded collector query_refreshed_dps pro úvodní načtení a poll-only režim nebyl změněn. Jeho dřívější omezení při prázdném ACK v těchto režimech tedy zůstává.
- Parser, konfigurace zařízení, podporované DPS a protokol se nemění.
- Zařízení bez explicitního refresh_dpids používají dosavadní cestu.
- Oprava čekajících povelů z post2 zůstává zachována.

## Testy a omezení

Lokální kontrola: **482 testů prošlo**. Ruff (včetně importů a formátování) prošel. Yamllint prošel s existujícím upozorněním na odsazení komentáře v nezměněném profilu marpou_ceiling_lamp_ledlight.yaml.

Testy zahrnují ACK před skutečnými daty, sloučení reportů, chybějící report bez záplavy dotazů, opakování až po intervalu, skutečnou chybu socketu, zamykání heartbeat/příjmu, zachování setup/poll-only cesty a skutečné šifrované rámce TinyTuya 1.20.0 / protokolu 3.5 přes socketpair. Společný test přijímací smyčky prokazuje, že CONTROL může proběhnout mezi ACK a opožděnými stavovými daty bez zavření spojení.

Při částečně doručeném nebo poškozeném rámci může čtení stále čekat na původní socket timeout TinyTuya a po tuto dobu držet zámek. Tato verze nezavádí vlastní streamový buffer, neřeší všechny možné případy zrušení již běžícího executor vlákna a neřeší selhání Wi-Fi ovladače. Neúplná DPS odpověď sama neoznačí zařízení jako nedostupné; skutečné přenosové chyby se dál zpracovávají původním způsobem.

## Test v HA

Instalovat přes HACS výslovně v2026.10.0.post3 z Kassel/tuya-local, vyčkat dokončení stahování, restartovat HA. Nejprve jednotlivé světlo. Pak pouze barva 500 ms, stejná světla, debug Tuya Local + PCAP + stopa. Ověřit četnost refresh chyb, obnov spojení, prodlevy akcí a fyzický konečný stav. Při regresi je připraven návrat na označenou v2026.10.0.post2.

Nejde o potvrzení fyzické funkčnosti nové verze: to bude ověřeno až po nasazení na testovaná světla.
