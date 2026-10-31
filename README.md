# TrackStock

Aplicação pessoal para acompanhar o mercado e o portefólio de investimentos, a correr no browser a partir do próprio PC.

- **Mercado**: watchlist com cotações de todas as bolsas (ações, ETFs, índices, fundos, câmbio e cripto), pré/pós-mercado, gráfico do dia e gráfico TradingView.
- **Portefólio**: registo manual de compras e vendas (em EUR ou USD), posições com custo médio, ganhos/perdas, alocação e evolução do valor desde a primeira transação.
- **Daily briefing**: resumo diário dos mercados gerado pelo Claude.

**Backend em Python (Flask)**: toda a lógica, cálculos e métricas (cotações, câmbio, posições, histórico, briefing). **Frontend em React (Vite)**: só a parte visual; pede os resultados ao backend e mostra-os. Não precisa de chaves de API.

## Instalação

1. Instala o **Python 3.10 ou mais recente** ([python.org](https://www.python.org/downloads/)) e marca a opção *Add python.exe to PATH*.
2. Instala o **Node.js LTS** ([nodejs.org](https://nodejs.org)), só necessário para compilar o frontend.
3. Na pasta do projeto, instala os pacotes Python:
   ```
   python -m pip install -r requirements.txt
   ```
4. Na pasta `frontend`, instala os pacotes e compila:
   ```
   cd frontend
   npm install
   npm run build
   ```
5. Cria o atalho no ambiente de trabalho: `python scripts\criar_atalho.py`.
6. Opcional, para o daily briefing: **Claude Code** (CLI ou extensão do VS Code) com sessão iniciada.

## Como abrir e fechar

- **Abrir**: duplo clique no atalho **TrackStock** do ambiente de trabalho. O servidor local liga-se em segundo plano (sem janelas) e a app abre numa janela própria do browser predefinido, sem separadores nem barra de endereços (em browsers baseados em Chromium: Chrome, Edge, Brave, Vivaldi). Noutros browsers, como o Firefox, abre num separador normal.
- **Fechar**: fecha a janela da app. O servidor desliga-se sozinho poucos segundos depois de fechares a última janela (um F5 não o desliga).

Para correr o servidor à mão, com consola (útil para ver erros): `python -m backend` na pasta do projeto (opções: `--port 9000`, `--no-browser`, `--auto-stop`).

## Desenvolvimento

- **Backend** (`backend/`): depois de alterar um ficheiro `.py`, fecha a app e abre-a de novo (ou reinicia o `python -m backend`).
- **Frontend** (`frontend/src/`): depois de alterar, corre `npm run build` na pasta `frontend` e faz `Ctrl+F5` na app.
- **Frontend com recarga automática**: com o backend a correr (`python -m backend --no-browser`), corre `npm run dev` na pasta `frontend` e abre `http://localhost:5173`. Cada alteração aparece logo, sem compilar; os pedidos `/api` seguem para o backend.

Para acrescentar uma funcionalidade nova ao backend (ex.: análises), cria `backend/analysis.py` com um `Blueprint` (como os outros módulos) e regista-o em `backend/app.py`. No frontend, chama as rotas novas a partir de `shared/api.js`.

## Funcionalidades

### Mercado
- **Pesquisa por nome ou símbolo** (`apple`, `EDP`, `vanguard all world`, `bitcoin`…), com sugestões de todas as bolsas.
- **Watchlist** com preço, variação do dia e estado de cada bolsa (aberta, pré-abertura, pós-fecho, fechada). Ao passar o rato sobre a bolsa vês o horário em hora de Lisboa, já com as mudanças de hora.
- **Pré/pós-mercado**: último preço fora da sessão regular e a variação face ao fecho (ações dos EUA).
- **Ao vivo**: gráfico de hoje em velas de 1 minuto, com o pré/pós-mercado a tracejado.
- **Gráfico TradingView** do ativo selecionado, com indicadores e intervalos. Se o símbolo convertido não mostrar dados, corrige-o no campo "Símbolo TradingView" (a correção fica guardada).

### Portefólio
- **Transações**: compra ou venda, ativo, data, quantidade e preço por unidade em EUR ou USD. "Usar preço atual" preenche o preço de mercado. O câmbio EUR/USD do dia da transação fica guardado com ela.
- **KPIs**: valor atual, montante investido, ganho/perda não realizado e realizado (método do custo médio).
- **Evolução do portefólio**: até ontem, valor ao fecho de cada dia desde a primeira transação (preços do Yahoo e câmbio do BCE desse dia); hoje, velas de 5 minutos até ao valor atual. Filtros 1H, 1D, 1S, 1M e Tudo.
- **Valorizar com pré/pós-mercado**: opcional; desligado, usa o preço de fecho da sessão regular.
- **Exportar/Importar JSON** para fazer cópias de segurança das transações e da watchlist.

### Daily briefing
- Briefing diário de mercados gerado pelo **Claude** no próprio PC, com a prompt de `historico/briefings/prompt.md` (cópia da rotina "Briefing Diário de Mercados" do claude.ai). Para mudar o conteúdo do briefing, edita esse ficheiro.
- O briefing de hoje começa a ser gerado automaticamente na primeira vez que abres a app no dia (demora 3–8 minutos; podes continuar a usar a app). **Gerar de novo** volta a gerá-lo.
- Cada briefing fica guardado em `historico/briefings/AAAA-MM-DD.md` e os anteriores podem ser escolhidos na lista de datas.
- Requer o **Claude Code** com sessão iniciada: o CLI (`%USERPROFILE%\.local\bin\claude.exe` ou no PATH) ou, se não houver, o `claude.exe` da extensão do VS Code; usa a tua subscrição Claude. O Claude só tem acesso a pesquisa e leitura de páginas web (`WebSearch`, `WebFetch`).

Todos os valores do portefólio são apresentados em euros. Os ativos noutras moedas (USD, GBP, CHF, JPY…) são convertidos com o câmbio do BCE.

## Fontes de dados

| Dados | Fonte | Notas |
|---|---|---|
| Cotações, pesquisa, histórico diário | Yahoo Finance (via `backend/market.py`) | Atualiza a cada 15 s com a bolsa aberta e a cada 5 min com ela fechada. Algumas bolsas têm 15–20 min de atraso. |
| Câmbio | Banco Central Europeu ([Frankfurter](https://frankfurter.dev), via `backend/fx.py`) | Uma taxa por dia útil. Moedas que o BCE não publica vêm do Yahoo. |
| Gráfico avançado | Widget TradingView | Algumas bolsas e índices não têm dados no widget gratuito. |

O Yahoo Finance não tem uma API oficial; pode alterar ou limitar o acesso sem aviso.

## Onde ficam os dados

Transações e watchlist ficam no ficheiro **`historico/transacoes.json`**, gerido pelo backend: é reescrito sempre que adicionas ou apagas uma transação ou mudas a watchlist. Como a pasta está no OneDrive, o ficheiro tem também cópia na nuvem. No browser ficam só preferências da interface (pré/pós-mercado, correções de símbolos TradingView).

O ficheiro tem o mesmo formato do **Exportar JSON**, por isso também pode ser usado em **Importar JSON**. Para guardar versões antigas, copia o ficheiro para outro sítio antes de fazer alterações.

## Estrutura do projeto

```
requirements.txt         pacotes Python (python -m pip install -r requirements.txt)
backend/                 servidor Flask: toda a lógica e cálculos, uma funcionalidade por ficheiro
├── __main__.py          arranque (python -m backend): localhost IPv4/IPv6, --auto-stop
├── app.py               junta os módulos, protege a API, serve o frontend compilado
├── config.py            caminhos e constantes
├── market.py            cotações, sessões das bolsas, pré/pós-mercado, pesquisa, watchlist, símbolos TradingView
├── fx.py                câmbio atual e histórico (BCE / Yahoo)
├── portfolio.py         transações, posições (custo médio), valorização, alocação, histórico
├── briefing.py          daily briefing (Claude Code)
├── presence.py          janelas da app abertas (para o --auto-stop)
├── storage.py           leitura/gravação de historico/transacoes.json
├── http_client.py       pedidos a serviços externos, com cache curta
└── desktop.py           integração com o Windows (abrir no browser predefinido)
frontend/                interface em React, compilada com Vite
├── index.html
├── vite.config.js
├── public/              manifest.webmanifest e ícones (copiados tal como estão)
├── dist/                versão compilada, servida pelo backend (gerada por npm run build)
└── src/
    ├── main.jsx         arranque do React
    ├── App.jsx          barra do topo, separadores, aviso "app desligada"
    ├── styles.css       tema (claro/escuro, segue o Windows)
    ├── pages/           um ficheiro por página da app
    │   ├── Market.jsx
    │   ├── Portfolio.jsx
    │   └── Briefing.jsx
    └── shared/          partilhado entre páginas
        ├── api.js           pedidos ao backend
        ├── format.js        formatação de valores e textos
        ├── hooks.js         hooks React (intervalos, tema, preferências)
        ├── components.jsx   componentes pequenos (pesquisa de ativos, valores com sinal, estado da bolsa)
        └── LineChart.jsx    gráfico de linha (Chart.js)
scripts/
├── abrir.py             o que o atalho executa: liga o servidor (escondido, --auto-stop) e abre o browser predefinido
├── criar_atalho.py      cria o atalho "TrackStock" no ambiente de trabalho
└── gerar_icones.py      desenha os ícones de frontend/public/icons
historico/
├── transacoes.json      transações e watchlist
└── briefings/
    ├── prompt.md        prompt do daily briefing (edita para mudar o conteúdo)
    └── AAAA-MM-DD.md    um ficheiro por dia com o daily briefing
```

### API do backend

| Rota | O que faz |
|---|---|
| `GET /api/market/quote?symbol=&bars=1` | cotação normalizada: preço, variação, pré/pós-mercado, estado da bolsa, símbolo TradingView e (com `bars=1`) o gráfico de hoje |
| `GET /api/market/search?q=` | pesquisa de ativos |
| `GET/POST /api/market/watchlist`, `DELETE /api/market/watchlist/<símbolo>` | watchlist |
| `GET /api/fx` | câmbio atual (unidades por 1 EUR) |
| `GET /api/portfolio?ext=1` | KPIs, posições, alocação e transações |
| `GET /api/portfolio/history?range=<ms>&ext=1` | série do gráfico de evolução |
| `POST /api/portfolio/transactions`, `DELETE /api/portfolio/transactions/<id>` | adicionar/apagar transações (com validação) |
| `GET /api/portfolio/price?symbol=&currency=` | preço atual convertido para EUR ou USD |
| `GET /api/portfolio/export`, `POST /api/portfolio/import` | exportar/importar JSON |
| `GET /api/briefing/list`, `GET /api/briefing?date=`, `POST /api/briefing/generate` | daily briefing |

O servidor só escuta em `localhost` (e recusa pedidos com outro `Host`). A API só responde à própria app: exige o cabeçalho `X-App` e, se houver, a origem `localhost`, para que outros sites abertos no browser não lhe consigam aceder.

Desligar sozinho (`--auto-stop`): cada janela da app avisa o servidor a cada 20 s (`/api/ping`) e despede-se ao fechar (`/api/bye`). Sem janelas abertas durante 8 s, o servidor termina. Se uma janela deixar de dar sinal sem se despedir (ex.: o browser fechou à força), deixa de contar ao fim de 10 min; se a app nunca chegar a abrir, o servidor termina ao fim de 2 min.

## Limitações conhecidas

- **Pré/pós-mercado** só existe para ações dos EUA; as outras bolsas mostram apenas a sessão regular.
- **Dias de fecho antecipado** (ex.: véspera de Natal nos EUA) não são tratados à parte.
- **Desdobramentos (splits)**: os fechos antigos do Yahoo não são ajustados à quantidade registada; o histórico desses dias fica errado até registares o desdobramento como transação.
- **Histórico de hoje** usa as quantidades atuais em todo o dia: uma transação feita hoje conta desde a meia-noite.

## Resolução de problemas

| Problema | Solução |
|---|---|
| Aviso vermelho "A app está desligada" / ponto vermelho | O servidor parou. Fecha a janela e abre a app pelo atalho **TrackStock**. |
| Mensagem "Não foi possível ligar a app" ao abrir | Outro programa está a usar a porta 8765, faltam pacotes Python (`python -m pip install -r requirements.txt`) ou há um erro no servidor. Corre `python -m backend` para ver o erro. |
| Página "Falta compilar o frontend" | Na pasta `frontend`, corre `npm install` e `npm run build`. |
| "Não foi possível gerar o briefing" | Vê a mensagem por baixo. Se for de sessão/autenticação, abre um terminal e corre `claude` para iniciar sessão; depois clica **Gerar de novo**. |
| Gráfico TradingView vazio | Corrige o símbolo no campo "Símbolo TradingView" (ex.: `EURONEXT:EDP`) ou usa "abrir ↗". |
| Alterações ao código não aparecem | Frontend: `npm run build` e `Ctrl+F5`. Backend: fecha todas as janelas da app (o servidor desliga-se), espera uns segundos e abre de novo. |
