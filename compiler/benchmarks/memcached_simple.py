from dsl2 import *
from compiler import Compiler
import net_real, library_dsl2
import queue_smart2

n_cores = 1

class MyState(State):
    pkt = Field('void*')
    pkt_buff = Field('void*')
    key = Field('void*', copysize='state.keylen')
    keylen = Field(Uint(16))
    core = Field(Size)


class main(Pipeline):
    state = PerPacket(MyState)

    def impl(self):
        # Queue
        RxEnq, RxDeq, RxScan = queue_smart2.smart_queue("rx_queue", entry_size=64, size=512, insts=n_cores,
                                                        channels=1, enq_blocking=True, enq_atomic=False, enq_output=True)
        rx_enq = RxEnq()
        rx_deq = RxDeq()

        class MakeKey(Element):
            def configure(self):
                self.inp = Input(Size, "void *", "void *")
                self.out = Output()

            def impl(self):
                self.run_c(r'''
        (size_t size, void* pkt, void* buff) = inp();
        state.pkt = pkt;
        state.pkt_buff = buff;
        iokvs_message* m = (iokvs_message*) pkt;

        //printf("keylen = %d\n", htons(m->mcr.request.keylen));
        //state.keylen = htons(m->mcr.request.keylen);
        //state.key = m->payload + m->mcr.request.extlen;
        //printf("size = %ld\n", size);
        state.keylen = 32;  // 32->64 vs 188(size)->192
        state.key = m;
        state.core = 0; //cvmx_get_core_num();

        output { out(); }
                ''')

        class GetPktBuff(Element):
            def configure(self):
                self.inp = Input()
                self.out = Output("void*", "void*")

            def impl(self):
                self.run_c(r'''
        void* pkt = state.pkt;
        void* pkt_buff = state.pkt_buff;
        output { out(pkt, pkt_buff); }
                ''')

        class nic_rx(InternalLoop):
            def impl(self):
                from_net = net_real.FromNet()
                from_net_free = net_real.FromNetFree()

                from_net >> MakeKey() >> rx_enq.inp[0]
                rx_enq.done >> GetPktBuff() >> from_net_free
                from_net.nothing >> library_dsl2.Drop()


        ############################ CPU #############################
        class Scheduler(Element):
            def configure(self):
                self.out = Output(Size)

            def impl(self):
                self.run_c(r'''
    static size_t core = 0;
    core = (core+1) %s %d;
                output { out(core); }
                ''' % ('%', n_cores))

        class Display(Element):
            def configure(self):
                self.inp = Input()

            def impl(self):
                self.run_c(r'''
    void *key = state.key;
    int keylen = state.keylen;

    static size_t count = 0;
    static uint64_t lasttime = 0;
    count++;
    if(count == 100000) {
        struct timeval now;
        gettimeofday(&now, NULL);

        uint64_t thistime = now.tv_sec*1000000 + now.tv_usec;
        printf("%zu pkts/s\n", (count * 1000000)/(thistime - lasttime));
        lasttime = thistime;
        count = 0;
    }
                ''')

        class run(InternalLoop):
            def impl(self):
                Scheduler() >> rx_deq
                rx_deq.out[0] >> Display()

        #nic_rx('nic_rx', device=target.CAVIUM, cores=range(n_cores))
        nic_rx('nic_rx', process='dpdk', cores=range(n_cores))
        run('run', process='app', cores=range(1))


master_process('app')

c = Compiler(main)
c.include = r'''
#include "protocol_binary.h"
'''
c.generate_code_as_header()
c.depend = {"test_queue": ['app'], "test_queue_dpdk": ['dpdk']}
c.compile_and_run(["test_queue", "test_queue_dpdk"])
