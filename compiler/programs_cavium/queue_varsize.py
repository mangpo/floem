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
        RxEnq, RxDeq, RxScan = queue_smart2.smart_queue("rx_queue", 32 * 1024, n_cores, 1,
                                                        enq_output=True, enq_blocking=True,
                                                        enq_atomic=True)
        rx_enq = RxEnq()
        rx_deq = RxDeq()

        # TxEnq, TxDeq, TxScan = queue_smart2.smart_queue("tx_queue", 32 * 1024, n_cores, 1,
        #                                                 enq_blocking=True, enq_output=True,
        #                                                 deq_atomic=True)
        # tx_enq = TxEnq()
        # tx_deq = TxDeq()

        class MakeKey(Element):
            def configure(self):
                self.inp = Input(Size, "void *", "void *")
                self.out = Output()

            def impl(self):
                self.run_c(r'''
        (size_t size, void* pkt, void* buff) = inp();
        state.pkt = pkt;
        state.pkt_buff = buff;

        static __thread uint32_t count = 1;

        state.keylen = 32 + (count % 4) * 8;
        uint8_t* key = (uint8_t*) malloc(state.keylen);
        int i;
        for(i=0; i<state.keylen; i++)
            key[i] = count;
        state.key = key;

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

        ############################ CPU #############################
        class Scheduler(Element):
            def configure(self):
                self.out = Output(Size)

            def impl(self):
                self.run_c(r'''
            output { out(0); }
                ''')

        class Display(Element):
            def configure(self):
                self.inp = Input()

            def impl(self):
                self.run_c(r'''
        uint8_t* key = state.key;
        printf("keylen = %d, key = %d %d\n", state.keylen, key[0], key[state.keylen-1]);
        assert(key[0] == key[state.keylen-1]);
                ''')

        class run(InternalLoop):
            def impl(self):
                Scheduler() >> rx_deq
                rx_deq.out[0] >> Display()

        nic_rx('nic_rx', device=target.CAVIUM, cores=range(1))
        run('run', process='app', cores=range(1))

master_process('app')

c = Compiler(main)
c.generate_code_as_header()
c.depend = ['app']
c.compile_and_run("test_queue")
