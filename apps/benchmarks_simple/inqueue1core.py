from floem import *

n_queues = 8
n_nic_cores = 11
size = 256

class MyState(State):
    key = Field(Int)
    qid = Field(Int)
    data = Field('void*', size='state.key')


class main(Flow):
    state = PerPacket(MyState)

    def impl(self):
        # Queue
        RxEnq, RxDeq, RxScan = queue_smart.smart_queue("rx_queue", entry_size=size, size=512, insts=n_queues,
                                                       channels=1, enq_blocking=True, enq_atomic=True, enq_output=False)
        rx_enq = RxEnq()
        rx_deq = RxDeq()

        class MakeKey(Element):
            def configure(self):
                self.out = Output()

            def impl(self):
                self.run_c(r'''
        static void* p = NULL;

        int n = 246;
        if(p == NULL) p = malloc(n);

        state.key = n;
        state.data = p;

        static __thread int qid = 0;
        state.qid = qid;
        qid = (qid + 1) %s %d;

        output { out(); }
                ''' % ('%', n_queues))


        class nic_rx(Segment):
            def impl(self):
                MakeKey() >> rx_enq.inp[0]


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
    state.data;

    static __thread size_t count = 0;
    static __thread uint64_t lasttime = 0;
    count++;
                if(count == 1000000) {
        struct timeval now;
        gettimeofday(&now, NULL);

        uint64_t thistime = now.tv_sec*1000000 + now.tv_usec;
        printf("%s pkts/s %s Gbits/s\n", (count * 1000000)/(thistime - lasttime), (count * %d * 8.0)/(thistime - lasttime)/1000);
        lasttime = thistime;
        count = 0;
    }
                ''' % ('%zu', '%f', size))

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
