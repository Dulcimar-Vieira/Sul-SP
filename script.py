#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import gzip
import hashlib
import io
import json
import os
import random
import re
from datetime import datetime

import xml.etree.ElementTree as ET
import requests

FEED_URL = "https://feeds.whatjobs.com/sinerj/sinerj_pt_BR.xml.gz"
OUTPUT_FOLDER = "json_parts"
MAX_JOBS = 100

ESTADOS = {"são paulo", "paraná", "santa catarina", "rio grande do sul"}

def norm(s):
    return (s or "").strip().lower()

def matches(city, state, title, desc):
    return norm(state) in ESTADOS and not (
        norm(state) == "são paulo" and norm(city) == "campinas"
    )

def clean(s):
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", s).strip()

def parse_date(s):
    if not s:
        return None
    s = s.strip()
    for fmt in (
        "%d.%m.%Y",
        "%d/%m/%Y",
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
    ):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            pass

    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None

def key(job):
    return job["url"] or hashlib.md5(
        f'{job["title"]}|{job["company"]}|{job["city"]}'.encode("utf-8")
    ).hexdigest()

def intro(title, city):
    return random.choice([
        f"Confira a vaga para {title} em {city}. Veja os detalhes e como se candidatar.",
        f"Nova oportunidade para {title} em {city}. Saiba mais sobre essa vaga.",
        f"Empresa está contratando {title} em {city}. Confira requisitos e envie seu currículo.",
    ])

def main():
    print("📥 Baixando feed completo do WhatJobs...")

    response = requests.get(
        FEED_URL,
        headers={"User-Agent": "Mozilla/5.0 (compatible; FeedProcessor/1.0)"},
        timeout=60,
    )
    response.raise_for_status()

    candidates = {}

    with gzip.open(io.BytesIO(response.content), "rt", encoding="utf-8") as f:
        for _, elem in ET.iterparse(f, events=("end",)):
            if elem.tag != "job":
                continue

            title = elem.findtext("title", "").strip()
            desc = elem.findtext("description", "").strip()
            company = elem.findtext("company/name", "").strip() or "Confidencial"
            url = (
                elem.findtext("urlDeeplink", "").strip()
                or elem.findtext("link", "").strip()
            )
            job_type = elem.findtext("jobType", "").strip()

            location = elem.find("locations/location")
            city = (
                location.findtext("city", "").strip()
                if location is not None
                else ""
            )
            state = (
                location.findtext("state", "").strip()
                if location is not None
                else ""
            )

            pub = elem.findtext("pubdate", "").strip()
            dt = parse_date(pub)

            if not title or not url or not city or not state or not dt:
                elem.clear()
                continue

            if not matches(city, state, title, desc):
                elem.clear()
                continue

            job = {
                "id": hashlib.md5(
                    f"{title}-{company}-{city}-{url}".encode("utf-8")
                ).hexdigest(),
                "title": title,
                "description": intro(title, city) + "\n\n" + clean(desc),
                "company": company,
                "city": city,
                "state": state,
                "tipo": job_type,
                "url": url,
                "data_publicacao": dt.strftime("%Y-%m-%d"),
                "origem": "WhatJobs",
            }

            candidates[key(job)] = job
            elem.clear()

    # Mantém o comportamento antigo de buscar o feed completo,
    # mas limita o JSON final a apenas 100 vagas.
    jobs = list(candidates.values())[:MAX_JOBS]

    os.makedirs(OUTPUT_FOLDER, exist_ok=True)

    for filename in os.listdir(OUTPUT_FOLDER):
        if filename.endswith(".json"):
            os.remove(os.path.join(OUTPUT_FOLDER, filename))

    output_path = os.path.join(OUTPUT_FOLDER, "part_1.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)

    print(f"🔎 Vagas encontradas no feed após filtros: {len(candidates)}")
    print(f"📦 Vagas enviadas ao JSON: {len(jobs)}")
    print(f"📄 Arquivo: {output_path}")

if __name__ == "__main__":
    main()
