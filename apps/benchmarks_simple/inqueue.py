from floem import *

n_nic_cores = 10
n_queues = 7

class MyState(State):
    pkt = Field('void*')
    pkt_buff = Field('void*')
    key = Field('void*', size=64)
    qid = Field(Int)


class main(Flow):
    state = PerPacket(MyState)

    def impl(self):
        # Queue
        RxEnq, RxDeq, RxScan = queue_smart.smart_queue("rx_queue", entry_size=96, size=1024, insts=n_queues,
                                                       channels=1, enq_blocking=True, enq_atomic=True, enq_output=True)
        rx_enq = RxEnq()
        rx_deq = RxDeq()

        class MakeKey(Element):
            def configure(self):
                self.inp = Input(SizeT, "void *", "void *")
                self.out = Output()

            def impl(self):
                self.run_c(r'''
        (size_t size, void* pkt, void* buff) = inp();
        state.pkt = pkt;
        state.pkt_buff = buff;
        iokvs_message* m = (iokvs_message*) pkt;

        state.key = m;
        static int qid = 0;
        state.qid= qid;
        qid = (qid+1) %s %d;

        output { out(); }
                ''' % ('%', n_queues))

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

        class nic_rx(Segment):
            def impl(self):
                from_net = net.FromNet()
                from_net_free = net.FromNetFree()

                from_net >> MakeKey() >> rx_enq.inp[0]
                rx_enq.done >> GetPktBuff() >> from_net_free
                from_net.nothing >> library.Drop()


        ############################ CPU #############################
        class Scheduler(Element):
            def configure(self):
                self.inp = Input(Int)
                self.out = Output(Int)

            def impl(self):
                self.run_c(r'''
    (int core_id) = inp();
    output { out(core_id); }
    ''')

        class Display(Element):
            def configure(self):
                self.inp = Input()

            def impl(self):
                self.run_c(r'''
    void *key = state.key;

    static __thread size_t count = 0;
    static __thread uint64_t lasttime = 0;
    count++;
                if(count == 1000000) {
        struct timeval now;
        gettimeofday(&now, NULL);

        uint64_t thistime = now.tv_sec*1000000 + now.tv_usec;
        printf("%zu pkts/s %f Gbits/s\n", (count * 1000000)/(thistime - lasttime), (count * 64 * 8.0)/(thistime - lasttime)/1000);
        lasttime = thistime;
        count = 0;
    }
                ''')

        class run(Segment):
            def impl(self):
                self.core_id >> rx_deq
                rx_deq.out[0] >> Display()

        nic_rx('nic_rx', device=target.CAVIUM, cores=range(n_nic_cores))
        run('run', process='app', cores=range(n_queues))


c = Compiler(main)
c.include = r'''
#include "protocol_binary.h"
'''
c.generate_code_as_header()
c.depend = ['app']
c.compile_and_run("test_queue")
