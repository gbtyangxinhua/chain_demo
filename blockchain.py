# -*- coding: UTF-8 -*-
# {
#     "index":0,
#     "timestamp":"",
#     "transactions":[
#         {
#             "sender":"",
#             "recipient":"",
#             "amount":5,
#         }
#     ],
#     "proof":"",
#     "previous_hash":""
# }

import hashlib
import json
from time import time
from urllib.parse import urlparse
from uuid import uuid4
from argparse import ArgumentParser

import requests
from flask import Flask, jsonify, request


class BlockChain:
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.nodes = set()

        self.new_block(proof=100, previous_hash=1)

    '''注册节点'''

    def register_node(self, address: str):
        # http://127.0.0.1:5001
        parsed_url = urlparse(address)
        self.nodes.add(parsed_url.netloc)

    '''验证邻居节点区块链是否完整'''

    def valid_chain(self, chain) -> bool:
        last_block = chain[0]
        current_index = 1
        while current_index < len(chain):
            block = chain[current_index]

            # 验证当前块存储的hash值是否与上一个块计算出来的hash值相同
            if block['previous_hash'] != self.hash(last_block):
                return False

            # 验证工作量证明是否正确
            if not self.valid_proof(last_block["proof"], block['proof']):
                return False

            last_block = block
            current_index += 1

        return True

    '''解决区块冲突'''

    def resolve_conflicts(self) -> bool:
        neighbours = self.nodes

        max_length = len(self.chain)

        new_chain = None

        '''请求邻居节点链条的信息'''
        for node in neighbours:
            response = requests.get(f'http://{node}/chain')
            if response.status_code == 200:
                length = response.json()["length"]
                chain = response.json()["chain"]

            if length > max_length and self.valid_chain(chain):
                max_length = length
                new_chain = chain

        if new_chain:
            self.chain = new_chain
            return True

        return False

    '''创建区块'''

    def new_block(self, proof, previous_hash=None):
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.last_block)

        }

        self.current_transactions = []
        self.chain.append(block)

        return block

    '''创建交易信息'''

    def new_transactions(self, sender, recipient, amount) -> int:
        self.current_transactions.append(
            {
                'sender': sender,
                'recipient': recipient,
                'amount': amount
            }
        )

        return self.last_block['index'] + 1

    '''计算hash值方法'''

    @staticmethod
    def hash(block):
        block_string = json.dumps(block, sort_keys=True).encode()

        return hashlib.sha256(block_string).hexdigest();

    '''获取最有一个区块'''

    @property
    def last_block(self):
        return self.chain[-1]

    '''计算工作证明'''

    def proof_of_work(self, last_proof: int) -> int:
        proof = 0
        while self.valid_proof(last_proof, proof) is False:
            proof += 1

        print(proof)
        return proof

    def valid_proof(self, last_proof, proof) -> bool:
        guess = f'{last_proof}{proof}'.encode()
        guess_hash = hashlib.sha256(guess).hexdigest()

        print(guess_hash)
        return guess_hash[0:4] == "0000"


app = Flask(__name__)

blockChain = BlockChain();

node_identifier = str(uuid4()).replace('-', '')

'''创建交易请求'''


@app.route('/transactions/new', methods=["POST"])
def new_transactions():
    values = request.get_json()
    required = ["sender", "recipient", "amount"]

    if values is None:
        return "Missing values", 400

    if not all(k in values for k in required):
        return "Missing values", 400

    index = blockChain.new_transactions(values['sender'], values["recipient"], values["amount"])

    response = {"message": f'Transcation will be added to Block {index}'}

    return jsonify(response), 201


'''挖矿的路由'''


@app.route('/mine', methods=["GET"])
def mine():
    last_block = blockChain.last_block
    last_proof = last_block['proof']
    proof = blockChain.proof_of_work(last_proof)

    blockChain.new_transactions(sender="0", recipient=node_identifier, amount=1)

    block = blockChain.new_block(proof, None)

    response = {
        "message": "New Block Forged",
        "index": block["index"],
        "transactions": block["transactions"],
        "proof": block["proof"],
        "previous_hash": block["previous_hash"]
    }

    return jsonify(response), 200


'''返回区块链信息'''


@app.route('/chain', methods=["GET"])
def full_chain():
    response = {
        'chain': blockChain.chain,
        'length': len(blockChain.chain)
    }

    return jsonify(response), 200


'''{"nodes":["http://127.0.0.1:5000"]}'''

'''注册节点'''


@app.route("/nodes/register", methods=["POST"])
def register_node():
    values = request.get_json()
    nodes = values.get("nodes")

    if nodes is None:
        return "Error: please supply a valid list of nodes", 400

    for node in nodes:
        blockChain.register_node(node)

    response = {
        "message": "New nodes have benn added",
        "total_nodes": list(blockChain.nodes)
    }

    return jsonify(response), 201


'''检查当前节点区块是否是最完整的区块。。如果不是就替换掉'''


@app.route("/nodes/resolve", methods=["GET"])
def consensus():
    replaced = blockChain.resolve_conflicts()

    if replaced:
        response = {
            "message": "Our chain was replaced",
            "new_chain": blockChain.chain
        }
    else:
        response = {
            "message": "Our chain is authoritative",
            "new_chain": blockChain.chain
        }

    return jsonify(response), 200


if __name__ == '__main__':
    parser = ArgumentParser()

    parser.add_argument('-p', '--port', default=5001, type=int, help='port to listen to')
    args = parser.parse_args()

    port = args.port

    app.run(host='0.0.0.0', port=port)
