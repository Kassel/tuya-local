# 2026.10.0.post1 — referenční testovací verze Kassel

Stav: připraveno místně, dosud nepublikováno ani neověřeno na skutečných světlech přes HACS.

## Účel

Převést funkční podporu explicitního načítání DPS ze zálohy instalace do verzovaného forku. Tato verze ještě neopravuje zpoždění světel ani zacházení s prázdným potvrzením.

## Změny

- Zachovává volbu `refresh_dpids`, existující doménu `tuya_local` a identifikaci zařízení.
- Přenáší původní funkční helper beze změny jeho pravidel příjmu.
- Prázdná volba DPS zachovává standardní status dotazy.
- Formulář využívá aktuální probatio z forku; vlastní validátor běží až při zpracování vstupu, aby nezpůsoboval dřívější chybu serializace formuláře.
- Přidává testy parseru, obnovy nastavení spojení, omezení příjmu, směrování stavových dotazů a zachování uložených DPS.
- Test `test_baseline_empty_ack_still_returns_902` výslovně dokumentuje dosud neopravenou chybu.

## Omezení

Jde o přenos na aktuální základ forku, nikoli binárně shodnou kopii celé instalace. Profily a další změny původního projektu nebyly nahrazovány starší zálohou. Explicitní DPS jsou podporované pouze pro přímo připojená zařízení; nikoli děti gateway. Jednotkové testy samy nedokazují správné chování s fyzickým zařízením ani dostupnost po restartu HA.

## Kontrolovaný test v HA po publikaci

1. Ponechat úplnou zálohu HA i archiv předchozí integrace.
2. V HACS přejít na fork až po ověření konkrétního vydání a správného zdroje. Neinstalovat současně dva zdroje do stejné domény. Přidaná zařízení neodstraňovat.
3. Instalovat konkrétní označenou verzi a restartovat HA; ověřit načtení všech nastavení.
4. Nejprve změnit jednotlivé světlo. Zátěž spustit pouze při funkční běžné komunikaci.
5. Souběžně uložit diagnostický log, PCAP a stopu testovacího skriptu, zaznamenat fyzický konečný stav.
6. Při regresi návrat pomocí zálohy. Návrat na čisté upstream vydání sám nezaručuje podporu uložené volby refresh_dpids.

Výchozí upstream testy: 431 úspěšných, 83,96 s. Prostředí: Python 3.14.2, HA 2026.10.2, TinyTuya 1.20.0, probatio 0.13.0. Výsledky po přenosu jsou zaznamenány samostatně v TEST_RESULTS_BASELINE.md.
