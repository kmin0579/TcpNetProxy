import socket
import time
import select
from net_proxy_common import TranslatorNode, NetProxy, TranslateStatus


class NetProxyServer(NetProxy):
    def __init__(self, server_port):
        '''
        server_port: 在哪个端口工作
        '''
        super(NetProxyServer, self).__init__()
        self.server_port = server_port
        self.host = '0.0.0.0'

    def __create_server(self, ip_port):
        '''
        创建server socket,用来接收连接
        '''
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(ip_port)
        server.setblocking(False)
        server.listen()
        return server
        
    def __match_conn(self, conn):
        '''
        将proxyClient的连接关联到client的连接
        这里是查找哪个client的连接没有与之关联的连接，找到了就把当前proxyClient的连接关联过去
        '''
        for translator_node in self.translator_node_pool:
            if translator_node.dest_conn == None:
                translator_node.dest_conn = conn
                for packet in translator_node.src_to_dest_packet:
                    translator_node.dest_conn.send(packet)
                return
        conn.close()

    def __add_proxy_conn(self):
        '''
        向proxyClient发送添加连接指令
        '''
        if self.proxy_conmunicate_conn != None:
            self.proxy_conmunicate_conn.send(self.command.proxy_client_add_conn)

    def __translate(self, conn, packet):
        translate_status = self.translate(conn, packet)
        if translate_status == TranslateStatus.ADD_PROXY_CLIENT_CONN:    # client的连接还没关联，通知proxyClient建立连接与之关联
            self.__add_proxy_conn()
        elif translate_status == TranslateStatus.ADD_TRANSLATOR_NODE:    # 新来一个client连接，建立TranslatorNode
            if packet:
                translator_node = TranslatorNode()
                translator_node.src_conn = conn
                translator_node.src_to_dest_packet.append(packet)
                self.translator_node_pool.append(translator_node)
                self.__add_proxy_conn()
            else:
                conn.close()
                self.inputs.remove(conn)

    def proxy_serve(self):
        '''
        启动proxyServer服务
        '''
        print('start proxy server: {}:{}'.format(self.host, self.server_port))
        proxy_server = self.__create_server((self.host, self.server_port))
        self.inputs = [proxy_server]
        while True:
            translating = False
            for translator_node in self.translator_node_pool:
                if translator_node.src_conn and translator_node.src_conn._closed:
                    translator_node.dest_conn.close()
                if translator_node.dest_conn and translator_node.dest_conn._closed:
                    translator_node.src_conn.close()
            self.translator_node_pool = [t for t in self.translator_node_pool if not ((t.src_conn and t.src_conn._closed) or (t.dest_conn and t.dest_conn._closed))]
            self.inputs = [i for i in self.inputs if not i._closed]
            rlist, wlist, elist = select.select(self.inputs, [], [], 5)
            for event in rlist:
                translating = True
                if event == proxy_server:
                    conn, addr = proxy_server.accept()
                    self.inputs.append(conn)
                else:
                    try:
                        packet = event.recv(self.get_buffer_size(event))
                        self.set_buffer_size(event, packet)
                    except Exception as e:
                        event.close()
                        if event == self.proxy_conmunicate_conn:
                            print('proxy client disconnect')
                            self.proxy_conmunicate_conn = None
                        continue
                    if packet == self.command.proxy_client_verify:
                        self.__match_conn(event)
                    elif packet == self.command.proxy_communicate_verify:
                        if self.proxy_conmunicate_conn == None:
                            self.proxy_conmunicate_conn = event
                        else:
                            event.close()
                    else:
                        self.__translate(event, packet)
            if not translating:
                time.sleep(1)
            else:
                time.sleep(0.01)

if __name__ == '__main__':
    web_proxy = NetProxyServer(int(9089))
    web_proxy.proxy_serve()