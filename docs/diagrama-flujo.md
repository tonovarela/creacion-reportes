    # Diagrama de flujo

## 1. Proceso semanal

`orquestador.py` corre los tres pasos en orden y se detiene si alguno falla. Desde el panel web se lanza
el mismo proceso, completo o por pasos.

```mermaid
flowchart TD
    inicio(["Inicio: orquestador.py o panel web"]) --> tieneExcel{"¿Se indicó --excel?"}

    tieneExcel -- No --> p1["<b>1. extraer_excel.py</b><br/>corre sql/NN-*.sql en orden"]
    sql[("SQL Server<br/>DataIA")] -.-> p1
    p1 --> xlsx[/"entrada/AAAA-Wnn.xlsx<br/>una hoja por consulta"/]
    tieneExcel -- Sí --> xlsx

    xlsx --> p2["<b>2. gen.py</b><br/>calcula indicadores por vendedor<br/>y firma un token por liga"]
    p2 --> internos[/"salida/reportes/<br/>reportes con nombre (uso interno)"/]
    p2 --> publicos[/"salida/public/año/sem/token/<br/>reportes publicables"/]
    p2 --> avisos[/"salida/avisos-SEM.json"/]
    p2 --> ligas[/"salida/ligas-SEM.csv<br/>vendedor, correo, liga"/]

    ligas --> modo{"Modo de correos"}
    modo -- "sin bandera" --> vista["<b>3. enviar_correos.py</b><br/>solo vistas previas<br/>salida/correos-SEM/*.html"]
    modo -- "--prueba CORREO" --> prueba["<b>3. enviar_correos.py</b><br/>todos los correos a una sola cuenta<br/>sin copia oculta"]
    modo -- "--enviar" --> cco{"¿CORREO_CCO<br/>en .env?"}
    cco -- No --> alto1(["Se detiene"])
    cco -- Sí --> crit{"¿Avisos críticos?"}
    avisos -.-> crit
    crit -- "Sí, sin --ignorar-avisos" --> alto2(["Se detiene:<br/>revisar avisos"])
    crit -- "No, o --ignorar-avisos" --> real["<b>3. enviar_correos.py</b><br/>envío real a cada vendedor<br/>con copia oculta a CORREO_CCO"]

    real --> registro[/"salida/envios-SEM.csv<br/>si se repite, omite a quien ya recibió"/]
    real --> smtp[("SMTP Google Workspace<br/>587 STARTTLS / 465 SSL<br/>con reintentos")]
    prueba --> smtp
    smtp --> buzon(["Correo con la liga<br/>al reporte del vendedor"])
```

## 2. Despliegue y acceso

```mermaid
flowchart TB
    subgraph usuarios[Usuarios]
        admin["Operador<br/>(red interna)"]
        vendedor["Vendedor<br/>(internet)"]
    end

    subgraph servidor["Servidor Linux"]
        apache["Apache<br/>servicios.litoprocess.com"]
        subgraph contenedor["Contenedor tonovarela/reportes-ventas<br/>127.0.0.1:8888 → 8000 (uvicorn, uid 1000)"]
            filtro{"Filtro ADMIN_REDES"}
            panel["Panel web y API<br/>FastAPI + JS + Tailwind"]
            trabajos["Trabajos<br/>(uno a la vez, log en vivo por SSE)"]
            scripts["extraer_excel.py → gen.py → enviar_correos.py"]
            estaticos["/reportes/<br/>sirve salida/public/"]
        end
        vol[("Volúmenes<br/>./entrada  ./salida")]
    end

    admin -- "/panel-reportes/<br/>Require ip: red interna" --> apache
    vendedor -- "/panel-reportes/reportes/año/sem/token/<br/>público" --> apache
    apache -- "ProxyPass + X-Forwarded-For" --> filtro
    filtro -- "IP interna" --> panel
    filtro -- "cualquier IP, solo /reportes/" --> estaticos
    panel --> trabajos --> scripts
    scripts <--> vol
    estaticos --> vol
    scripts -.-> sqlsrv[("SQL Server")]
    scripts -. "correo con la liga<br/>al vendedor" .-> gmail[("SMTP Google")]
```
