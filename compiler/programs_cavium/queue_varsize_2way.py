from dsl2 import *
from compiler import Compiler
import target, queue2, net_real, library_dsl2
import queue_smart2

MAX_ELEMS = 64
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
        RxEnq, RxDeq, RxScan = queue_smart2.smart_queue("rx_queue", entry_size=64, size=32 * 1024, insts=n_cores,
                                                        channels=1, enq_blocking=True, enq_atomic=True, enq_output=True)
        rx_enq = RxEnq()
        rx_deq = RxDeq()

        TxEnq, TxDeq, TxScan = queue_smart2.smart_queue("tx_queue", entry_size=64, size=32 * 1024, insts=n_cores,
                                                        channels=1, enq_blocking=True, deq_atomic=True)
        tx_enq = TxEnq()
        tx_deq = TxDeq()

        class MakeKey(Element):
            def configure(self):
                self.inp = Input(Size, "void *", "void *")
                self.out = Output()

            def impl(self):
                self.run_c(r'''
        (size_t size, void* pkt, void* buff) = inp();
        state.pkt = pkt;
        state.pkt_buff = buff;

        static __thread uint32_t count = 0;
        count++;

        int keylen = 32 + (count % 4) * 8;
        state.keylen = keylen;
        uint8_t* key = (uint8_t*) malloc(keylen);
        int i;
        for(i=0; i<keylen; i++)
            key[i] = count;
        state.key = key;
        state.core = 0;

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

        class Scheduler(Element):
            def configure(self):
                self.out = Output(Size)

            def impl(self):
                self.run_c(r'''
            output { out(0); }
                ''')

        class Free(Element):
            def configure(self):
                self.inp = Input()

            def impl(self):
                self.run_c(r'''
            free(state.key);
                ''')

        class nic_rx(InternalLoop):
            def impl(self):
                from_net = net_real.FromNet()
                from_net_free = net_real.FromNetFree()

                from_net >> MakeKey() >> rx_enq.inp[0]
                rx_enq.done >> Free()
                rx_enq.done >> GetPktBuff() >> from_net_free
                from_net.nothing >> library_dsl2.Drop()

        class nic_tx(InternalLoop):
            def impl(self):
                Scheduler() >> tx_deq
                tx_deq.out[0] >> Display() >> library_dsl2.Drop()

        ############################ CPU #############################


        class Display(Element):
            def configure(self):
                self.inp = Input()
                self.out = Output()

            def impl(self):
                self.run_c(r'''
        static __thread size_t count = 0;
        count++;

        uint8_t* key = state.key;
        if(1) {
        //if(count % 1000000 == 0) {
                printf("count = %ld\n", count);
        printf("keylen = %d, key = %d %d\n", state.keylen, key[0], key[state.keylen-1]);
                }
        assert(key[0] == key[state.keylen-1]);

#if 0
        static uint8_t last = 0;
        if(key[0] > 0) {
            if(key[0] != last+1)
            printf("key = %d, last = %d\n", key[0], last);
            assert(key[0] == last+1);
        } else {
            if(last != 255)
            printf("key = %d, last = %d\n", key[0], last);
            assert(last == 255);
        }
        last = key[0];
#endif

#if 1
                static uint64_t lasttime = 0;
                struct timeval now;
                gettimeofday(&now, NULL);
                if((now.tv_sec*1000000 + now.tv_usec) - lasttime >= 1000000) {
                  lasttime = (now.tv_sec*1000000 + now.tv_usec);
                  printf("%ld pkts/s\n", count);
                  count = 0;
                }
#endif

        output { out(); }
                ''')

        class run(InternalLoop):
            def impl(self):
                Scheduler() >> rx_deq
                rx_deq.out[0] >> Display() >> tx_enq.inp[0]

        nic_rx('nic_rx', device=target.CAVIUM, cores=[0])
        nic_tx('nic_tx', device=target.CAVIUM, cores=[4])
        run('run', process='app', cores=range(1))

master_process('app')

c = Compiler(main)
c.generate_code_as_header()
c.depend = ['app']
c.compile_and_run("test_queue")
