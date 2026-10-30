# 2026.10.0.post2 — oprava evidence odesílaných povelů

Předběžné vydání pro kontrolované ověření přes HACS. Neopravuje Wi-Fi ovladač a nemění příjem v DPS helperu.

## Problém

Při rychlém ovládání mohl stavový report nebo novější požadavek změnit seznam čekajících DPS, zatímco pracovní vlákno odesílalo předchozí povel. Následné označení položky jako odeslané pak mohlo vyvolat KeyError nebo nesprávně označit novější hodnotu jako již odeslanou. Obecné opakování operace po KeyError vedlo k dalším povelům a obnovám spojení.

V testu referenční verze ze dne 2026-10-30 bylo v rychlém běhu zaznamenáno 90 retry s KeyError a maximální trvání akce HA 24,313 s. Deterministické regresní testy nad referenčním kódem selhaly; po opravě procházejí.

## Změny

- Síťové vlákno pouze odesílá data a vrací výsledek TinyTuya. Evidenci čekajících změn upravuje hlavní smyčka HA.
- Každý pokus připraví aktuální neodeslané hodnoty až po získání komunikačního zámku. Prázdný nebo již odbavený požadavek se neposílá.
- Úspěch označí pouze původní položku, pokud stále existuje. Novější požadavek, i se stejnou hodnotou, zůstává neodeslaný.
- Chybový návrat TinyTuya se předá dosavadní obsluze chyb; neoznačí se jako úspěšné odeslání.
- KeyError, IndexError a TypeError se předají volajícímu; nejsou důvodem k opakování a resetování spojení.
- DPS helper zůstává bajtově shodný s verzí post1 a funkční zálohou.

## Ověření

Přidáno 13 regresních případů včetně skutečného pracovního vlákna řízeného synchronizačními bariérami, souběžně čekajících odesílatelů, novějšího požadavku při opakování a zrušení úlohy čekající na zámek. Tyto testy nepředstavují ověření zrušení již běžícího síťového vlákna ani všech souběhů přijímací smyčky.

Kompletní místní sada: **468 testů prošlo** (83,72 s). Kontroly Python kódu prošly; YAML kontrola má pouze dřívější upozornění v nezměněném profilu. DPS helper má nadále SHA-256 `2514264adbbbc54fc6d6a8c6ce952a09e6d30486946c6b4c75eca1a637f203aa`.

## Známá omezení

Původní předčasné ukončení refresh po prázdném potvrzení zůstává k samostatnému řešení. Síťové chyby a selhání vyjednání session se mohou nadále objevit. Oprava nebyla před vydáním fyzicky ověřena na světlech; počet odstraněných chyb v reálném provozu bude teprve změřen.

## Postup ověření v HA

1. Ověřit ping z Lenova a běžné ovládání před instalací. Ponechat zálohu a referenční vydání v2026.10.0.post1.
2. V HACS vybrat Kassel/tuya-local a konkrétní v2026.10.0.post2. Vyčkat dokončení stahování, pak restartovat pouze HA.
3. Ověřit jednotlivé světlo; poté při zapnutém diagnostickém logování spustit stejný postupný test 2000 ms a rychlý 500 ms se stejným výběrem světel.
4. Uložit log, stopy a fyzický konečný stav. Kontrolovat zvlášť KeyError, dobu akcí HA, obnovy spojení a chyby refresh.
5. Při regresi v HACS vybrat označenou post1; při úplném výpadku nejdřív ověřit síť a ovladač, aby se nezaměnil síťový problém za regresi kódu.
