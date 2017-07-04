import net_real, target
from dsl2 import *
from compiler import Compiler

class Display(Element):
    def configure(self):
        self.inp = Input('void *', 'void *')
        self.out = Output('void *', 'void *')

    def impl(self):
        self.run_c(r'''
(void* p, void* buff) = inp();
{
    int i;
    uint8_t* pkt = (uint8_t*) p;

    for (i = 0; i < 16; i++) {
        printf("%x ", pkt[i]);
    }
    printf("\n");
}
output { out(p, buff); }
        ''')


class Const(Element):
    def configure(self):
        self.out = Output(Size)

    def impl(self):
        self.run_c("output { out(14 + 20 + 8 + 16); }")


class PreparePkt(Element):
    def configure(self):
        self.inp = Input("void *", "void *")
        self.out = Output(Size, "void *", "void *")  # size, dest_port, packet, buffer

    def impl(self):
        self.run_c(r'''
    (void* pkt_ptr, void* buf) = inp();
    rebuild_ether_header(pkt_ptr);
    rebuild_ip_header(pkt_ptr);
    rebuild_udp_header(pkt_ptr);
    rebuild_payload(pkt_ptr);
    recalculate_ip_chksum(pkt_ptr);
    recalculate_udp_chksum(pkt_ptr);
    output { out(14 + 20 + 8 + 16, pkt_ptr, buf); }
        ''')

from_net = net_real.FromNet()
from_net_free = net_real.FromNetFree()
net_alloc = net_real.NetAlloc()
net_alloc_free = net_real.NetAllocFree()
to_net = net_real.ToNet()

class test(InternalLoop):
    def impl(self):
        size = Const()
        display = Display()
        from_net >> display >> from_net_free
        size >> net_alloc >> PreparePkt() >> to_net
        net_alloc >> net_alloc_free

        run_order(from_net_free, size)
        run_order(to_net, net_alloc_free)

    def impl2(self):
        from_net >> Display() >> PreparePkt() >> to_net
        from_net >> from_net_free
        run_order(to_net, from_net_free)

test('test', device=target.CAVIUM, cores=[0,1,2,3])

c = Compiler()
c.include = r'''#include "packet_build.h"'''
c.generate_code_as_header()