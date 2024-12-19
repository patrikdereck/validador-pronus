from flask import Flask, jsonify, render_template, Response
import threading
import time
import pymysql
import json
import requests  # Para fazer a solicitação HTTP à API de validação

app = Flask(__name__)

# Configurações do banco de dados
DB_HOST = 'DBHOST'
DB_USER = 'DBUSER'
DB_PASSWORD = 'DBSENHA'
DB_NAME = 'DBNAME'

# Variáveis globais para progresso
progress = 0
total_numbers = 0
lock = threading.Lock()

# URL da API de validação de números
VALIDATION_API_URL = 'https://evo.pronustech.com/chat/whatsappNumbers/INSTANCIA'
API_KEY = 'APIKEY'

def connect_db():
    """Conecta ao banco de dados."""
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

def update_notify_status(phone, status):
    """Atualiza a coluna 'notify' no banco de dados."""
    try:
        connection = connect_db()
        with connection.cursor() as cursor:
            query = "UPDATE clientes SET notify = %s WHERE telefone_cliente = %s"
            cursor.execute(query, (status, phone))
            connection.commit()
    finally:
        connection.close()

def validate_phone_number(phone):
    """Valida o número de telefone através da API externa."""
    headers = {
        'apikey': API_KEY
    }
    data = {
        'numbers': [phone]
    }
    try:
        response = requests.post(VALIDATION_API_URL, headers=headers, json=data)
        response_data = response.json()

        # Verifica se a chave 'exists' está presente e se é 'true' ou 'false'
        if response_data and response_data[0].get('exists') == False:
            return "INVALIDO"
        else:
            return "VALIDO"
    except Exception as e:
        print(f"Erro ao validar o número {phone}: {e}")
        return "INVALIDO"  # Em caso de erro, consideramos o número como inválido

def process_numbers():
    """Função para processar números do banco de dados."""
    global progress, total_numbers

    # Conecta ao banco e busca os números cujo 'notify' é NULL
    connection = connect_db()
    try:
        with connection.cursor() as cursor:
            # Modificado para buscar apenas números com 'notify' NULL
            cursor.execute("SELECT telefone_cliente FROM clientes WHERE notify IS NULL")
            numbers = cursor.fetchall()
            total_numbers = len(numbers)

            for idx, row in enumerate(numbers):
                phone = row[0]
                # Chama a função para validar o número
                status = validate_phone_number(phone)

                # Atualiza o status no banco de dados
                update_notify_status(phone, status)

                # Exibe no console o número e seu status
                print(f"Número: {phone} - Status: {status}")

                # Envia a atualização do número processado para o frontend
                data = {"phone": phone, "status": status}
                with lock:
                    progress = int(((idx + 1) / total_numbers) * 100)
                yield f"data:{json.dumps(data)}\n\n"  # Envia a atualização via Server-Sent Events (SSE)
    finally:
        connection.close()

@app.route('/')
def index():
    """Rota principal para renderizar a interface."""
    return render_template('index.html')

@app.route('/start', methods=['GET'])
def start_analysis():
    """Inicia a análise dos números."""
    global progress, total_numbers
    progress = 0
    total_numbers = 0
    threading.Thread(target=process_numbers).start()
    return jsonify({"message": "Análise iniciada!"}), 200

@app.route('/progress', methods=['GET'])
def get_progress():
    """Retorna o progresso atual."""
    global progress
    with lock:
        return jsonify({"progress": progress}), 200

@app.route('/numbers')
def numbers():
    """Rota para enviar atualizações dos números sendo analisados."""
    return Response(process_numbers(), content_type='text/event-stream')

if __name__ == '__main__':
    app.run(debug=True)
