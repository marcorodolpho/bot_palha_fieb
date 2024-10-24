from flask import Flask, render_template, request, redirect, url_for
import firebase_admin
from firebase_admin import credentials, db

# Inicializar o Firebase com o arquivo de chave privada
cred = credentials.Certificate("firebase_config.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': 'https://palhacerta-default-rtdb.firebaseio.com/'  # Coloque sua URL do Firebase aqui
})

from flask import Flask
app = Flask(__name__)

@app.route('/')
def index():
    return "Hello, World!"

# Rota para página do administrador
@app.route('/admin', methods=['GET', 'POST'])
def admin():
    if request.method == 'POST':
        palha = request.form['palha']
        bolinha = request.form['bolinha']
        # Atualizar quantidades no Firebase
        ref = db.reference('produtos')
        ref.set({
            'palha_italiana': palha,
            'bolinha_italiana': bolinha
        })
        return redirect(url_for('admin'))

    # Exibir as quantidades atuais
    ref = db.reference('produtos')
    produtos = ref.get()
    return render_template('admin.html', produtos=produtos)

# Função auxiliar para decrementar a quantidade de produtos em uma transação
def decrementar_produto(ref, quantidade_pedida):
    def transaction(current_value):
        if current_value is None:
            return 0  # Retorna 0 se o valor for None
        current_value = int(current_value)  # Converter o valor atual para inteiro
        if current_value < quantidade_pedida:
            raise ValueError("Quantidade insuficiente disponível.")  # Lança um erro se não houver quantidade suficiente
        return current_value - quantidade_pedida

    return ref.transaction(transaction)

@app.route('/cliente', methods=['GET', 'POST'])
def cliente():
    ref = db.reference('produtos')
    produtos = ref.get()

    if not produtos:
        produtos = {
            'palha_italiana': 0,
            'bolinha_italiana': 0
        }
    else:
        produtos['palha_italiana'] = int(produtos.get('palha_italiana', 0))
        produtos['bolinha_italiana'] = int(produtos.get('bolinha_italiana', 0))

    mensagem_erro = None
    mensagem_sucesso = None

    if request.method == 'POST':
        nome = request.form['nome']
        produto1 = request.form.get('produto1', '')
        quantidade1 = int(request.form.get('quantidade1', 0))
        produto2 = request.form.get('produto2', '')
        quantidade2 = int(request.form.get('quantidade2', 0))
        horario = request.form['horario']
        pagamento = request.form['pagamento']

        try:
            # Verificar a quantidade do primeiro produto antes de tentar atualizar
            if produto1 and quantidade1 > 0:
                produto1_ref = db.reference(f'produtos/{produto1.lower().replace(" ", "_")}')
                produto1_quantidade = int(produto1_ref.get())
                if produto1_quantidade < quantidade1:
                    raise ValueError(f"Desculpa, o {produto1} não está disponível na quantidade solicitada.")

            # Verificar a quantidade do segundo produto antes de tentar atualizar
            if produto2 and quantidade2 > 0:
                produto2_ref = db.reference(f'produtos/{produto2.lower().replace(" ", "_")}')
                produto2_quantidade = int(produto2_ref.get())
                if produto2_quantidade < quantidade2:
                    raise ValueError(f"Desculpa, o {produto2} não está disponível na quantidade solicitada.")

            # Se tudo estiver disponível, fazer a transação de decrementar
            if produto1 and quantidade1 > 0:
                decrementar_produto(produto1_ref, quantidade1)

            if produto2 and quantidade2 > 0:
                decrementar_produto(produto2_ref, quantidade2)

            # Salvar o pedido no Firebase
            db.reference('pedidos').push({
                'nome': nome,
                'produto1': produto1,
                'quantidade1': quantidade1,
                'produto2': produto2,
                'quantidade2': quantidade2,
                'horario': horario,
                'pagamento': pagamento,
                'status': 'Em andamento'
            })

            # Redirecionar sem mensagem de sucesso na URL
            return redirect(url_for('cliente') + "?pedido=sucesso")

        except ValueError as e:
            return render_template('client.html', produtos=produtos, mensagem_erro=str(e))

    # Checar se a URL contém "?pedido=sucesso" para exibir a mensagem de sucesso apenas uma vez
    mensagem_sucesso = "Pedido confirmado, obrigado!" if request.args.get('pedido') == 'sucesso' else None

    return render_template('client.html', produtos=produtos, mensagem_sucesso=mensagem_sucesso)



# Página do administrador para ver pedidos
@app.route('/verpedidos', methods=['GET', 'POST'])
def ver_pedidos():
    pedidos_ref = db.reference('pedidos')
    pedidos = pedidos_ref.order_by_key().get()  # Obter os pedidos

    # Inverter a ordem dos pedidos para que os mais recentes fiquem no topo
    pedidos_ordenados = list(reversed(list(pedidos.items())))

    total = 0
    pedidos_com_valor = []

    for key, pedido in pedidos_ordenados:
        # Cálculo do preço para o primeiro produto
        preco_total = 0
        if 'produto1' in pedido and pedido['produto1'] == 'Palha Italiana':
            preco_total += 7 * int(pedido['quantidade1'])
        elif 'produto1' in pedido and pedido['produto1'] == 'Bolinha Italiana':
            preco_total += 4 * int(pedido['quantidade1'])

        # Cálculo do preço para o segundo produto, se houver
        if 'produto2' in pedido and pedido['produto2'] == 'Palha Italiana':
            preco_total += 7 * int(pedido['quantidade2'])
        elif 'produto2' in pedido and pedido['produto2'] == 'Bolinha Italiana':
            preco_total += 4 * int(pedido['quantidade2'])

        # Aplicar ajuste de 5% se o pagamento for com Cartão
        if pedido['pagamento'] == 'Cartão':
            preco_total *= 1.05

        # Adiciona o preço total ao pedido e adiciona à lista de pedidos
        pedido['preco_total'] = preco_total
        pedido['key'] = key  # Armazena a chave para uso no template
        pedidos_com_valor.append(pedido)
        total += preco_total

    # Atualizar o status se for um POST request
    if request.method == 'POST':
        pedido_id = request.form['pedido_id']
        novo_status = request.form['status']
        db.reference(f'pedidos/{pedido_id}/status').set(novo_status)
        return redirect(url_for('ver_pedidos'))

    return render_template('admin_pedidos.html', pedidos=pedidos_com_valor, total=total)

if __name__ == '__main__':
    app.run(debug=True)
