from entropy import *
import logging as LOG
from Queue import Queue
from socket import AF_INET, socket, SOCK_STREAM
import sys
from serialization import *
from threading import Thread, Lock

root_port21k = 21000
root_port20k = 20000
address = 'localhost'
mHandler = None

def master_logic(line, client_vv, index):
    LOG.debug('%d: client.master_logic begins' % index)
    line = line.split()
    if 'add' == line[0]:
        songName = line[1]
        URL = line[2]
        s_id = int(line[3])
        # Send add song to the server
        msg = client_add(index, client_vv, songName, URL)
        send(s_id, msg)

    elif 'delete' == line[0]:
        songName = line[1]
        s_id = int(line[2])
        ## Send delete song to the server
        
        # get msg payload
        msg = client_delete(index, client_vv, songName)
        # send msg to server
        send(s_id, msg)

    elif 'get' == line[0]:
        songName = line[1]
        s_id = int(line[2])
        ## Send get song to the server
        msg = client_get(index, client_vv, songName)
        send(s_id, msg)
    LOG.debug('%d: client.master_logic ends' % index)

class MasterHandler(Thread):
    def __init__(self, index, address, port, queue):
        Thread.__init__(self)
        self.buffer = ''
        self.index = index
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.sock.bind((address, port))
        self.sock.listen(1)
        self.conn, self.addr = self.sock.accept()
        self.valid = True
        self.queue = queue
        LOG.debug('%d: client.MasterHandler()' % self.index)

    def run(self):
        while self.valid:
            if '\n' in self.buffer:
                (line, rest) = self.buffer.split('\n', 1)
                self.buffer = rest
                self.queue.put(line)
                LOG.debug('%d: client.MasterHandler got \'%s\'' % (self.index, line))
            else:
                try:
                    data = self.conn.recv(1024)
                    self.buffer += data
                except:
                    self.valid = False
                    self.conn.close()
                    break

    def send(self, s):
        self.conn.send(str(s) + '\n')

    def close(self):
        try:
            self.sock.close()
        except:
            pass

def send(pid, msg):
    global mHandler, root_port20k
    LOG.debug('   client.send()')
    if pid is -1:
        mHandler.send(msg)
        return
    try:
        sock = socket(AF_INET, SOCK_STREAM)
        sock.connect((address, root_port20k + pid))
        sock.send(str(msg) + '\n')
        sock.close()
    except:
        LOG.debug('SOCKET: ERROR ' + str(msg))


class WorkerHandler(Thread):
    def __init__(self, index, address, internal_port, queue):
        Thread.__init__(self)
        self.index = index
        self.queue = queue
        self.sock = socket(AF_INET, SOCK_STREAM)
        self.sock.bind((address, internal_port))
        self.sock.listen(1)
    
    def run(self):
        while True:
            conn, addr = self.sock.accept()
            handler = ServerHandler(conn, self.index, self.queue)
            handler.start()

def server_logic(line, client_vv, index):
    LOG.debug('   client.server_logic(%s)' % line)
    line = ClientDeserialize(line)
    LOG.debug('   client.server_logic(%s)' % line.__dict__)
    if line.url == ERR_DEP:
        if line.action_type == GET:
            # send msg to master
            msg = 'getResp %s:%s' % (line.song_name, line.url)
            send(-1, msg)
    # operation successful
    else:
        if line.action_type in [ADD, DELETE]:
            compute_vv(client_vv, line.vv)
        elif line.action_type == GET:
            # send msg to master
            compute_vv(client_vv, line.vv)
            msg = 'getResp %s:%s' % (line.song_name, line.url)
            LOG.debug('   client.server_logic about to send \'%s\'' % msg)
            send(-1,msg)
    LOG.debug('   client.server_logic ends')



class ServerHandler(Thread):
    def __init__(self, conn, index, queue):
        Thread.__init__(self)
        self.index = index
        self.conn = conn
        self.valid = True
        self.buffer = ''
        self.queue = queue
        LOG.debug('%d: client.ServerHandler()' % self.index)

    def run(self):
        while self.valid:
            if '\n' in self.buffer:
                (line, rest) = self.buffer.split('\n', 1)
                LOG.debug('%d: client.ServerHandler got \'%s\'' % (self.index, line))
                self.buffer = rest
                self.queue.put(line)
            else:
                try:
                    data = self.conn.recv(1024)
                    self.buffer += data
                except:
                    self.valid = False
                    self.conn.close()
                    break

def main():
    global address, mHandler, root_port21k
    vv = dict()
    mqueue = Queue()
    squeue = Queue()

    pid = int(sys.argv[1])
    port = int(sys.argv[2])

    LOG.basicConfig(filename='LOG/%d.log' % pid, level=LOG.DEBUG)

    whandler = WorkerHandler(pid, address, root_port21k + pid, squeue)
    mHandler = MasterHandler(pid, address, port, mqueue)
    whandler.start()
    mHandler.start()
    LOG.debug('%d: client.main()' % pid)

    while True:
        line = mqueue.get(block=True)
        master_logic(line, vv, pid)
        line = squeue.get(block=True)
        server_logic(line, vv, pid)

if __name__ == '__main__':
    main()
