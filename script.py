import requests
import gzip
import xml.etree.ElementTree as ET
import io
import json
import os
import hashlib
import random
import re
import unicodedata
from datetime import datetime

feed_url = "https://feeds.whatjobs.com/sinerj/sinerj_pt_BR.xml.gz"

json_folder = "json_parts"
os.makedirs(json_folder, exist_ok=True)

file_count = 1
jobs = []

estados_permitidos = [
    "são paulo",
    "paraná",
    "santa catarina",
    "rio grande do sul"
]

cidade_bloqueada = "campinas"


# Validação conservadora de salário: não confundir números de benefícios com remuneração.
MONEY_NUMBER = (
    r"(?:"
    r"\d{1,3}(?:\.\d{3})+(?:,\d{2})?"
    r"|\d{1,3}(?:,\d{3})+(?:\.\d{2})?"
    r"|\d+(?:,\d{2}|\.\d{2})?"
    r")"
)
SALARY_AMOUNT_RE = re.compile(
    rf"\b(?:faixa salarial|piso salarial|sal[aá]rios?|remunera[cç][aã]o|proventos)\b"
    rf"(?:\s+(?:fixo|base|mensal(?:\s+de)?|bruto|inicial|m[ií]nimo garantido|"
    rf"oferecido|oferecida|oferecidos|oferecidas|de at[eé]|a partir de|entre)){{0,3}}"
    rf"\s*(?:[:：=–—-]\s*)?"
    rf"(?:(?:a partir de|de|entre)\s+)?"
    rf"(?P<amount>(?:R\$\s*)?{MONEY_NUMBER})(?![\d.,])",
    re.IGNORECASE,
)

def normalize_salary_text(text):
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", text).strip().lower()

def has_real_salary(salary):
    value = normalize_salary_text(salary)
    if not value:
        return False
    placeholders = (
        "a combinar", "nao informado", "nao informada",
        "nao divulgado", "nao divulgada", "confidencial",
        "negociavel", "sob consulta", "salario nao informado",
        "salario a combinar",
    )
    if any(marker in value for marker in placeholders):
        return False
    if not re.search(r"\d", value):
        return False
    if not re.search(r"(?:R\$|[$€£])", value) and re.fullmatch(r"\d+", value):
        return False
    return True

def extract_salary(structured_salary, description):
    structured_salary = re.sub(r"\s+", " ", structured_salary or "").strip()
    if has_real_salary(structured_salary):
        return structured_salary
    text = re.sub(r"<[^>]+>", " ", description or "")
    text = re.sub(r"\s+", " ", text).strip()
    for match in SALARY_AMOUNT_RE.finditer(text):
        amount = re.sub(r"\s+", " ", match.group("amount")).strip()
        raw_number = re.sub(r"^R\$\s*", "", amount, flags=re.IGNORECASE).strip()
        if not amount.upper().startswith("R$") and re.fullmatch(r"\d{1,2}", raw_number):
            continue
        return amount
    return ""


headers = {
    "User-Agent": "Mozilla/5.0 (compatible; FeedProcessor/1.0)"
}

def normalizar(texto):
    return texto.strip().lower()

def gerar_id(titulo, empresa, cidade, url):
    base = f"{titulo}-{empresa}-{cidade}-{url}"
    return hashlib.md5(base.encode()).hexdigest()

def gerar_slug(titulo, cidade):
    texto = f"{titulo}-{cidade}"
    texto = texto.lower()
    texto = re.sub(r"[^\w\s-]", "", texto)
    texto = re.sub(r"\s+", "-", texto)
    return texto

def limpar_html(texto):
    return re.sub(r"<[^>]+>", "", texto).strip()

def gerar_intro(titulo, cidade):
    intros = [
        f"Confira a vaga para {titulo} em {cidade}. Veja os detalhes e como se candidatar.",
        f"Nova oportunidade para {titulo} em {cidade}. Saiba mais sobre essa vaga.",
        f"Empresa está contratando {titulo} em {cidade}. Confira requisitos e envie seu currículo."
    ]
    return random.choice(intros)

print("📥 Baixando feed...")

try:
    response = requests.get(feed_url, stream=True, headers=headers, timeout=30)
except requests.RequestException as e:
    print(f"Erro: {e}")
    exit(1)

if response.status_code == 200:
    with gzip.open(io.BytesIO(response.content), "rt", encoding="utf-8") as f:
        urls_vistas = set()

        for event, elem in ET.iterparse(f, events=("end",)):
            if elem.tag == "job":
                title = elem.findtext("title", "").strip()
                description = elem.findtext("description", "").strip()
                company = elem.findtext("company/name", "").strip()
                job_type = elem.findtext("jobType", "").strip()
                source_salary = elem.findtext("salary", "").strip()
                url = elem.findtext("urlDeeplink", "").strip()

                location_elem = elem.find("locations/location")
                city = location_elem.findtext("city", "").strip() if location_elem is not None else ""
                state = location_elem.findtext("state", "").strip() if location_elem is not None else ""

                if not city or not state or not title or not url:
                    elem.clear()
                    continue

                city_lower = normalizar(city)
                state_lower = normalizar(state)

                if state_lower not in estados_permitidos:
                    elem.clear()
                    continue

                if state_lower == "são paulo" and city_lower == cidade_bloqueada:
                    elem.clear()
                    continue

                salary = extract_salary(source_salary, description)
                if not salary:
                    elem.clear()
                    continue

                if not company:
                    company = "Confidencial"

                if url in urls_vistas:
                    elem.clear()
                    continue
                urls_vistas.add(url)

                description = limpar_html(description)
                intro = gerar_intro(title, city)
                descricao_final = intro + "\n\n" + description

                job_id = gerar_id(title, company, city, url)
                slug = gerar_slug(title, city)
                data_publicacao = datetime.utcnow().isoformat()

                job_data = {
                    "id": job_id,
                    "title": title,
                    "slug": slug,
                    "description": descricao_final,
                    "company": company,
                    "salary": salary,
                    "city": city,
                    "state": state,
                    "tipo": job_type,
                    "url": url,
                    "data_publicacao": data_publicacao
                }

                jobs.append(job_data)
                elem.clear()

                # Limite final: apenas 1000 vagas no JSON.
                if len(jobs) >= 1000:
                    json_path = os.path.join(json_folder, "part_1.json")
                    with open(json_path, "w", encoding="utf-8") as json_file:
                        json.dump(jobs, json_file, ensure_ascii=False, indent=2)
                    print(f"✅ {json_path} gerado com {len(jobs)} vagas")
                    jobs = []
                    file_count = 2
                    break

        if not jobs and file_count == 1:
            raise SystemExit("ERRO: nenhuma vaga com remuneração válida; os arquivos existentes foram preservados.")

        if jobs and file_count == 1:
            json_path = os.path.join(json_folder, "part_1.json")
            with open(json_path, "w", encoding="utf-8") as json_file:
                json.dump(jobs, json_file, ensure_ascii=False, indent=2)
            print(f"✅ Último arquivo gerado com {len(jobs)} vagas")

    print(f"📦 Total de vagas no JSON: {1000 if file_count == 2 else len(jobs)}")
else:
    print(f"Erro HTTP: {response.status_code}")
