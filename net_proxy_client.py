import socket
import time
import select
from net_proxy_common import TranslatorNode, NetProxy


class NetProxyClient(NetProxy):
    def __init__(self, server_ip, server_port, proxy_ip, proxy_port):
        '''
        server_ip: server的ip
        server_port: server的port
        proxy_ip: proxyServer的ip
        proxy_port: proxyServer的port
        '''
        super(NetProxyClient, self).__init__()
        self.server_ip = server_ip
        self.server_port = server_port
        self.proxy_ip = proxy_ip
        self.proxy_port = proxy_port
        self.regist_success = False
        try:
            self.__regist_server()    # 与proxyServer建立proxy_conmunicate_conn
            self.regist_success = True
        except Exception as e:
            print('can nor connect proxy server')

    def __create_conn(self, ip_port):
        '''
        根据ip和port建立连接
        '''
        conn = None
        try:
            conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            conn.setblocking(False)
            conn.connect(ip_port)
        except Exception as e:
            pass
        return conn

    def __regist_server(self):
        '''
        与服务器建立proxy_conmunicate_conn
        '''
        self.proxy_conmunicate_conn = self.__create_conn((self.proxy_ip, self.proxy_port))
        self.proxy_conmunicate_conn.send(self.command.proxy_communicate_verify)    # 发送指令

    def __add_proxy_conn(self):
        '''
        新建一个与proxyServer的连接，并新建一个到server的连接，将两者关联
        '''
        try:
            proxy_conn = self.__create_conn((self.proxy_ip, self.proxy_port))
            proxy_conn.send(self.command.proxy_client_verify)
            server_conn = self.__create_conn((self.server_ip, self.server_port))
            translator_node = TranslatorNode()
            translator_node.src_conn = proxy_conn
            translator_node.dest_conn = server_conn
            self.translator_node_pool.append(translator_node)
            self.inputs.append(proxy_conn)
            self.inputs.append(server_conn)
        except Exception as e:
            return

    def __translate(self, conn, packet):
        '''
        转发数据包
        '''
        self.translate(conn, packet)

    def proxy_serve(self):
        '''
        启动proxyClient服务
        '''
        if not self.regist_success:
            return
        self.inputs = [self.proxy_conmunicate_conn]
        while True:
            translating = False
            self.inputs = [i for i in self.inputs if not i._closed]
            rlist, wlist, elist = select.select(self.inputs, [], [], 5)
            for event in rlist:
                translating = True
                try:
                    packet = event.recv(self.get_buffer_size(event))
                    self.set_buffer_size(event, packet)
                except Exception as e:
                    event.close()
                    if event == self.proxy_conmunicate_conn:
                        print('proxy server disconnect')
                        return
                    continue
                if event == self.proxy_conmunicate_conn:
                    if not packet:
                        self.proxy_conmunicate_conn.close()
                        print('proxy server disconnect')
                        return
                    if packet == self.command.proxy_client_add_conn:
                        self.__add_proxy_conn()
                else:
                    self.__translate(event, packet)
            if not translating:
                time.sleep(1)
            else:
                time.sleep(0.01)

if __name__ == '__main__':
    web_client = NetProxyClient(server_ip='127.0.0.1', server_port=8089, proxy_ip='127.0.0.1', proxy_port=9089)
    web_client.proxy_serve()