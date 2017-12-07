from dsl import *
from compiler import Compiler
import net_real, library

n_cores = 1

class MyState(State):
    core = Field(Size)
    payload = Field(Pointer(Uint(8)), copysize='sizeof(param_entry)')


class Reply(Element):
    def configure(self):
        self.inp = Input(Size, "void*", "void*")
        self.out = Output(Size, "void*", "void*")

    def impl(self):
        self.run_c(r'''
(size_t size, void* pkt, void* buff) = inp();
param_message* m = (param_message*) pkt;

struct eth_addr src = m->ether.src;
struct eth_addr dest = m->ether.dest;
m->ether.src = dest;
m->ether.dest = src;

struct ip_addr src_ip = m->ipv4.src;
struct ip_addr dest_ip = m->ipv4.dest;
m->ipv4.src = dest_ip;
m->ipv4.dest = src_ip;

uint16_t src_port = m->udp.src_port;
uint16_t dest_port = m->udp.dest_port;
m->udp.dest_port = src_port;
m->udp.src_port = dest_port;

m->status = 1;

/*
uint8_t* p = pkt;
int i;
for(i=0; i<64; i++) {
  printf("%x ",p[i]);
}
printf("\n");
*/

output { out(size, pkt, buff); }
        ''')


class Update(Element):
    def configure(self):
        self.inp = Input(Size, "void *", "void *")

    def impl(self):
        self.run_c(r'''
(size_t size, void* pkt, void* buff) = inp();
param_message* m = (param_message*) pkt;
//printf("udpate: pool = %d, param = %lf\n", m->pool, m->param);
update_param(m->pool, m->param);
        ''')


class run(InternalLoop):
    def impl(self):
        from_net = net_real.FromNet()
        to_net = net_real.ToNet()

        from_net.nothing >> library.Drop()

        from_net >> Update()
        from_net >> Reply() >> to_net


run('run', process='dpdk', cores=range(n_cores))

c = Compiler()
c.include = r'''
#include "protocol_binary.h"
'''
c.generate_code_as_header()
c.depend = ['dpdk', 'param_update']
c.compile_and_run("test_queue")
