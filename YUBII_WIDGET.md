# Widget telefono → Yubii Home (accensioni e termostati)

Questa guida spiega come avere un **pulsante nella schermata home del telefono**
che accende un riscaldamento, imposta un termostato o lancia una scena su
**Yubii Home** (Nice / Fibaro Home Center), comandando dispositivi **già
presenti** in Yubii.

Architettura:

```
  [Widget home telefono]  --HTTP-->  [yubii_bridge.py]  --REST-->  [Yubii Home]
   URL semplice + token              traduce + autentica           dispositivi
```

Il widget chiama solo il **ponte** (`yubii_bridge.py`); le credenziali Yubii
restano nel ponte e non finiscono mai sul telefono. Il ponte gira su un
qualunque dispositivo sempre acceso nella tua rete (Raspberry Pi, NAS, mini PC,
lo stesso host che usi per ESPHome).

---

## 1. Avviare il ponte

Nessuna dipendenza esterna: serve solo Python 3.8+ (solo libreria standard).

```bash
export YUBII_HOST=192.168.1.20        # IP del tuo Yubii Home / Home Center
export YUBII_USER=admin               # utente Yubii (consigliato: utente dedicato)
export YUBII_PASSWORD=la-mia-password
export BRIDGE_TOKEN=$(python3 -c "import secrets;print(secrets.token_urlsafe(24))")
echo "Il tuo token è: $BRIDGE_TOKEN"   # annotalo, serve nel widget

python3 yubii_bridge.py
```

Verifica che sia vivo (da un browser o `curl`):

```bash
curl http://<host-ponte>:8770/
# {"service":"yubii-bridge","endpoints_require_token":true,"ok":true}
```

### Avvio automatico con systemd (consigliato)

Crea `/etc/systemd/system/yubii-bridge.service`:

```ini
[Unit]
Description=Ponte Yubii per widget telefono
After=network-online.target

[Service]
Environment=YUBII_HOST=192.168.1.20
Environment=YUBII_USER=admin
Environment=YUBII_PASSWORD=la-mia-password
Environment=BRIDGE_TOKEN=incolla-qui-il-token
ExecStart=/usr/bin/python3 /percorso/loadcontrol/yubii_bridge.py
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

Poi:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now yubii-bridge
```

---

## 2. Trovare gli ID dei dispositivi / scene

Apri nel browser (sostituendo host e token):

```
http://<host-ponte>:8770/devices?token=IL-TUO-TOKEN
http://<host-ponte>:8770/scenes?token=IL-TUO-TOKEN
```

Cerca il termostato o il relè che ti interessa e annota il suo `id`.
In alternativa l'ID è visibile anche nell'interfaccia web di Yubii/Fibaro
(nelle impostazioni del dispositivo).

---

## 3. Endpoint disponibili

Tutti gli URL accettano **GET** (così funzionano da qualsiasi widget) e
richiedono il token come `?token=...` o header `X-Bridge-Token`.

| Cosa vuoi fare | URL |
| --- | --- |
| Accendere un relè/luce | `/device/<id>/on` |
| Spegnere un relè/luce | `/device/<id>/off` |
| Impostare dimmer/livello (0-99) | `/device/<id>/level/<n>` |
| **Accendere riscaldamento a 21°** | `/thermostat/<id>?temp=21` |
| Modalità + temperatura insieme | `/thermostat/<id>?temp=21&mode=Heat` |
| Solo cambio modalità | `/thermostat/<id>/mode/Heat` (o `Off`, `Auto`, `Cool`) |
| Lanciare una scena | `/scene/<id>/run` |
| Azione Fibaro generica | `/device/<id>/action/<nome>?args=22.5` |

Esempio completo (accendi il termostato 12 a 21 gradi):

```
http://192.168.1.50:8770/thermostat/12?temp=21&token=IL-TUO-TOKEN
```

> Nota sui nomi azione: il ponte usa le azioni standard Fibaro HC3
> (`setHeatingThermostatSetpoint`, `setThermostatMode`, `turnOn`, `turnOff`,
> `setValue`). Se un tuo dispositivo usa un'azione diversa, usa l'escape hatch
> `/device/<id>/action/<nome>?args=...` (gli argomenti numerici vengono
> convertiti automaticamente; separa più argomenti con la virgola).

---

## 4. Creare il widget sulla schermata home

### iPhone / iPad — app **Scorciatoie** (Shortcuts)

1. Apri **Scorciatoie** → `+` per una nuova scorciatoia.
2. Aggiungi l'azione **«Ottieni contenuto dell'URL»** (Get Contents of URL).
3. Incolla l'URL completo, es.
   `http://192.168.1.50:8770/thermostat/12?temp=21&token=IL-TUO-TOKEN`
   (metodo **GET**).
4. Dai un nome e un'icona alla scorciatoia (es. «Accendi salotto 🔥»).
5. Vai sulla schermata home → tieni premuto → `+` → **Scorciatoie** →
   scegli il widget e seleziona la scorciatoia.

Tocca il widget: parte l'accensione. (Funziona quando il telefono è sulla
rete di casa o via VPN.)

### Android — app **HTTP Shortcuts** (gratuita, consigliata)

1. Installa *HTTP Shortcuts* dal Play Store.
2. **Create Shortcut** → metodo **GET** → incolla l'URL completo con token.
3. Salva, scegli nome e icona.
4. Tieni premuto sulla home → **Widget** → *HTTP Shortcuts* → scegli la
   scorciatoia.

In alternativa puoi usare **Tasker** o un semplice segnalibro del browser.

---

## 5. Sicurezza

- **Tieni il ponte solo sulla LAN.** Non esporlo direttamente su Internet:
  per l'accesso da fuori casa usa una **VPN** (es. WireGuard) verso casa.
- Il **token** evita che chiunque sulla rete possa comandare la casa: usane uno
  lungo e casuale. Senza token impostato il ponte avvisa ed è aperto a tutti.
- Crea in Yubii un **utente dedicato** per il ponte, invece di usare l'admin.
- L'URL contiene il token: va bene per uso personale sulla LAN, ma evita di
  condividerlo o salvarlo in posti pubblici.

---

## 6. Risoluzione problemi

| Sintomo | Causa probabile |
| --- | --- |
| `401 token mancante o errato` | token assente o diverso da `BRIDGE_TOKEN` |
| `502 impossibile raggiungere Yubii` | `YUBII_HOST` errato o Yubii spento |
| `502 Yubii ha risposto 401` | utente/password Yubii errati |
| `502 Yubii ha risposto 404` | ID dispositivo/scena inesistente |
| L'azione non ha effetto | il dispositivo usa un'azione diversa → usa `/device/<id>/action/<nome>` |

Per il dettaglio degli errori il ponte risponde sempre con un JSON
`{"ok":false,"error":"..."}`.
