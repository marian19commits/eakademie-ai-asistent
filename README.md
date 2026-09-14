# eAkademie AI Asistent

Flask aplikace pro eAkademie AI asistent s podporou streamování odpovědí přes SSE, strukturovaných výstupů, Azure OpenAI a připraveností pro Kubernetes.

## Klíčové funkce
- chat rozhraní pro eAkademie
- streamování odpovědí po částech (SSE)
- validace vstupní zprávy
- ukládání historie konverzace do Flask session
- Docker podpora pro lokální i produkční nasazení

## Použité technologie
- Python 3.11+
- Flask
- Azure OpenAI (GPT-4o)
- Pydantic
- Gunicorn
- Docker / Kubernetes

## Struktura projektu
- app.py – hlavní Flask aplikace a routy
- config.py – konfigurace aplikace načítaná z prostředí
- prompts_eakademie.py – systémový prompt pro eAkademie asistenta
- templates/chateAkademieAIJson.html – frontend chat UI se streamováním
- static/style.css – sdílené styly, pokud jsou používány
- .env – lokální konfigurace a tajné hodnoty (nikdy necommitovat)
- .env.example – ukázková konfigurace bez tajných hodnot
- deployment.yaml – Kubernetes manifesty pro produkční nasazení

## Lokální spuštění

### 1. Vytvoření virtuálního prostředí
python -m venv .venv

### 2. Aktivace prostředí
Windows PowerShell:
.venv\Scripts\Activate.ps1

Windows CMD:
.venv\Scripts\activate.bat

### 3. Instalace závislostí
pip install -r requirements.txt

### 4. Nastavení .env
Zkopíruj .env.example do .env a doplň skutečné hodnoty.

Doporučené proměnné:
APP_NAME=eAkademie AI asistent
VERSION=v1.0
DEBUG=True
SECRET_KEY=change-me
RELATIVE_URL=
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_KEY=...
AZURE_OPENAI_DEPLOYMENT=gpt-4o
AZURE_API_VERSION=2024-12-01-preview
PORT=5000
FLASK_DEBUG=0

Pokud se objeví connection error, zkontroluj hlavně:
- AZURE_OPENAI_ENDPOINT musí být plný Azure endpoint včetně https://
- AZURE_OPENAI_KEY musí být platný klíč pro daný resource
- AZURE_OPENAI_DEPLOYMENT musí přesně odpovídat názvu deploymentu v Azure OpenAI
- AZURE_API_VERSION musí být podporovaná verze API pro tvůj resource
- síť nesmí blokovat odchozí spojení na Azure OpenAI

Pro Kubernetes nasazení používej deployment.yaml pouze jako šablonu bez citlivých údajů. Tajné hodnoty ukládej do Kubernetes Secret a do deploymentu je připojuj přes valueFrom.secretKeyRef.

### 5. Spuštění aplikace
python app.py

Aplikace bude dostupná na:
http://localhost:5000

## Docker

### Build image
docker build -t eakademie-ai-asistent .

### Run container
docker run --rm -p 5000:5000 --env-file .env eakademie-ai-asistent

## Doporučení pro provoz
- .env nikdy necommitovat do repozitáře
- staré šablony a statické soubory odstranit nebo přesunout do archivu, pokud už nejsou používané
- před nasazením ověřit Azure endpoint, deployment a klíč
- pro produkci používat Docker nebo Gunicorn, ne Flask development server

## Stav projektu
Projekt je zjednodušený na jeden hlavní chatbot flow pro eAkademie, je kompletně zabezpečený a připravený pro prezentaci v portfoliu nebo další rozšiřování.

---
Autor: Marián Kraus
GitHub: https://github.com/marian19commits
