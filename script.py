import requests
import gzip
import xml.etree.ElementTree as ET
import io
import json
import os
import hashlib
import random
import re
from datetime import datetime

feed_url = "https://feeds.whatjobs.com/sinerj/sinerj_pt_BR.xml.gz"

json_folder = "json_parts"
os.makedirs(json_folder, exist_ok=True)

file_count = 1
jobs = []

# Estados permitidos
estados_permitidos = [
    "são paulo",
    "paraná",
    "santa catarina",
    "rio grande do sul"
]

# Cidade bloqueada (somente SP)
cidade_bloqueada = "campinas"

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
                url = elem.findtext("urlDeeplink", "").strip()

                location_elem = elem.find("locations/location")
                city = location_elem.findtext("city", "").strip() if location_elem is not None else ""
                state = location_elem.findtext("state", "").strip() if location_elem is not None else ""

                if not city or not state or not title or not url:
                    elem.clear()
                    continue

                city_lower = normalizar(city)
                state_lower = normalizar(state)

                # 🔥 FILTRO PRINCIPAL
                if state_lower not in estados_permitidos:
                    elem.clear()
                    continue

                # 🔥 BLOQUEAR CAMPINAS SOMENTE EM SP
                if state_lower == "são paulo" and city_lower == cidade_bloqueada:
                    elem.clear()
                    continue

                if not company:
                    company = "Confidencial"

                # ❌ evitar duplicados
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
                    "city": city,
                    "state": state,
                    "tipo": job_type,
                    "url": url,
                    "data_publicacao": data_publicacao
                }

                jobs.append(job_data)
                elem.clear()

                if len(jobs) >= 1000:
                    if file_count > 5:
                        print("⛔ Limite de arquivos atingido")
                        break

                    json_path = os.path.join(json_folder, f"part_{file_count}.json")

                    with open(json_path, "w", encoding="utf-8") as json_file:
                        json.dump(jobs, json_file, ensure_ascii=False, indent=2)

                    print(f"✅ {json_path} gerado")

                    jobs = []
                    file_count += 1

        if jobs:
            json_path = os.path.join(json_folder, f"part_{file_count}.json")

            with open(json_path, "w", encoding="utf-8") as json_file:
                json.dump(jobs, json_file, ensure_ascii=False, indent=2)

            print(f"✅ Último arquivo gerado")

    print(f"📦 Total de arquivos: {file_count}")

else:
    print(f"Erro HTTP: {response.status_code}")
