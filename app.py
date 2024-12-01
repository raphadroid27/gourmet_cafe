from uuid import uuid4
from flask import Flask, request, render_template,flash,redirect, url_for, jsonify, session
from email.mime.text import MIMEText
from models import Usuario, Produto, Avaliacao, Compra, ItensCompra, Feedback, Endereco, session as db_session
from functools import wraps
import hashlib
import re
import random
import threading
import time
from datetime import datetime
from uuid import UUID

app = Flask(__name__)
app.secret_key = 'sua_chave_secreta'

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        senha_hash = hashlib.sha256(senha.encode()).hexdigest()
        usuario = db_session.query(Usuario).filter_by(email=email).first()
        if usuario and usuario.senha == senha_hash:
            session['user_id'] = usuario.email
            session['user_name'] = usuario.nome
            return redirect(url_for('catalogo'))
        else:
            return render_template('index.html', mensagemLoginErro="Credenciais inválidas, tente novamente.")
    return render_template('index.html')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('user_name', None)
    return redirect(url_for('index'))

@app.route('/cadastrar', methods=['POST'])
    
def cadastrar_usuario():
    nome = request.form['nome']
    email = request.form['email']
    senha = request.form['senha']

    # Verificar se o email já está cadastrado
    usuario_existente = db_session.query(Usuario).filter_by(email=email).first()
    if usuario_existente:
        return render_template('index.html', mensagemCadastroErro="E-mail já cadastrado!")

    if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
        return render_template('index.html', mensagemCadastroErro="E-mail inválido.")
    
    if len(senha) < 8 or not re.search(r"[A-Za-z]", senha) or not re.search(r"[0-9]", senha):
        return render_template ('index.html', mensagemCadastroErro="A senha deve conter pelo menos 8 caracteres, incluindo uma letra e um número.")

    senha_hash = hashlib.sha256(senha.encode()).hexdigest()
    codigo_recuperacao = gerar_codigo_recuperacao()
    novo_usuario = Usuario(nome=nome, email=email, senha=senha_hash, codigo_recuperacao=codigo_recuperacao)
    db_session.add(novo_usuario)
    db_session.commit()
    return render_template('index.html', mensagemCadastro=f"Usuário {nome} cadastrado com sucesso.")


@app.route('/recuperar_senha')
def recuperar_senha():
    return render_template('recuperar_senha.html')

def gerar_codigo_recuperacao():
    return ''.join(random.choices('0123456789', k=6))

def atualizar_codigos_recuperacao():
    while True:
        pass

        time.sleep(60)  # Espera por 1 minuto
        usuarios = db_session.query(Usuario).all()
        for usuario in usuarios:
            usuario.codigo_recuperacao = gerar_codigo_recuperacao()
        db_session.commit()

@app.route('/enviar_codigo', methods=['POST'])
def enviar_codigo():
    email = request.form['email']
    usuario = db_session.query(Usuario).filter_by(email=email).first()
    if usuario:
        usuario.codigo_recuperacao = gerar_codigo_recuperacao()
        db_session.commit()
        return render_template('recuperar_senha.html', email=email, mensagem="Código de recuperação enviado para o e-mail.")
    return render_template('recuperar_senha.html', mensagemErro="E-mail não encontrado.")

@app.route('/verificar_codigo', methods=['POST'])
def verificar_codigo():
    email = request.form['email']
    codigo_recuperacao = request.form['codigo_recuperacao']
    usuario = db_session.query(Usuario).filter_by(email=email, codigo_recuperacao=codigo_recuperacao).first()
    if usuario:
        return render_template('nova_senha.html', email=email, codigo_recuperacao=codigo_recuperacao)
    return render_template('recuperar_senha.html', mensagemErro="Código de recuperação inválido.")
    
@app.route('/resetar_senha', methods=['POST'])
def resetar_senha():
    email = request.form['email']
    codigo_recuperacao = request.form['codigo_recuperacao']
    nova_senha = request.form['nova_senha']
    confirmar_senha = request.form['confirmar_senha']
    
    # Validação da senha
    regex = re.compile(r'^(?=.*[A-Za-z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$')
    if not regex.match(nova_senha):
        return render_template('nova_senha.html', email=email, codigo_recuperacao=codigo_recuperacao, mensagem="A senha deve conter pelo menos 8 caracteres, incluindo uma letra, um número e um caractere especial.")
    
    if nova_senha != confirmar_senha:
        return render_template('nova_senha.html', email=email, codigo_recuperacao=codigo_recuperacao, mensagem="As senhas não coincidem. Por favor, tente novamente.")
    
    usuario = db_session.query(Usuario).filter_by(email=email, codigo_recuperacao=codigo_recuperacao).first()
    if usuario:
        usuario.senha = hashlib.sha256(nova_senha.encode()).hexdigest()
        db_session.commit()
        return render_template('nova_senha.html', mensagem="Senha redefinida com sucesso.")
    
    return render_template('nova_senha.html', email=email, codigo_recuperacao=codigo_recuperacao, mensagem="Erro ao redefinir a senha.")

@app.route('/editar_usuario', methods=['GET', 'POST'])
@login_required
def editar_usuario():
    usuario = db_session.query(Usuario).filter_by(email=session['user_id']).first()
    enderecos = db_session.query(Endereco).filter_by(email_usuario=session['user_id']).all()
    if request.method == 'POST':
        usuario.nome = request.form['nome']
        usuario.data_nascimento = datetime.strptime(request.form['data_nascimento'], '%d/%m/%Y').date()
        db_session.commit()
        return redirect(url_for('area_cliente'))
    return render_template('editar_usuario.html', usuario=usuario, enderecos=enderecos)

@app.route('/catalogo')
def catalogo():
    search = request.args.get('search', '')
    query = db_session.query(Produto).filter(Produto.nome.like(f'%{search}%'))
    produtos = query.order_by(Produto.nome).all()
    return render_template('catalogo.html', produtos=produtos)

@app.route('/produto/<produto_id>', methods=['GET', 'POST'])
def ver_produto(produto_id):
    produto = db_session.query(Produto).filter_by(id=produto_id).first()
    avaliacoes = db_session.query(Avaliacao).filter_by(id_produto=produto_id).all()
    return render_template('produto.html', produto=produto, avaliacoes=avaliacoes)

@app.route('/adicionar_ao_carrinho', methods=['POST'])
def adicionar_ao_carrinho():
    produto_id = request.form.get('produto_id')
    if not produto_id:
        flash("Produto não encontrado.", 'danger')
        return redirect(url_for('catalogo'))

    produto = db_session.query(Produto).filter_by(id=produto_id).first()
    if not produto:
        flash(f"Produto {produto_id} não encontrado.", 'danger')
        return redirect(url_for('catalogo'))

    if 'carrinho' not in session:
        session['carrinho'] = []

    # Verifica se o produto já está no carrinho
    for item in session['carrinho']:
        if item['id'] == produto.id:
            item['quantidade'] += 1
            break
    else:
        session['carrinho'].append({
            'id': produto.id,
            'nome': produto.nome,
            'preco': produto.preco,
            'quantidade': 1,
            'imagem': produto.imagem
        })

    session.modified = True
    
    flash(f"Produto {produto.nome} adicionado ao carrinho.", 'success')
    return redirect(url_for('catalogo'))

@app.route('/ver_carrinho')
def ver_carrinho():
    carrinho = session.get('carrinho', [])
    total = sum(item['preco'] * item['quantidade'] for item in carrinho)
    for item in carrinho:
        item['subtotal'] = item['preco'] * item['quantidade']
    return render_template('carrinho.html', produtos=carrinho, total=total)

@app.route('/remover_item', methods=['POST'])
def remover_item():
    produto_id = request.form['produto_id']
    carrinho = session.get('carrinho', [])
    session['carrinho'] = [item for item in carrinho if item['id'] != produto_id]
    return redirect(url_for('ver_carrinho'))

@app.route('/atualizar_quantidade', methods=['POST'])
def atualizar_quantidade():
    produto_id = request.form['produto_id']
    quantidade = int(request.form['quantidade'])
    carrinho = session.get('carrinho', [])
    for item in carrinho:
        if item['id'] == produto_id:
            item['quantidade'] = quantidade
            break
    session['carrinho'] = carrinho
    return redirect(url_for('ver_carrinho'))

@app.route('/limpar_carrinho')
def limpar_carrinho():
    session.pop('carrinho', None)
    return redirect(url_for('ver_carrinho'))

@app.route('/finalizar_compra', methods=['GET', 'POST'])
@login_required
def finalizar_compra():
    if request.method == 'POST':
        endereco = request.form.get('endereco')
        cidade = request.form.get('cidade')
        estado = request.form.get('estado')
        cep = request.form.get('cep')
        forma_pagamento = request.form.get('forma_pagamento')
        numero_cartao = request.form.get('numero_cartao')
        nome_cartao = request.form.get('nome_cartao')
        validade_cartao = request.form.get('validade_cartao')
        cvv_cartao = request.form.get('cvv_cartao')
        carrinho = session.get('carrinho', [])
        total = sum(item['preco'] * item['quantidade'] for item in carrinho)

        if not forma_pagamento:
            flash('Por favor, selecione a forma de pagamento.', 'danger')
            return redirect(url_for('finalizar_compra'))

        # Obter o último código de pedido e gerar o próximo código sequencial
        ultimo_pedido = db_session.query(Compra).order_by(Compra.id.desc()).first()
        if ultimo_pedido:
            codigo_pedido = int(ultimo_pedido.id) + 1
        else:
            codigo_pedido = 1

        # Salvar o endereço de entrega no banco de dados
        novo_endereco = Endereco(
            email_usuario=session['user_id'],
            endereco=endereco,
            cidade=cidade,
            estado=estado,
            cep=cep
        )
        db_session.add(novo_endereco)
        db_session.commit()

        # Salvar a compra no banco de dados
        nova_compra = Compra(
            id=codigo_pedido,
            email_usuario=session['user_id'],
            data_compra=datetime.now().date(),
            quantidade=len(carrinho),
            preco_total=total,
            forma_pagamento=forma_pagamento,
            numero_cartao=numero_cartao,
            nome_cartao=nome_cartao,
            validade_cartao=validade_cartao,
            cvv_cartao=cvv_cartao,
            endereco_entrega=novo_endereco.id
        )
        db_session.add(nova_compra)
        db_session.commit()

        # Salvar os itens comprados na tabela ItensCompra
        for item in carrinho:
            novo_item = ItensCompra(
                id_compra=codigo_pedido,
                id_produto=item['id'],
                quantidade=item['quantidade'],
                preco_unitario=item['preco']
            )
            db_session.add(novo_item)

        db_session.commit()

        # Limpar o carrinho
        session.pop('carrinho', None)

        # Redirecionar para a página de detalhes do pedido
        return redirect(url_for('detalhes_pedido', pedido_id=codigo_pedido))

    carrinho = session.get('carrinho', [])
    total = sum(item['preco'] * item['quantidade'] for item in carrinho)
    return render_template('finalizar_compra.html', produtos=carrinho, total=total)

@app.route('/validar_cupom', methods=['POST'])
def validar_cupom():
    cupom = request.form['cupom']
    desconto = verificar_cupom(cupom)
    if desconto:
        return jsonify({'desconto': desconto})
    return jsonify({'desconto': 0})

def verificar_cupom(cupom):
    cupons_validos = {
        'DESCONTO10': 10,
        'DESCONTO20': 20
    }
    return cupons_validos.get(cupom.upper())

@app.route('/avaliar_produto/<produto_id>', methods=['GET', 'POST'])
@login_required
def avaliar_produto(produto_id):
    produto = db_session.query(Produto).filter_by(id=produto_id).first()
    if not produto:
        flash('Produto não encontrado.', 'danger')
        return redirect(url_for('catalogo'))

    if request.method == 'POST':
        nota = request.form.get('nota')
        comentario = request.form.get('comentario')
        pedido_id = request.form.get('pedido_id')

        try:
            nota = int(nota)
        except (ValueError, TypeError):
            nota = None

        if nota is None:
            flash('Nota inválida. Por favor, insira um número entre 1 e 5.', 'danger')
            return redirect(url_for('avaliar_produto', produto_id=produto_id))

        # Salvar a avaliação no banco de dados
        nova_avaliacao = Avaliacao(
            id_produto=produto_id,
            email_usuario=session['user_id'],
            nota=nota,
            comentario=comentario,
            #data_avaliacao=datetime.now()
        )
        db_session.add(nova_avaliacao)
        db_session.commit()

        flash('Avaliação enviada com sucesso!', 'success')
        return redirect(url_for('area_cliente'))

    return render_template('avaliar_produto.html', produto=produto)

@app.route('/editar_avaliacao/<avaliacao_id>', methods=['GET', 'POST'])
def editar_avaliacao(avaliacao_id):
    avaliacao = db_session.query(Avaliacao).filter_by(id=avaliacao_id).first()
    if request.method == 'POST':
        avaliacao.nota = request.form['nota']
        avaliacao.comentario = request.form['comentario']
        db_session.commit()
        return redirect(url_for('ver_produto', produto_id=avaliacao.id_produto))
    return render_template('editar_avaliacao.html', avaliacao=avaliacao)

@app.route('/excluir_avaliacao/<int:avaliacao_id>', methods=['POST'])
def excluir_avaliacao(avaliacao_id):
    avaliacao = db_session.query(Avaliacao).filter_by(id=avaliacao_id).first()
    if avaliacao:
        db_session.delete(avaliacao)
        db_session.commit()
        flash('Avaliação excluída com sucesso!', 'success')
    else:
        flash('Avaliação não encontrada.', 'danger')
    return redirect(url_for('area_cliente'))

@app.route('/devolucao', methods=['GET', 'POST'])
def devolucao():
    if request.method == 'POST':
        numero_pedido = request.form['numero_pedido']
        motivo = request.form['motivo']
        contato = request.form['contato']
        # Lógica para processar a devolução
        return render_template('devolucao_confirmacao.html', numero_pedido=numero_pedido)
    return render_template('devolucao.html')

@app.route('/status_devolucao', methods=['GET'])
def status_devolucao():
    numero_pedido = request.args.get('numero_pedido')
    # Lógica para obter o status da devolução
    status = "Em processamento"  # Exemplo de status
    return render_template('status_devolucao.html', numero_pedido=numero_pedido, status=status)

@app.route('/area_cliente')
@login_required
def area_cliente():
    usuario = db_session.query(Usuario).filter_by(email=session['user_id']).first()
    pedidos = db_session.query(Compra).filter_by(email_usuario=session['user_id']).order_by(Compra.id.desc()).all()
    avaliacoes = db_session.query(Avaliacao).filter_by(email_usuario=session['user_id']).all()
    current_date = datetime.now().strftime('%d/%m/%Y')
    return render_template('area_cliente.html', usuario=usuario, pedidos=pedidos, avaliacoes=avaliacoes, current_date=current_date)

@app.route('/detalhes_pedido/<int:pedido_id>')
@login_required
def detalhes_pedido(pedido_id):
    pedido = db_session.query(Compra).filter_by(id=pedido_id).first()
    if not pedido:
        return "Pedido não encontrado", 404
    itens = db_session.query(ItensCompra).filter_by(id_compra=pedido_id).all()
    
    # Adicione prints para verificar os dados
    print(f"Pedido: {pedido}")
    print(f"Itens: {itens}")
    
    return render_template('detalhes_pedido.html', pedido=pedido, itens=itens)

@app.route('/feedback', methods=['GET', 'POST'])
def feedback():
    if request.method == 'POST':
        nome = request.form['nome']
        email = request.form['email']
        sugestao = request.form['sugestao']
        
        # Salvar feedback no banco de dados
        novo_feedback = Feedback(nome=nome, email=email, sugestao=sugestao)
        db_session.add(novo_feedback)
        db_session.commit()
        
        return redirect(url_for('feedback'))
    
    return render_template('feedback.html',mensagem="Feedback enviado com sucesso!")

@app.route('/cadastrar_produto', methods=['GET', 'POST'])
def cadastrar_produto():
    if request.method == 'POST':
        nome = request.form['nome']
        descricao = request.form['descricao']
        preco = request.form['preco']
        imagem = request.form['imagem']
        tipo = request.form['tipo']
        ingredientes = request.form['ingredientes']
        
        novo_produto = Produto(
            id=str(uuid4()), 
            nome=nome, 
            descricao=descricao, 
            preco=float(preco), 
            imagem=imagem, 
            tipo=tipo, 
            ingredientes=ingredientes
        )
        db_session.add(novo_produto)
        db_session.commit()
        return render_template('cadastrar_produto.html', mensagem="Produto cadastrado com sucesso!")
    return render_template('cadastrar_produto.html')


@app.route('/gerenciar_sistema', methods=['GET', 'POST'])
def gerenciar_sistema():
    if request.method == 'POST':
        feedback_id = request.form.get('feedback_id')
        if feedback_id:
            feedback = db_session.query(Feedback).filter_by(id=feedback_id).first()
            if feedback:
                feedback.respondido = not feedback.respondido
                db_session.commit()
            else:
                flash('Feedback não encontrado.', 'danger')
        return redirect(url_for('gerenciar_sistema'))

    search_feedback = request.args.get('search_feedback', '')
    search_produto = request.args.get('search_produto', '')
    search_usuario = request.args.get('search_usuario', '')

    feedbacks = db_session.query(Feedback).filter(Feedback.nome.contains(search_feedback) | Feedback.email.contains(search_feedback)).all()
    produtos = db_session.query(Produto).filter(Produto.nome.contains(search_produto) | Produto.descricao.contains(search_produto)).all()
    usuarios = db_session.query(Usuario).filter(Usuario.nome.contains(search_usuario) | Usuario.email.contains(search_usuario)).all()

    return render_template('gerenciar_sistema.html', feedbacks=feedbacks, produtos=produtos, usuarios=usuarios)

@app.route('/editar_produto/<uuid:produto_id>', methods=['GET', 'POST'])
def editar_produto(produto_id):
    produto = db_session.query(Produto).filter_by(id=produto_id).first()
    if request.method == 'POST':
        produto.nome = request.form['nome']
        produto.descricao = request.form['descricao']
        produto.preco = request.form['preco']
        produto.tipo = request.form['tipo']
        db_session.commit()
        return redirect(url_for('gerenciar_sistema'))
    return render_template('editar_produto.html', produto=produto)

@app.route('/excluir_produto/<uuid:produto_id>', methods=['DELETE'])
def excluir_produto(produto_id):
    try:
        produto = db_session.query(Produto).filter_by(id=str(produto_id)).first()
        if produto:
            db_session.delete(produto)
            db_session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False}), 404
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/listar_usuarios', methods=['GET'])
def listar_usuarios():
    search = request.args.get('search', '')
    usuarios = db_session.query(Usuario).filter(Usuario.nome.contains(search) | Usuario.email.contains(search)).all()
    return render_template('gerenciar_sistema.html', usuarios=usuarios)

@app.route('/excluir_usuario', methods=['DELETE'])
def excluir_usuario():
    data = request.get_json()
    email = data.get('email')
    usuario = db_session.query(Usuario).filter_by(email=email).first()
    if usuario:
        db_session.delete(usuario)
        db_session.commit()
        flash('Usuário excluído com sucesso!', 'success')
        return jsonify({'success': True})
    return jsonify({'success': False}), 404

@app.route('/excluir_endereco/<int:endereco_id>', methods=['POST'])
@login_required
def excluir_endereco(endereco_id):
    endereco = db_session.query(Endereco).filter_by(id=endereco_id).first()
    if endereco:
        # Verificar se o endereço está sendo usado em alguma compra
        compras_usando_endereco = db_session.query(Compra).filter_by(endereco_entrega=endereco_id).all()
        if compras_usando_endereco:
            flash('Não é possível excluir o endereço, pois ele está sendo usado em uma ou mais compras.', 'danger')
        else:
            db_session.delete(endereco)
            db_session.commit()
            flash('Endereço excluído com sucesso.', 'success')
    else:
        flash('Endereço não encontrado.', 'danger')
    return redirect(url_for('editar_usuario'))

if __name__ == '__main__':
    threading.Thread(target=atualizar_codigos_recuperacao).start()
    app.run(debug=True)