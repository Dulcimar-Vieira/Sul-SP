import os
import json
from datetime import datetime

pasta = "json_parts"
arquivo_saida = "merged.json"

if not os.path.exists(pasta):
    print(f"❌ Pasta '{pasta}' não encontrada.")
    raise SystemExit(1)

arquivos = sorted(
    [
        f for f in os.listdir(pasta)
        if f.startswith("part_") and f.endswith(".json")
    ],
    key=lambda x: int(x.split("_")[1].split(".")[0])
)

print(f"🔍 {len(arquivos)} arquivos encontrados em '{pasta}'.")

dados_totais = []
erros = 0

for arquivo in arquivos:
    caminho = os.path.join(pasta, arquivo)
    try:
        with open(caminho, "r", encoding="utf-8") as f:
            dados = json.load(f)

        if isinstance(dados, list):
            dados_totais.extend(dados)
            print(f"✅ {arquivo}: {len(dados)} registros.")
        else:
            print(f"⚠️ {arquivo} não contém uma lista.")
    except Exception as e:
        erros += 1
        print(f"❌ Erro em {arquivo}: {e}")

if erros > 0:
    print("❌ Há erros nos arquivos JSON. O merged.json não será alterado.")
    raise SystemExit(1)

if not dados_totais:
    print("❌ Nenhuma vaga foi encontrada. O merged.json existente será preservado.")
    raise SystemExit(1)

# Segurança: mesmo que apareça mais de um part_*.json,
# o resultado final nunca passa de 100 vagas.
dados_totais = dados_totais[:100]

resultado = {
    "gerado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "total_vagas": len(dados_totais),
    "vagas": dados_totais
}

with open(arquivo_saida, "w", encoding="utf-8") as f:
    json.dump(resultado, f, ensure_ascii=False, indent=2)

tamanho_mb = os.path.getsize(arquivo_saida) / (1024 * 1024)
print(f"✅ '{arquivo_saida}' atualizado com {len(dados_totais)} vagas.")
print(f"📄 Tamanho: {tamanho_mb:.2f} MB")
