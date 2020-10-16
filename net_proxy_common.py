from enum import Enum


class TranslatorNode:
    def __init__(self):
        self.src_conn = None
        self.dest_conn = None
        self.src_to_dest_packet = []
        self.buffer_size = 1024


class Command:
    def __init__(self):
        '''
        proxyClient和proxyServer约定的指令，指令定义为私有变量，不能直接改变
        通过property装饰器，指定这些只可访问，不可修改
        '''
        split_str = '\r\n\r\n\r\n****\r\n\r\n\r\n'
        self.__proxy_client_verify = bytes('{0}I am proxy client{0}'.format(split_str).encode())
        self.__confirm_proxy = bytes('{0}OK{0}'.format(split_str).encode())
        self.__proxy_communicate_verify = bytes('{0}I am proxy communicator{0}'.format(split_str).encode())
        self.__proxy_client_add_conn = bytes('{0}Create a connection{0}'.format(split_str).encode())

    @property
    def proxy_client_verify(self):
        return self.__proxy_client_verify

    @property
    def confirm_proxy(self):
        return self.__confirm_proxy

    @property
    def proxy_communicate_verify(self):
        return self.__proxy_communicate_verify

    @property
    def proxy_client_add_conn(self):
        return self.__proxy_client_add_conn


class TranslateStatus(Enum):
    COMPLETE = 0
    ADD_TRANSLATOR_NODE = 1
    ADD_PROXY_CLIENT_CONN = 2


class NetProxy:
    def __init__(self):
        self.buffer_size = 1024
        self.max_buffer_size = 100 * 1024 * 1024
        self.command = Command()
        self.proxy_conmunicate_conn = None
        self.translator_node_pool = []
        self.inputs = []

    def remove_translator_node(self, translator_node):
        '''
        断开连接之后的操作
        '''
        if translator_node.src_conn:
            translator_node.src_conn.close()
        if translator_node.dest_conn:
            translator_node.dest_conn.close()
        if translator_node.src_conn in self.inputs:
            self.inputs.remove(translator_node.src_conn)
        if translator_node.dest_conn in self.inputs:
            self.inputs.remove(translator_node.dest_conn)
        if translator_node in self.translator_node_pool:
            self.translator_node_pool.remove(translator_node)

    def translate(self, conn, packet):
        '''
        转发数据包
        '''
        for idx, translator_node in enumerate(self.translator_node_pool):
            if translator_node.src_conn == conn:
                if translator_node.dest_conn != None:
                    if packet:
                        try:
                            translator_node.dest_conn.send(packet)
                        except Exception as e:
                            self.remove_translator_node(translator_node)
                    else:
                        self.remove_translator_node(translator_node)
                    return TranslateStatus.COMPLETE
                else:
                    if packet:
                        translator_node.src_to_dest_packet.append(packet)
                        return TranslateStatus.ADD_PROXY_CLIENT_CONN
                    else:
                        self.remove_translator_node(translator_node)
                        return TranslateStatus.COMPLETE
            elif translator_node.dest_conn == conn:
                if packet:
                    try:
                        translator_node.src_conn.send(packet)
                    except Exception as e:
                        self.remove_translator_node(translator_node)
                else:
                    self.remove_translator_node(translator_node)
                return TranslateStatus.COMPLETE
        return TranslateStatus.ADD_TRANSLATOR_NODE

    def get_buffer_size(self, conn):
        '''
        应该设置多大的buffer_size
        '''
        for idx, translator_node in enumerate(self.translator_node_pool):
            if translator_node.src_conn == conn or translator_node.dest_conn == conn:
                return translator_node.buffer_size
        return self.buffer_size

    def set_buffer_size(self, conn, packet):
        '''
        根据当前接收到的数据判断是否需要改变buffer_size
        '''
        for idx, translator_node in enumerate(self.translator_node_pool):
            if translator_node.src_conn == conn or translator_node.dest_conn == conn:
                if len(packet) == translator_node.buffer_size:
                    if translator_node.buffer_size * 2 <= self.max_buffer_size:
                        translator_node.buffer_size = translator_node.buffer_size * 2
                elif len(packet) < self.buffer_size and translator_node.buffer_size > self.buffer_size:
                    translator_node.buffer_size = self.buffer_size
                return

