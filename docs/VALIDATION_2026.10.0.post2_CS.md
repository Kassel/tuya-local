# Fyzické ověření post2 — 2026-10-30

Uživatel dodal dva JSON exporty stop a diagnostický log Tuya Local. Testy zahrnují stejných sedm entit světel jako předchozí srovnávací běh. Záznamy s klíči a surovými daty nejsou součástí repozitáře.

| Ukazatel rychlého testu 500 ms | post1, 13:20:59 | post2, 13:48:12 |
|---|---:|---:|
| Retry KeyError | 90 | 0 |
| Failed to update device state | 30 | 0 |
| Selhání vyjednání session v kroku 1 | 7 | 0 |
| Retry No DPS received after refresh request | 4 | 0 |
| Nejdelší zachovaná akce HA | 24,313 s | 0,0847 s |
| Celkové trvání skriptu včetně přestávek | 72,966 s | 51,672 s |

Postupný test 2000 ms po opravě: 13:46:34–13:48:04, přibližně 89,95 s. Jeden retry refresh v 13:47:03.311, bez KeyError a neúspěšných aktualizací. Maximum zachované akce 0,261 s. Zachováno je pouze posledních 20 opakovaných značek kroků (omezení stopy), nikoli plné časování všech 24 kroků.

Rychlý test po opravě: 13:48:12–13:49:04, přibližně 51,67 s. Časování všech 24 akcí je zachované; medián 53 ms, maximum 84,7 ms. V obou bězích je pro každé světlo 26 záznamů předání změny k odeslání (počáteční nastavení + 24 kroků + závěrečný povel). Koncový sloučený hlášený stav všech sedmi: DPS20=true, DPS21=colour, DPS24=000003e802ed (červená, přibližně 75 %).

V 13:47:15.543 HA upozornil na časté logování modulu light. Jde o diagnostický režim; nezaměňovat počet logových záznamů s počtem paketů.

## Interpretace a omezení

V jednom srovnatelném rychlém běhu se prokazatelně neobjevil původní retry storm a akce HA se zkrátily. Je to pozitivní fyzické ověření opravy, nikoli důkaz odstranění všech příčin opožděných změn. Log zachycuje hlášené stavy, ne fyzickou barvu ani čas změny světla. Uživatel dosud nepotvrdil vizuální výsledek tohoto běhu. Chybí synchronní PCAP a kernelový log; nehodnotíme dlouhodobou stabilitu Wi-Fi. Původní problém refresh zůstává mimo tuto opravu a jednou se projevil v postupném testu.

Doporučení: ponechat post2, vyžádat fyzické pozorování a potom běžný provoz bez diagnostického logování. Další zrychlování testu není pro ověření této konkrétní opravy nyní potřeba.
