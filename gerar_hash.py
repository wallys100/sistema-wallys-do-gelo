import bcrypt 

senha = "123456"
hash_senha = bcrypt.hashpw(senha.encode(), bcrypt.gensalt())

print(hash_senha.decode())