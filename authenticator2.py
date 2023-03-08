import socket
import time
import os
import ssl
import jwt

from hashlib import sha256
from Cryptodome.Util import number
from Cryptodome.Random import get_random_bytes, random
from server import server_address as server_address
from server import decryptVotes_address as decryptVotes_address

## Pip install pycryptodomex
## pip install pyJWT

currentPath = os.getcwd()

## Define params for JWT & generate token with payload and secret key
params = {'username':'authenticator2'}
token = jwt.encode(params, 'sEcUrEkEy', algorithm='HS256')
token = str.encode(token)

def generate_r(q):
    r = number.getRandomRange(1, q - 1)
    return r

def retrievePublicKeys(receivePubKeyInfo):
    count = 0
    receivePubKeyInfo.connect(server_address)
    pubKeyInfo = ""
    p = ""
    q = ""
    g = ""
    verified = False
    ## Sending token to Server to verify itself
    while not verified:
        receivePubKeyInfo.send(token)
        while True:
            msgCode = receivePubKeyInfo.recv(1024).decode("utf-8")
            if msgCode == "Valid user!":
                verified = True
                break
            else:
                raise Exception()

    while not pubKeyInfo or not p or not q or not g:
        receivePubKeyInfo.sendall(b'Retrieve public key parameters')
        pubKeyInfo = receivePubKeyInfo.recv(8192*10).decode("utf-8")
        print("Recevived Public Key Parameters!")
        p = int(pubKeyInfo.split("||")[0])
        q = int(pubKeyInfo.split("||")[1])
        g = int(pubKeyInfo.split("||")[2])
        count += 1
        if count == 10:
            raise Exception()
    if p and q and g:
        receivePubKeyInfo.sendall(b"Received Params!")

    while True:
        if receivePubKeyInfo.recv(1024).decode("utf-8") == "Partial Private Key Generated Complete!":
            time.sleep(10)
            break

    ## Generate part of public key here (g^x mod p)
    partialx = number.getRandomRange(1,int(q))
    print("Private Key Generated!")
    partialPublicKey = pow(g, partialx, p)
    print("Partial Public Key Generated!")

    ## Commitment
    r = generate_r(q)
    secret = (pow(g,partialPublicKey,p) * pow(partialPublicKey, r, p)) % p
    print("Commitment for Partial Public Key Generated!")
    return partialx,secret,partialPublicKey,r, p, q, g

def sendCommitment(commitmentValue,server):
    global token
    count = 0
    server.connect(server_address)
    verified = False

    print("Sending Commitment to Server!")
    ## Sending token to Server to verify itself
    ## Submit commitmentValue first if verified
    while not verified:
        server.sendall(token)
        while True:
            msgCode = server.recv(1024).decode("utf-8")
            if msgCode == "Connection is secure":
                server.sendall(commitmentValue)
            if msgCode == "Commitment Received":
                server.close()
                verified = True
                break
            count += 1
            if count == 10:
                raise Exception()


def sendEncryptedPartialPublicKey(partialPublicKeyInfo,server):
    global token
    count = 0
    server.connect(server_address)
    verified = False

    print("Sending Encrypted Partial Public Key to Server!")
     ## Sending token to Server to verify itself
    ## Submit partial Public Key if verified
    while not verified:
        server.send(token)
        while True:
            msgCode = server.recv(1024).decode("utf-8")
            if msgCode == "Connection is secure":
                server.sendall(partialPublicKeyInfo)
            if msgCode == "Valid":
                server.close()
                verified = True
                break
            count += 1
            if count == 10:
                raise Exception()

def sendSignature(privateKeySignature, server, privateKey, p, g):
    global token
    connected = False
    print("Voting in progress..")
    while not connected:
        try:
            server.connect(decryptVotes_address)
            print("Connected")
            server.send(token)
            msgCode = server.recv(1024).decode("utf-8")
            if msgCode == "Connection is secure":
                server.send(privateKeySignature)
                break
        except ConnectionRefusedError:
            time.sleep(5)
    while True:
        msgCode = server.recv(1024).decode("utf-8")
        if msgCode == "Verification complete":
            decryptEncryptedVotes(server, privateKey, p, g)

def decryptEncryptedVotes(server, privateKey, p, g):
    decryptedText = ""
    encryptedVote = server.recv(8192).decode("utf-8")
    splitEncryptedVote = encryptedVote.split("||")

    print("Decrypting votes")
    for i in range(0, len(splitEncryptedVote)-1):
        decryptedText = decryptedText + str(partialDecrypt(int(splitEncryptedVote[i]), privateKey,p)) + "||"
    print("Votes are decrypted.. Sending back to server")
    sendDecryptedVotes(server, decryptedText)

def sendDecryptedVotes(server, decryptedText):
    decryptedText = str.encode(str(decryptedText))
    server.send(decryptedText)
    print("Completed!. Exiting the program in 5 seconds")
    time.sleep(5)
    server.close()
    exit()

# partial decrypt function
def partialDecrypt(a, privateKey, p):
    return pow(a, p-1-privateKey, p)

# creating the Schnorr signature
def schnorrSignature(p, q, g, privateKey, message):
    messageInASCII = ''.join(str(ord(c)) for c in message)
    r = random.randint(1, q - 1)
    x = pow(g, r, p)
    e = hashThis(x, messageInASCII) % p
    s = pow((r - (privateKey * e)), 1, p - 1)
    return str(e), str(s)

def verifySchnorr(p, g, s, e, publicKey, message):
    messageInASCII = ''.join(str(ord(c)) for c in message)
    rv = pow(pow(g, s, p) * pow(publicKey, e, p), 1, p)
    ev = hashThis(rv, messageInASCII) % p
    return ev == e

# sample hash function
def hashThis(r, message):
    hash=sha256();
    hash.update(str(r).encode());
    hash.update(message.encode());
    return int(hash.hexdigest(),16)

def startSocket():
    port = number.getRandomRange(1, 65536)
    auth2_address = ('127.0.0.3',port)
    auth2Connection = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    auth2Connection.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    auth2Connection.bind(auth2_address)

    auth2TLS = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
    auth2TLS.load_verify_locations(cafile="server.crt")

    auth2 = auth2TLS.wrap_socket(auth2Connection, server_hostname="greek")

    return auth2

def main():
    auth2 = startSocket()
    secret = ""
    partialPublicKey = ""
    r = ""
    privateKey = ""
    count = 0

    # this message is to determine which server/authenticator sent the Schnorr signature
    message = "auth2"
    messageInASCII = ''.join(str(ord(c)) for c in message)

    while not secret or not partialPublicKey or not r or not privateKey:
        try:
            privateKey,secret,partialPublicKey,r,p,q,g = retrievePublicKeys(auth2)
        except:
            print("An error has occured")
            count += 1
        if count == 10:
            print("Please restart the server")
            exit()

    partialPublicKeyInfo = str(partialPublicKey) + "||" + str(r)
    ## Convert the commitmentInfo into bytes and send to server
    partialPublicKeyInfo = str.encode(partialPublicKeyInfo)
    secret = str.encode(str(secret))

    auth2 = startSocket()
    sendCommitment(secret,auth2)
    auth2.close()
    time.sleep(15)

    auth2 = startSocket()
    sendEncryptedPartialPublicKey(partialPublicKeyInfo,auth2)
    auth2.close()

    auth2 = startSocket()
    e, s = schnorrSignature(p, q, g, privateKey, 'Auth2')
    privateKeySignature = e + "||" + s
    privateKeySignature = str.encode(privateKeySignature + "||" + str(partialPublicKey))
    sendSignature(privateKeySignature, auth2, privateKey, p, g)

if __name__ == "__main__":
    main()
