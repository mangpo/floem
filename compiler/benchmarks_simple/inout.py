from dsl import *
from compiler import Compiler
import target
import queue_smart

n_nic_rx = 1
n_nic_tx = 1
n_queues = 1

class MyState(State):
    key = Field(Uint(64))
    qid = Field(Int)


class main(Flow):
    state = PerPacket(MyState)

    def impl(self):
        # Queue
        RxEnq, RxDeq, RxScan = queue_smart.smart_queue("rx_queue", entry_size=64, size=1024, insts=n_queues,
                                                       channels=1, enq_blocking=True)
        TxEnq, TxDeq, TxScan = queue_smart.smart_queue("tx_queue", entry_size=64, size=1024, insts=n_queues,
                                                       channels=1, enq_blocking=True)
        rx_enq = RxEnq()
        rx_deq = RxDeq()
        tx_enq = TxEnq()
        tx_deq = TxDeq()

        ############################ NIC RX #############################
        class MakeKey(Element):
            def configure(self):
                self.out = Output()

            def impl(self):
                self.run_c(r'''
        state.qid= 0;
        state.key = core_time_now_us();

        output { out(); }
                ''')

        class nic_rx(Pipeline):
            def impl(self):
                MakeKey() >> rx_enq.inp[0]


        ############################ CPU #############################
        class run(Pipeline):
            def impl(self):
                self.core_id >> rx_deq
                rx_deq.out[0] >> tx_enq.inp[0]

        ############################ NIC RX #############################

        class Display(Element):
            def configure(self):
                self.inp = Input()

            def impl(self):
                self.run_c(r'''
        uint64_t now = core_time_now_us();
        uint64_t latency = now - state.key;
                
        static __thread size_t count = 0;
        static __thread size_t latency_tot = 0;
        count++;
        latency_tot += latency;
        if(count == 1000) {
            printf("latency = %f\n", 1.0*latency_tot/count);
            count = latency_tot = 0;
        }
                    ''')

        class nic_tx(Pipeline):
            def impl(self):
                self.core_id >> tx_deq
                tx_deq.out[0] >> Display()

        nic_rx('nic_rx', device=target.CAVIUM, cores=[1])
        nic_tx('nic_tx', device=target.CAVIUM, cores=[0])
        run('run', process='app', cores=range(n_queues))


c = Compiler(main)
c.generate_code_as_header()
c.depend = ['app']
c.compile_and_run("test_queue")
