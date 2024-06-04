def getKey():
    file = open("API.txt", "r")
    file.readline()
    key = file.readline().strip()
    file.readline()
    secret = file.readline().strip()
    return key, secret

def getAlphaKey():
    file = open("AlphaVantage.txt", "r")
    key = file.readline().strip()
    return key