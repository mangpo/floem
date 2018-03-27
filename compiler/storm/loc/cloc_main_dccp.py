import queue, net
from dsl import *
from compiler import Compiler

test = "spout"
workerid = {"spout": 0, "count": 1, "rank": 2}

n_cores = 4 #7
n_workers = 'MAX_WORKERS'
n_nic_rx = 2
n_nic_tx = 3

class Classifier(Element):
    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.pkt = Output("struct pkt_dccp_headers*")
        self.ack = Output("struct pkt_dccp_headers*")
        self.drop = Output()

    def impl(self):
        self.run_c(r'''''')

class Save(Element):
    def configure(self):
        self.inp = Input(SizeT, 'void*', 'void*')
        self.out = Output("struct pkt_dccp_headers*")

    def impl(self):
        self.run_c(r'''''')


class TaskMaster(State):
    task2executorid = Field(Pointer(Int))
    task2worker = Field(Pointer(Int))
    executors = Field('struct executor*')

    def init(self):
        self.task2executorid = "get_task2executorid()"
        self.task2worker = "get_task2worker()"
        self.executors = "get_executors()"

task_master = TaskMaster('task_master')


class GetCore(Element):
    this = Persistent(TaskMaster)
    def states(self): self.this = task_master

    def configure(self):
        self.inp = Input("struct tuple*")
        self.out = Output("struct tuple*", Int)

    def impl(self):
        self.run_c(r'''''')

class LocalOrRemote(Element):
    this = Persistent(TaskMaster)
    def states(self): self.this = task_master

    def configure(self):
        self.inp = Input("struct tuple*")
        self.out_send = Output("struct tuple*")
        self.out_local = Output("struct tuple*")

    def impl(self):
        self.run_c(r'''''')


class PrintTuple(Element):
    def configure(self):
        self.inp = Input("struct tuple*")
        self.out = Output("struct tuple*")

    def impl(self):
        self.run_c(r'''''')



############################### DCCP #################################
class DccpInfo(State):
    header = Field("struct pkt_dccp_headers")
    connections = Field(Array("struct connection", n_workers))
    retrans_timeout = Field(Uint(64))
    link_rtt = Field(Uint(64))
    global_lock = Field("rte_spinlock_t")
    acks_sent = Field(SizeT)
    tuples = Field(SizeT)

    def init(self):
        self.header = lambda(x): "init_header_template(&{0})".format(x)
        self.connections = lambda(x): "init_congestion_control({0})".format(x)
        self.retrans_timeout = "LINK_RTT"
        self.link_rtt = "LINK_RTT"
        self.global_lock = lambda(x): "rte_spinlock_init(&{0})".format(x)
        self.acks_sent = 0
        self.tuples = 0

        self.packed = False

dccp_info = DccpInfo()

class DccpGetStat(Element):
    dccp = Persistent(DccpInfo)

    def states(self):
        self.dccp = dccp_info

    def configure(self):
        self.inp = Input()
        self.out = Output(Pointer(DccpInfo))

    def impl(self):
        self.run_c(r'''
        output { out(dccp); }''')


class DccpCheckCongestion(Element):
    dccp = Persistent(DccpInfo)

    def states(self):
        self.dccp = dccp_info

    def configure(self):
        self.inp = Input(Int)
        self.send = Output(Int)
        self.drop = Output()

    def impl(self):
        self.run_c(r'''''')


class DccpSeqTime(Element):
    dccp = Persistent(DccpInfo)

    def states(self):
        self.dccp = dccp_info

    def configure(self):
        self.inp = Input("void*", Int)
        self.out = Output("void*")

    def impl(self):
        self.run_c(r'''''')


class DccpSendAck(Element):  # TODO
    dccp = Persistent(DccpInfo)

    def states(self):
        self.dccp = dccp_info

    def configure(self):
        self.inp = Input("struct pkt_dccp_ack_headers *", "struct pkt_dccp_headers*")
        self.out = Output("void *")

    def impl(self):
        self.run_c(r'''''')

class DccpRecvAck(Element):
    dccp = Persistent(DccpInfo)

    def configure(self):
        self.inp = Input("struct pkt_dccp_headers*")
        self.out = Output("struct pkt_dccp_headers*")
        self.dccp = dccp_info

    def impl(self):
        self.run_c(r'''''')

class CountTuple(Element):
    dccp = Persistent(DccpInfo)
    def states(self): self.dccp = dccp_info

    def configure(self):
        self.inp = Input("struct tuple*")
        self.out = Output("struct tuple*")

    def impl(self):
        self.run_c(r'''''')

class CountPacket(Element):
    dccp = Persistent(DccpInfo)
    def states(self): self.dccp = dccp_info

    def configure(self):
        self.inp = Input("void*")
        self.out = Output("void*")

    def impl(self):
        self.run_c(r'''''')



################################################

class SaveWorkerID(Element):
    this = Persistent(TaskMaster)

    def states(self):
        self.this = task_master

    def configure(self):
        self.inp = Input("struct tuple*")
        self.out = Output("struct tuple*")

    def impl(self):
        self.run_c(r'''''')

class GetWorkerID(Element):
    def configure(self):
        self.inp = Input()
        self.out = Output(Int)

    def impl(self):
        self.run_c(r'''output { out(state.worker); }''')

class GetWorkerIDPkt(Element):
    def configure(self):
        self.inp = Input("void*")
        self.out = Output("void*", Int)

    def impl(self):
        self.run_c(r'''''')


class Tuple2Pkt(Element):
    dccp = Persistent(DccpInfo)

    def states(self):
        self.dccp = dccp_info

    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.out = Output("void*")

    def impl(self):
        self.run_c(r'''''')


class Pkt2Tuple(Element):
    dccp = Persistent(DccpInfo)

    def states(self): self.dccp = dccp_info

    def configure(self):
        self.inp = Input("struct pkt_dccp_headers*")
        self.out = Output("struct tuple*")

    def impl(self):
        self.run_c(r'''''')


class SizePkt(Element):
    def configure(self, len):
        self.inp = Input()
        self.out = Output(SizeT)
        self.len = len

    def impl(self):
        self.run_c(r'''''' % self.len)

class GetBothPkts(Element):
    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.out = Output("struct pkt_dccp_ack_headers*", "struct pkt_dccp_headers*")

    def impl(self):
        self.run_c(r'''''')

class GetTxBuf(Element):
    def configure(self, len):
        self.inp = Input("void *")
        self.out = Output(SizeT, "void *", "void *")
        self.len = len

    def impl(self):
        self.run_c(r'''''' % self.len)

class GetRxBuf(Element):
    def configure(self):
        self.inp = Input()
        self.out = Output("void *", "void *")

    def impl(self):
        self.run_c(r'''''')


############################### Queue #################################
class BatchScheduler(Element):
    this = Persistent(TaskMaster)

    def states(self): self.this = task_master

    def configure(self):
        self.inp = Input(Int)
        self.out = Output(Int)

    def impl(self):
        self.run_c(r'''   ''' % (n_cores, n_nic_tx, '%', '%',))


class BatchInc(Element):
    def configure(self):
        self.inp = Input()

    def impl(self):
        self.run_c("")

################## Queue addr ####################
class DropAddr(Element):
    def configure(self):
        self.inp = Input("struct tuple*", "uintptr_t")
        self.out = Output("struct tuple*")

    def impl(self):
        self.run_c(r'''''')

class AddNullAddr(Element):
    def configure(self):
        self.inp = Input("struct tuple*")
        self.out = Output("struct tuple*", "uintptr_t")

    def impl(self):
        self.run_c(r'''''')

class SaveBuff(Element):
    def configure(self):
        self.inp = Input(queue.q_buffer)
        self.out = Output("struct tuple*")

    def impl(self):
        self.run_c(r'''''')

class GetBuff(Element):
    def configure(self):
        self.inp = Input()
        self.out = Output(queue.q_buffer)

    def impl(self):
        self.run_c(r'''''')

class Identity(ElementOneInOut):
    def impl(self):
        self.run_c(r'''output { out(); }''')

class Drop(Element):
    def configure(self):
        self.inp = Input()

    def impl(self):
        self.run_c("")

#################### Connection ####################
import target

MAX_ELEMS = (4 * 1024)

rx_enq_creator, rx_deq_creator, rx_release_creator = \
    queue.queue_custom("rx_queue", "struct tuple", MAX_ELEMS, n_cores, "status", enq_blocking=False,
                       deq_blocking=True, enq_atomic=True, enq_output=True)

tx_enq_creator, tx_deq_creator, tx_release_creator = \
    queue.queue_custom("tx_queue", "struct tuple", MAX_ELEMS, n_cores, "status", enq_blocking=True,
                       deq_atomic=False)


class RxState(State):
    rx_pkt = Field("struct pkt_dccp_headers*")
    rx_net_buf = Field("void *")
    tx_net_buf = Field("void *")


class NicRxFlow(Flow):
    state = PerPacket(RxState)

    def impl(self):
        from_net = net.FromNet(configure=[64])
        from_net_free = net.FromNetFree()
        class nic_rx(Pipeline):

            def impl_basic(self):
                # Notice that it's okay to connect non-empty port to an empty port.
                rx_enq = rx_enq_creator()
                from_net >> Save() >> Pkt2Tuple() >> GetCore() >> rx_enq >> GetRxBuf() >> from_net_free
                from_net.nothing >> Drop()

            def impl(self):
                network_alloc = net.NetAlloc()
                to_net = net.ToNet(configure=["alloc", 32])
                classifier = Classifier()
                rx_enq = rx_enq_creator()
                tx_buf = GetTxBuf(configure=['sizeof(struct pkt_dccp_ack_headers)'])
                size_ack = SizePkt(configure=['sizeof(struct pkt_dccp_ack_headers)'])
                rx_buf = GetRxBuf()

                from_net.nothing >> Drop()
                from_net >> classifier

                # CASE 1: not ack
                # send ack
                classifier.pkt >> size_ack >> network_alloc >> GetBothPkts() >> DccpSendAck() >> tx_buf >> to_net
                # process
                pkt2tuple = Pkt2Tuple()
                classifier.pkt >> pkt2tuple >> GetCore() >> rx_enq >> rx_buf

                # CASE 2: ack
                classifier.ack >> DccpRecvAck() >> rx_buf

                # Exception
                classifier.drop >> rx_buf
                network_alloc.oom >> Drop()
                rx_buf >> from_net_free

        nic_rx('nic_rx', process='dpdk', cores=range(n_nic_rx))
        #nic_rx('nic_rx', device=target.CAVIUM, cores=[0,1,2,3])


class inqueue_get(CallablePipeline):
    def configure(self):
        self.inp = Input(Int)
        self.out = Output(queue.q_buffer)

    def impl(self): self.inp >> rx_deq_creator() >> self.out


class inqueue_advance(CallablePipeline):
    def configure(self):
        self.inp = Input(queue.q_buffer)

    def impl(self): self.inp >> rx_release_creator()


class outqueue_put(CallablePipeline):
    def configure(self):
        self.inp = Input("struct tuple*", Int)

    def impl(self): self.inp >> tx_enq_creator()

class get_dccp_stat(CallablePipeline):
    def configure(self):
        self.inp = Input()
        self.out = Output(Pointer(DccpInfo))

    def impl(self): self.inp >> DccpGetStat() >> self.out

class TxState(State):
    worker = Field(Int)
    myworker = Field(Int)
    tx_net_buf = Field("void *")
    q_buf = Field(queue.q_buffer)

class NicTxFlow(Flow):
    state = PerPacket(TxState)

    def impl(self):
        tx_release = tx_release_creator()
        network_alloc = net.NetAlloc()
        to_net = net.ToNet(configure=["alloc", 32])

        tx_buf = GetTxBuf(configure=['sizeof(struct pkt_dccp_headers) + sizeof(struct tuple)'])
        size_pkt = SizePkt(configure=['sizeof(struct pkt_dccp_headers) + sizeof(struct tuple)'])

        queue_schedule = BatchScheduler()
        batch_inc = BatchInc()

        tuple2pkt = Tuple2Pkt()
        nop = Identity()

        class PreparePkt(Composite):
            def configure(self):
                self.inp = Input("struct tuple*")
                self.out = Output()

            def impl_basic(self):
                self.inp >> size_pkt >> network_alloc >> tuple2pkt >> tx_buf >> to_net

                network_alloc.oom >> nop
                tuple2pkt >> nop
                nop >> self.out

            def impl(self):
                dccp_check = DccpCheckCongestion()

                self.inp >> GetWorkerID() >> dccp_check

                dccp_check.send >> size_pkt >> network_alloc >> tuple2pkt >> CountPacket() >> GetWorkerIDPkt() >> DccpSeqTime() \
                >> tx_buf >> to_net

                dccp_check.drop >> nop
                network_alloc.oom >> nop
                tuple2pkt >> nop
                nop >> self.out


        class nic_tx(Pipeline):
            def impl(self):
                tx_deq = tx_deq_creator()
                rx_enq = rx_enq_creator()
                local_or_remote = LocalOrRemote()
                save_buff = SaveBuff()
                get_buff = GetBuff()

                self.core_id >> queue_schedule >> tx_deq >> save_buff >> PrintTuple() >> SaveWorkerID() >> local_or_remote
                save_buff >> batch_inc
                # send
                local_or_remote.out_send >> PreparePkt() >> get_buff
                # local
                local_or_remote.out_local >> GetCore() >> rx_enq >> get_buff #CountTuple() >> get_buff

                get_buff >> tx_release

        nic_tx('nic_tx', process='dpdk', cores=range(n_nic_tx))
        # nic_tx('nic_tx', device=target.CAVIUM, cores=[4,5,6,7])


inqueue_get('inqueue_get', process='dpdk')
inqueue_advance('inqueue_advance', process='dpdk')
outqueue_put('outqueue_put', process='dpdk')
get_dccp_stat('get_dccp_stat', process='dpdk')


c = Compiler(NicRxFlow, NicTxFlow)
c.include = r'''
#include <rte_memcpy.h>
#include "worker.h"
#include "storm.h"
#include "dccp.h"
'''
c.depend = {"test_storm": ['list', 'hash', 'hash_table', 'spout', 'count', 'rank', 'worker', 'dpdk']}
c.generate_code_as_header("dpdk")
c.compile_and_run([("test_storm", workerid[test])])

