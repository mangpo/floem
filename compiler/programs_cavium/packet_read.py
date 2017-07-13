import net_real, target
from dsl2 import *
from compiler import Compiler

class Display(Element):
    def configure(self):
        self.inp = Input(Size, 'void *', 'void *')
        self.out = Output('void *', 'void *')

    def impl(self):
        self.run_c(r'''
(size_t sz, void* p, void* buff) = inp();
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

class Drop(Element):
    def configure(self):
        self.inp = Input()

    def impl(self):
        self.run_c(r'''while (0); ''')

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
        drop = Drop('drop')
        from_net.out >> display >> from_net_free
        from_net.nothing >> drop
        size >> net_alloc
        net_alloc.out >> PreparePkt() >> to_net
        net_alloc.oom >> drop
        net_alloc.out >> net_alloc_free

        run_order(from_net_free, size)
        run_order(to_net, net_alloc_free)

    def impl2(self):
        from_net.out >> Display() >> PreparePkt() >> to_net
        from_net.out >> from_net_free
        from_net.nothing >> Drop('drop')
        run_order(to_net, from_net_free)

test('test', process='dpdk', cores=[0,1,2,3])

c = Compiler()
c.include = r'''#include "packet_build.h"'''
c.generate_code_as_header()
