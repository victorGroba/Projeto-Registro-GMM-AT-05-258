from flask import Flask, render_template, request, redirect, url_for
import sqlite3
import qrcode
import os
from datetime import datetime

app = Flask(__name__)

def coluna_existe(nome_tabela, nome_coluna):
    with sqlite3.connect("equipamentos.db") as conn:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({nome_tabela})")
        colunas = [linha[1] for linha in cursor.fetchall()]
    return nome_coluna in colunas

# Criar banco de dados e tabelas
def init_db():
    with sqlite3.connect("equipamentos.db") as conn:
        cursor = conn.cursor()

        # Criar tabelas se não existirem
        cursor.execute('''CREATE TABLE IF NOT EXISTS equipamentos (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            patrimonio TEXT UNIQUE,
                            nome TEXT,
                            modelo TEXT,
                            marca TEXT,
                            fabricante TEXT,
                            numero_serie TEXT
                        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS historico (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            equipamento_id INTEGER,
                            data TEXT,
                            tipo_servico TEXT,
                            responsavel_execucao TEXT,
                            responsavel_analise TEXT,
                            proxima_manutencao TEXT,
                            local_uso TEXT,
                            historico_detalhado TEXT,  
                            observacoes TEXT,  
                            FOREIGN KEY(equipamento_id) REFERENCES equipamentos(id)
                        )''')

        # Adicionar colunas novas apenas se ainda não existirem
        if not coluna_existe("equipamentos", "historico_detalhado"):
            cursor.execute("ALTER TABLE equipamentos ADD COLUMN historico_detalhado TEXT")
        if not coluna_existe("equipamentos", "observacoes"):
            cursor.execute("ALTER TABLE equipamentos ADD COLUMN observacoes TEXT")
        if not coluna_existe("historico", "historico_detalhado"):
            cursor.execute("ALTER TABLE historico ADD COLUMN historico_detalhado TEXT")
        if not coluna_existe("historico", "observacoes"):
            cursor.execute("ALTER TABLE historico ADD COLUMN observacoes TEXT")

        conn.commit()

# Função para converter dd/mm/aaaa para yyyy-mm-dd
def converter_data(data_str):
    try:
        return datetime.strptime(data_str, "%d/%m/%Y").strftime("%Y-%m-%d")
    except ValueError:
        return None

# Rota para cadastrar um equipamento
@app.route("/cadastrar_equipamento", methods=["GET", "POST"])
def cadastrar_equipamento():
    if request.method == "POST":
        patrimonio = request.form["patrimonio"]
        nome = request.form["nome"]
        modelo = request.form["modelo"]
        marca = request.form["marca"]
        fabricante = request.form["fabricante"]
        numero_serie = request.form["numero_serie"]

        with sqlite3.connect("equipamentos.db") as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO equipamentos (patrimonio, nome, modelo, marca, fabricante, numero_serie) VALUES (?, ?, ?, ?, ?, ?)",
                           (patrimonio, nome, modelo, marca, fabricante, numero_serie))
            conn.commit()

        return redirect(url_for("listar_equipamentos"))

    return render_template("cadastrar_equipamento.html")

# Rota para listar equipamentos
@app.route("/equipamentos")
def listar_equipamentos():
    termo_busca = request.args.get("busca", "").lower()

    with sqlite3.connect("equipamentos.db") as conn:
        cursor = conn.cursor()
        if termo_busca:
            query = """
                SELECT * FROM equipamentos
                WHERE LOWER(patrimonio) LIKE ? OR LOWER(nome) LIKE ? OR LOWER(modelo) LIKE ?
            """
            like_term = f"%{termo_busca}%"
            cursor.execute(query, (like_term, like_term, like_term))
        else:
            cursor.execute("SELECT * FROM equipamentos")
        equipamentos = cursor.fetchall()

    return render_template("listar_equipamentos.html", equipamentos=equipamentos, busca=termo_busca)

# Rota para adicionar um novo registro ao histórico de um equipamento
@app.route("/adicionar_historico/<int:equip_id>", methods=["GET", "POST"])
def adicionar_historico(equip_id):
    with sqlite3.connect("equipamentos.db") as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT patrimonio FROM equipamentos WHERE id = ?", (equip_id,))
        equipamento = cursor.fetchone()

    if not equipamento:
        return "Equipamento não encontrado", 404

    patrimonio = equipamento[0]

    if request.method == "POST":
        data = converter_data(request.form["data"])
        proxima_manutencao = converter_data(request.form["proxima_manutencao"])

        if not data or not proxima_manutencao:
            return "Formato de data inválido. Use DD/MM/AAAA.", 400

        tipo_servico = request.form["tipo_servico"]
        responsavel_execucao = request.form["responsavel_execucao"]
        responsavel_analise = request.form["responsavel_analise"]
        local_uso = request.form["local_uso"]
        historico_detalhado = request.form.get("historico_detalhado", "")
        observacoes = request.form.get("observacoes", "")

        with sqlite3.connect("equipamentos.db") as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO historico (
                    equipamento_id, data, tipo_servico, responsavel_execucao, 
                    responsavel_analise, proxima_manutencao, local_uso, 
                    historico_detalhado, observacoes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                equip_id, data, tipo_servico, responsavel_execucao,
                responsavel_analise, proxima_manutencao, local_uso,
                historico_detalhado, observacoes
            ))
            conn.commit()

        return redirect(url_for("historico_equipamento", equip_id=equip_id))

    return render_template("adicionar_historico.html", equip_id=equip_id, patrimonio=patrimonio)

# Rota para exibir histórico de um equipamento
@app.route("/historico/<int:equip_id>")
def historico_equipamento(equip_id):
    with sqlite3.connect("equipamentos.db") as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM equipamentos WHERE id = ?", (equip_id,))
        equipamento = cursor.fetchone()

        cursor.execute("SELECT * FROM historico WHERE equipamento_id = ?", (equip_id,))
        historico = cursor.fetchall()

    if not equipamento:
        return "Equipamento não encontrado", 404

    return render_template("historico_equipamento.html", equipamento=equipamento, historico=historico)

# Gerar QR Code para acessar o histórico do equipamento
@app.route("/gerar_qr/<int:equip_id>")
def gerar_qr(equip_id):
    ip_local = "192.168.1.151"  # Substitua pelo IP real da rede
    url = f"http://{ip_local}:5000/historico/{equip_id}"

    qr = qrcode.make(url)
    qr_folder = "static/qr_codes"

    if not os.path.exists(qr_folder):
        os.makedirs(qr_folder)

    qr_filename = f"qr_{equip_id}.png"
    qr_path = os.path.join(qr_folder, qr_filename)
    qr.save(qr_path)

    return render_template("qr_code.html", qr_filename=qr_filename)

# Inicialização
if __name__ == "__main__":
    if not os.path.exists("static"):
        os.makedirs("static")
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)
