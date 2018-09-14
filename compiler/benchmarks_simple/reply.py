from dsl import *
from compiler import Compiler
import target, queue, net, library

class Reply(Element):

    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.out = Output(SizeT, "void*", "void*")

    def impl(self):
        self.run_c(r'''
(size_t size, void* pkt, void* buff) = inp();
iokvs_message* m = (iokvs_message*) pkt;
//printf("pkt %ld\n", size);

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

            m->mcr.request.magic = PROTOCOL_BINARY_RES;
            m->mcr.request.opcode = PROTOCOL_BINARY_CMD_GET;
            m->mcr.request.datatype = PROTOCOL_BINARY_RAW_BYTES;
            m->mcr.request.status = htons(PROTOCOL_BINARY_RESPONSE_KEY_ENOENT);
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

class nic_rx(Segment):
    def impl(self):
        from_net = net.FromNet()
        to_net = net.ToNet()

        from_net.nothing >> library.Drop()

        from_net >> Reply() >> to_net


nic_rx('nic_rx', process='dpdk', cores=range(2))
#nic_rx('nic_rx', device=target.CAVIUM, cores=range(1))
c = Compiler()
c.include = r'''
#include "protocol_binary.h"
'''
c.testing = 'while (1) pause();'
#c.generate_code_as_header()
c.generate_code_and_compile()
