# Výchozí stav vývoje Tuya Local

## Zachované podklady

- Fork: https://github.com/Kassel/tuya-local
- Výchozí HEAD forku: 01df3fc8 (2026-10-29). Při přípravě nebyl změněn integrační kód.
- Referenční instalace: tuya_local-zaloha-20261030-100921.tar.gz, uložená mimo repozitář.
- Manifest obou variant uvádí 2026.10.0; nejde o důkaz shodných zdrojů.
- Dřívější úprava byla připravena nad 245469649fb2df6767988213dd6ae9dcb3b3e0f6. Záloha se od něj liší také profily zařízení; ne všechny rozdíly jsou našimi úpravami.
- Zálohy, diagnostické logy, PCAP a konfigurační exporty zařízení nejsou určeny ke zveřejnění v repozitáři.

## Potřebná funkčnost

Volitelné explicitní DPS pro zařízení, která odmítají standardní status dotaz, ale odpovídají na UPDATEDPS v protokolu 3.5. Zachovat nastavení již přidaných zařízení, současné entity a chování zařízení bez této volby.

## Potvrzené pozorování a omezení

Původní helper může při None z receive předčasně ukončit načítání bez DPS. Logy ukazují prázdné potvrzení staršího povelu těsně před chybou 902 a nové vyjednání spojení. Samotné nahrazení break za pokračování způsobilo uživatelem potvrzenou regresi; po rollbacku funkce obnovena. Přesný mechanismus regrese nebyl dokázán. Není správné prohlásit delší čekání za bezpečné pouze na základě jednotkového testu helperu.

## Návrhové podmínky

1. Pro provozní spojení musí být jednoznačný vlastník příjmu zpráv; prověřit konkurenci receive loop, heartbeat, refresh a odesílání.
2. Rozlišit počáteční získání stavu od periodického refresh na běžícím spojení.
3. Prázdné potvrzení není stav DPS ani automatický důkaz síťové chyby.
4. Změny timeout/retry/persistence musí mít řízený životní cyklus a nesmí narušovat jiné úlohy.
5. Testovat dobu držení API zámku, zrušení úlohy a nepřítomné zařízení; časové limity skutečně měřit.
6. Nejprve reprodukovat původní problém a regresi, potom zvolit minimální opravu.

## Ověření a vydávání

Připravit prostředí uv podle AGENTS.md, spustit původní testy a zaznamenat výchozí chyby před změnou kódu. Doplnit testy skutečného chování TinyTuya 1.20.0 a integrační testy souběhu. Poté projít povinné kontroly repozitáře. Vydávat označené testovací verze pro HACS s návratem ke konkrétní verzi. Publikace a instalace zatím neproběhly.

## Referenční přenos 2026.10.0.post1

Přenos podpory DPS z funkční zálohy připraven na větvi codex/functional-baseline. Příjmová logika helperu zachována. Nová oprava souběhu není součástí tohoto vydání. Výsledky kontrol: viz TEST_RESULTS_BASELINE.md. GitHub zápis při přípravě vyžadoval přihlášení; publikace a instalace v HA dosud neprovedeny.
