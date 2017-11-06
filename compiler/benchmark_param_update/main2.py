from dsl2 import *
from compiler import Compiler
import target, queue2, net_real, library_dsl2, queue_smart2

n_cores = 1

class MyState(State):
    pkt = Field('void*')

class main(Pipeline):
    state = PerPacket(MyState)

    def impl(self):
        class Reply(Element):
            def configure(self):
                self.inp = Input(Size, "void*", "void*")
                self.out = Output(Size, "void*", "void*")

            def impl(self):
                self.run_c(r'''
        (size_t size, void* pkt, void* buff) = inp();

        output { out(size, pkt, buff); }
                ''')

        class Copy(Element):
            def configure(self):
                self.inp = Input(Size, "void*", "void*")
                self.out = Output(Size, "void*", "void*")

            def impl(self):
                self.run_c(r'''
        (size_t size, void* pkt, void* buff) = inp();
        memcpy(pkt, state.pkt, size);

        output { out(size, pkt, buff); }
                ''')

        class Fork(Element):
            def configure(self):
                self.inp = Input(Size)
                self.out1 = Output(Size)
                self.out2 = Output(Size)
                self.out3 = Output(Size)
                self.out4 = Output(Size)
                self.out5 = Output(Size)

            def impl(self):
                self.run_c(r'''
        (size_t size) = inp();
        output { 
                out1(size); 
                out2(size); 
                out3(size); 
                out4(size); 
                out5(size); 
                }
                    ''')

        class Update(Element):
            def configure(self):
                self.inp = Input(Size, "void *", "void *")
                self.out = Output(Size)

            def impl(self):
                self.run_c(r'''
        (size_t size, void* pkt, void* buff) = inp();
        param_message* m = (param_message*) pkt;
        //printf("udpate: pool = %d, param = %lf\n", m->pool, m->param);
        update_param(m->pool, m->param);

        state.pkt = pkt;

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

        output { out(size); }
                ''')

        class run(InternalLoop):
            def impl(self):
                from_net = net_real.FromNet()
                update = Update()
                to_net1 = net_real.ToNet(configure=["from_net"])
                to_net2 = net_real.ToNet(configure=["alloc"])
                net_alloc = net_real.NetAlloc()
                copy = Copy()
                fork = Fork()

                from_net.nothing >> library_dsl2.Drop()

                #from_net >> update >> library_dsl2.Drop()
                from_net >> update >> fork
                fork.out1 >> net_alloc
                fork.out2 >> net_alloc
                fork.out3 >> net_alloc
                fork.out4 >> net_alloc
                fork.out5 >> net_alloc

                net_alloc >> copy >> to_net2
                net_alloc.oom >> library_dsl2.Drop()

                from_net >> Reply() >> to_net1

        run('run', process='dpdk', cores=range(n_cores))

c = Compiler(main)
c.include = r'''
#include "protocol_binary.h"
'''
c.generate_code_as_header()
c.depend = ['dpdk', 'param_update']
c.compile_and_run("test_queue")
