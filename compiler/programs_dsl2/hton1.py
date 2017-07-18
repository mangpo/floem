from dsl2 import *
import net_real
from compiler import Compiler

class protocol_binary_request_header_request(State):
    magic = Field(Uint(8))
    opcode = Field(Uint(8))
    keylen = Field(Uint(16))
    extlen = Field(Uint(8))
    datatype = Field(Uint(8))
    status = Field(Uint(16))
    bodylen = Field(Uint(32))
    opaque = Field(Uint(32))
    cas = Field(Uint(64))

class protocol_binary_request_header(State):
    request = Field(protocol_binary_request_header_request)


class iokvs_message(State):
    ether = Field('struct ether_hdr')
    ipv4 = Field('struct ipv4_hdr')
    udp = Field('struct udp_hdr')
    mcudp = Field('memcached_udp_header')
    mcr = Field(protocol_binary_request_header)
    payload = Field(Array(Uint(8)))

class Display(Element):
    def configure(self):
        self.inp = Input(Size, 'void*', 'void*')
        self.out = Output('void*', 'void*')

    def impl(self):
        self.run_c(r'''
        (size_t size, void* p, void* buff) = inp();
        iokvs_message* m = (iokvs_message*) p;
        printf("packet: opcode = %d, keylen = %d, bodylen = %d\n", m->mcr.request.opcode, m->mcr.request.keylen, m->mcr.request.bodylen);
        output { out(p, buff); }
        ''')

class Drop(Element):
    def configure(self):
        self.inp = Input()

    def impl(self):
        self.run_c("")

class run(InternalLoop):
    def impl(self):
        from_net = net_real.FromNet()
        from_net_free = net_real.FromNetFree()
        hton = net_real.HTON(configure=['iokvs_message'])

        from_net.out >> hton >> Display() >> from_net_free
        from_net.nothing >> Drop()

iokvs_message()
run('run', process='dpdk')

c = Compiler()
c.include = r'''
#include <rte_ether.h>
#include <rte_ip.h>
#include <rte_udp.h>
#include <rte_arp.h>
#include <rte_ethdev.h>
'''
c.generate_code_and_run()