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

    # Tell compiler not to generate this struct because it's already declared in some other header file.
    def init(self): self.declare = False

class protocol_binary_request_header(State):
    request = Field(protocol_binary_request_header_request)

    def init(self): self.declare = False


class iokvs_message(State):
    ether = Field('struct ether_hdr')
    ipv4 = Field('struct ipv4_hdr')
    udp = Field('struct udp_hdr')
    mcudp = Field('memcached_udp_header')
    mcr = Field(protocol_binary_request_header)
    payload = Field(Array(Uint(8)))
    layout = [ether, ipv4, udp, mcudp, mcr, payload]

    #def init(self): self.declare = False


class Display(Element):
    def configure(self):
        self.inp = Input(Size, 'void*', 'void*')
        self.out = Output('void*', 'void*')

    def impl(self):
        self.run_c(r'''
        (size_t size, void* p, void* buff) = inp();
        iokvs_message* m = (iokvs_message*) p;
        printf("packet: magic = %d, opcode = %d, keylen = %d, bodylen = %d\n", m->mcr.request.magic, m->mcr.request.opcode, m->mcr.request.keylen, m->mcr.request.bodylen);
        //int offset = sizeof(struct ether_hdr) + sizeof(struct ipv4_hdr) + sizeof(struct udp_hdr) + sizeof(memcached_udp_header);
        //printf("offset = %d, %p - %p\n",offset, &m->mcr.request.magic, m);

/*        uint8_t* x = (uint8_t*) p;
        int i;
        for(i=0; i<64; i++) {
          if(i % 16 == 0) printf("\n");
          printf("%x ", x[i]);
        }
        printf("---------------\n");

        for(i=offset; i< offset + 16; i++) {
          if(i % 16 == 0) printf("\n");
          printf("%x ", x[i]);
        }
*/
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
#include "protocol_binary.h"
'''
c.testing = r'''
while(1) pause();
'''
c.generate_code_and_run()
