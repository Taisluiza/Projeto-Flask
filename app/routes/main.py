from flask import Blueprint, jsonify, request
from app.models.user import LoginPayload
from pydantic import ValidationError
from app import db
from bson import ObjectId
from app.models.products import *
from app.models.sale import Sale
from app.decorators import token_required
from datetime import datetime, timedelta, timezone
import jwt
import csv
import os
import io



main_bp = Blueprint('main_bp', __name__)
@main_bp.route('/')
def index():
    return jsonify({"message":"Bem vindo ao Stylesync!"})

#Criando um CRUD

#  O sistema deve permitir que um usuário se autentique para obter um token
@main_bp.route('/login', methods=['POST'])
def login():

    try:
       raw_data = request.get_json()
       user_data = LoginPayload(**raw_data)
    except ValidationError as e:
     return jsonify({"error": e.errors()}), 400
    except Exception as e:
     return jsonify({"error": "Erro durante a requisição do dado"}), 500

    if user_data.username == 'admin' and user_data.password == "supersecret":
       token = jwt.encode(
          {
            "user_id": user_data.username,
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30)
           },
           current_app.config['SECRET_KEY'], algorithm="HS256")
       return jsonify({'access_token': token}),200
    return jsonify({"message": "Credenciais invalidas!"}),401

    return jsonify({"message": f"Realizar o login do usuario {user_data.model_dump_json()}"})

#  O sistema deve permitir listagem de todos os produtos
@main_bp.route('/products')
def get_products():
    
    products_cursor = db.products.find({})
    products_list = [ProductDBModel(**product).model_dump(by_alias=True, exclude_none=True) for product in products_cursor]
    for product in products_cursor:
     product['_id'] = str(product['_id'])
     products_list.append(product)

    return jsonify(products_list)

# O sistema deve permitir a criacao de um novo produto
@token_required
@main_bp.route('/products', methods=['POST'])
def create_product(token):
    try:
       product = Product(**request.get_json())
    except ValidationError as e:
       return jsonify({"error": e.errors()})

    result = db.products.insert_one(product.model_dump())

    return jsonify({"id": str(result.inserted_id), "message":"Produto criado com sucesso"}), 201


# O sistema deve permitir a visualizacao dos detalhes de um unico produto
@main_bp.route('/product/<string:product_id>', methods=['GET'])
def get_product_by_id(product_id):
    try:
       oid = ObjectId(product_id)
    except Exception as e:
     return jsonify({"error": f"Erro ao transformar o produto {product_id} em ObjectID: {e}"})

    product = db.products.find_one({'_id': oid})

    if product:
       products_model = [ProductDBModel(**product).model_dump(by_alias=True, exclude_none=True)]
       return jsonify(products_model)
    else:
        return jsonify({"error": f"Produto com o id: {product_id} - Não encontrado"})
    
    return jsonify({"message":f"Esta é a rota de visualizacao do detalhe do id do produto {product_id}"})

# O sistema deve permitir a atualizacao de um unico produto e produto existente
@main_bp.route('/product/<string:product_id>', methods=['PUT'])
@token_required
def update_product(token, product_id):
    try: 
       oid= ObjectId(product_id)
       update_data = UpdateProduct(**request.get_json())

    except ValidationError as e:
       return jsonify({"error": e.errors()})

    update_result = db.products.update_one(
       {"_id": oid},
       {"$set": update_data.model_dump(exclude_unset=True)}
    )

    if update_result.matched_count == 0:
       return jsonify({"error": "Produto não encontrado"}),404

    updated_product = db.products.find_one({"_id":oid})
    return jsonify(ProductDBModel(**updated_product).model_dump(by_alias=True, exclude=None))

# O sistema deve permitir a delecao de um unico produto e produto existente
@main_bp.route('/product/<string:product_id>', methods=['DELETE'])
@token_required
def delete_product(token, product_id):
    try:
        oid = ObjectId(product_id)
    except Exception:
       return jsonify({"error":"id do produto invalido"}),400

    delete_product = db.products.delete_one({"_id": oid})

    if delete_product.deleted_count == 0:
       return jsonify({"error":"Produto não foi encontrado"}),400
    return "", 204

# O sistema deve permitir a importacao de vendas através de um arquivo
@main_bp.route('/sales/upload', methods=['POST'])
@token_required
def upload_sales(token):
    if 'file' not in request.files:
       return jsonify({"error":"Nenhum arquivo foi enviado."}),200

    file = request.files['file']

    if file.filename =='':
       return jsonify({"error":"Nenhum arquivo selecionado."}),400

    if file and file.filename.endswith('.csv'):
       csv_syeam = io.StringIO(file.stream.read().decode(' UTF-8'), newline=None)
       csv_reader = csv.DictReader(csv_syeam)

       sales_to_insert = []
       error = []

       for row_num, row in enumerate(csv_syeam, 1):
          try:
             sale_data = Sale(**row)
             sales_to_insert.append(sale_data.model_dump())

          except ValidationError as e:
             error.append(f'Linha {row_num} com dados inválidos.')
          except Exception:
             error.append(f'Linha {row_num} com erro insperado nos dados.')

       if sales_to_insert:
         try:
          db.sale.insert_many(sales_to_insert)
         except Exception as e:
            return jsonify ({'error': f'{e}'})
       return jsonify({
               "message": "Upload realizado com sucesso.",
               "vendas importadas": len(sales_to_insert),
               "error encontrados": error
        }),200
                 
    return jsonify({"message":"Esta é a rota de upload do arquivo de vendas"})




