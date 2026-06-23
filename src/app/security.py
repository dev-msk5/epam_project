# JWT creation & verification
from pwdlib import PasswordHash
import jwt
from jwt.exceptions import InvalidTokenError
# token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
# payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])

# password_hash = PasswordHash.recommended()
# password_hash.hash(password)
# password_hash.verify(plain, hashed)
