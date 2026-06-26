# register, login, bad password, duplicate user
test_register
#  valid registration returns 201 + user data
#  passwords don't match returns 422
#  login shorter than 8 chars returns 422
#  password shorter than 8 chars returns 422
# duplicate login returns 409
#  missing fields returns 422

# test_login
#  valid credentials returns 200 + access_token + token_type="bearer"
#  wrong password returns 401
#  non-existent login returns 401
#  missing password returns 422
#  missing login returns 422

# test_token_expiry
#  valid token is accepted on protected route
#  expired token returns 401
#  malformed token returns 401
#  missing token returns 401
#  tampered token (wrong signature) returns 401
