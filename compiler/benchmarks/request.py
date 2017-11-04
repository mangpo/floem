from dsl2 import *
from compiler import Compiler
import target, queue2, net_real, library_dsl2


class Request(Element):
    def configure(self):
        self.inp = Input(Size, "void*", "void*")
        self.out = Output(Size, "void*", "void*")

    def impl(self):
        self.run_c(r'''
(size_t size, void* pkt, void* buff) = inp();
iokvs_message* m = (iokvs_message*) pkt;

m->ether.src = "\x68\x05\xca\x33\x13\x40"; // n30
m->ether.dest = "\x68\x05\xca\x33\x11\x3c"; // n33

m->ipv4.src = "\x0a\x03\x00\x1e";
m->ipv4.dest = "\x0a\x03\x00\x21";

static __thread uint16_t sport = 0;
udp.src_port = (++sport == 0 ? ++sport : sport);
m->udp.dest_port = htons(11211);

output { out(size, pkt, buff); }
        ''')

class gen(InternalLoop):
    def impl(self):
        net_alloc = net_real.NetAlloc()
        to_net = net_real.ToNet(configure=["net_alloc"])

        library_dsl2.Constant(configure=[64]) >> net_alloc
        net_alloc.oom >> library_dsl2.Drop()
        net_alloc.out >> Request() >> to_net


gen('gen', process='dpdk', cores=[0])
c = Compiler()
c.include_h = r'''
#include "protocol_binary.h"
'''
c.testing = 'while (1) pause();'
c.generate_code_and_compile()