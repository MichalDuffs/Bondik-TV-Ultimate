# Niky: první klíček k hudbě — izolovaný experiment

Samostatný návrh pro Bond City v repozitáři Bondík-TV. Produkční App ani
LivePreview jej neimportují. Žádné připojení Niky, Bridge, Spidera, plánovač,
pasivní sledování, persistence ani změna NIKOLA PR #444.

## Kontrakt

Host vytvoří `createMusicKey({ media, tracks, maxVolume: 0.2 })` s vlastním
HTML audio elementem a lidsky schváleným seznamem `{ id, url }` (HTTPS).
Vytvoření nevolá přehrávač. Výchozí stav je OFF.
Host si ponechá `host`; budoucí ověřený adaptér Niky dostane pouze
`agent.command({ action: 'play', trackId })`, `pause` a `stop`.
Žádný adaptér Niky zatím neexistuje. Příkazy v testech jsou testovací vstupy,
nikoli Nikčina rozhodnutí.

Člověk explicitně povolí relaci `host.enable()`. Hlasitost příkaz nemůže zvýšit
nad nakonfigurovaný strop (nejvýše 20 % softwarové škály; nejde o limit dB).
STOP okamžitě zavolá pause, odstraní zdroj a odebere oprávnění. Zruší i čekající
play; novou relaci nelze povolit do jeho dokončení. Chyba play relaci vypne,
bez opakování a bez zveřejnění textu chyby. Pokud se play nikdy nevyřeší,
STOP přesto odpojí zdroj a relace zůstane uzamčená; host může vytvořit novou instanci.

Host a media adaptér jsou důvěryhodné. Toto není izolace proti libovolnému JS
kódu s přístupem k DOM; přímé ovládání audio elementu obchází toto API.
Schválení URL se vztahuje i na jejího poskytovatele a případná přesměrování.
Žádný příkaz nepřiděluje oprávnění ke kódu, paměti ani jiným zařízením.
Poradní Spider ani jeho pass neudělují tento klíček. V362 zůstává beze změny.

## Ověření

Z kořene repozitáře, bez instalace závislostí a bez síťových požadavků:

```sh
node --test experiments/niky-music-key/controller.test.mjs
```

Testy používají fake media adaptér a neplatnou doménu example.invalid.
Ověřují OFF, výběr ID, hlasitost, pause, STOP během play, chyby a zákaz rozšíření
oprávnění. Nepotvrzují zvuk, browser autoplay ani skutečné rozhodování Niky.

### Ruční lokální zvukový smoke test

Z kořene izolovaného checkoutu spusť na Blacku:

```powershell
py -m http.server 8765 --bind 127.0.0.1 --directory experiments/niky-music-key
```

Otevři `http://127.0.0.1:8765/smoke.html`. Server ukončíš Ctrl+C.
Stránka používá lokálně vytvořený dvousekundový WAV tón s fade-in/out.
Důvěryhodný fixture adaptér převádí virtuální schválenou HTTPS adresu
na tento blob; žádná externí skladba ani rádio se nestahuje.
Je to ruční simulace příkazů, nikoli propojení Niky. Hlasitost API je 10 %.

1. Bez povolení klikni Přehrát: výsledek `disabled`, bez zvuku.
2. Povol relaci a přehraj tón: `playing`; potvrď skutečný zvuk poslechem.
3. Zkus pause a nepovolenou skladbu: `paused` / `rejected`.
4. Dej STOP během tónu: `enabled: false`, `hasSource: false`, zvuk skončí;
   další play vrátí `disabled`.
5. Povol relaci, zvol čekající výsledek, dej STOP a dokonči výsledek:
   `cancelled`, zdroj zůstane odpojený. Čekání zde simuluje promise,
   nepředstavuje skutečnou síťovou latenci.
6. Povol relaci a simuluj chybu play: `error`, relace se vypne.

Zaznamenej SHA (`git rev-parse HEAD`), verzi prohlížeče a výsledky každého bodu.
Výpis je omezený na 40 řádků v paměti stránky, bez ukládání či odesílání.
Test na Blacku není splněn pouhým vytvořením této stránky.

## Otevřené acceptance brány

- Nezávislá kritika konkrétního kódu/SHA a vyhodnocení připomínek.
- Ruční browser smoke na Blacku: lidské enable, skutečný výběr Niky ze seznamu,
  doložené přehrávání, pause, STOP i během načítání, odmítnutý zdroj/autoplay.
- Doklad, že po STOP již nedojde k přehrávání a další play vyžaduje lidské enable.
- Výslovné lidské schválení před jakýmkoli produkčním propojením v samostatném PR.

Draft je podklad k revizi, nikoli udělený produkční klíček.
