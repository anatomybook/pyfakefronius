import socket
import datetime

def make_timestamp():
    return datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()

UDP_IP = "0.0.0.0"
UDP_PORT = 50052
QUERY = b"{\"Query\":{\"DeviceFamily\":\"Datamanager\",\"ReplyOnPort\":50052},\"V\":1}"
RESPONSE = b"{\"Response\":{\"DeviceFamily\":\"DataManager\",\"Hardware\":\"2.4E\",\"Id\":\"240.1534227\",\"Label\":\"&#83;&#111;&#98;&#111;&#116;&#116;&#97;&#32;&#87;&#105;&#116;&#116;&#108;&#105;&#110;&#103;&#101;&#110;\",\"Model\":\"WILMA2-O\",\"Software\":\"3.21.4-1\"},\"V\":1}"
#RESPONSE = b"Escaped \"string\""

sock = socket.socket(socket.AF_INET, # Internet
                     socket.SOCK_DGRAM) # UDP
sock.bind((UDP_IP, UDP_PORT))

while True:
    data, addr = sock.recvfrom(1024) # buffer size is 1024 bytes
    print("received message: %s @ %s" % (data, make_timestamp()))
    ip, port = addr
    print("received addr:", addr)
    print("received ip:%s, port:%d" % (ip, port))
    #ip = "192.168.178.60"
    if data == QUERY:
        print("Got query for Datamanager, answering to ip:%s, port:%d" % (ip, UDP_PORT))
        sock.sendto(RESPONSE, (ip, UDP_PORT))
