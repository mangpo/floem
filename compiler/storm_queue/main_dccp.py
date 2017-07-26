import queue2, net_real
from dsl2 import *
from compiler import Compiler

test = "spout"
inject_func = "random_" + test
workerid = {"spout": 0, "count": 1, "rank": 2}

n_cores = 7
n_workers = 2

class Classifier(Element):
    def configure(self):
        self.inp = Input(Size, "void*", "void*")
        self.pkt = Output("struct pkt_dccp_headers*")
        self.ack = Output("struct pkt_dccp_headers*")
        self.drop = Output()

    def impl(self):
        self.run_c(r'''
        (size_t size, void* hdr, void* b) = inp();
        struct pkt_dccp_headers* p = hdr;
        int type = 0;
        if (ntohs(p->eth.type) == ETHTYPE_IP && p->ip._proto == IP_PROTO_DCCP) {
            if(((p->dccp.res_type_x >> 1) & 15) == DCCP_TYPE_ACK) type = 1;
            else type = 2;
            state.rx_pkt = p;
            state.rx_net_buf = b;
        }
        output switch {
            case type==1: ack(p);
            case type==2: pkt(p);
            else: drop();
        }
        ''')

class Save(Element):
    def configure(self):
        self.inp = Input(Size, 'void*', 'void*')
        self.out = Output("struct pkt_dccp_headers*")

    def impl(self):
        self.run_c(r'''
        (size_t size, void* p, void* b) = inp();
        state.rx_pkt = p;
        state.rx_net_buf = b;
        output { out(p); }
        ''')


class TaskMaster(State):
    task2executorid = Field(Pointer(Int))
    task2worker = Field(Pointer(Int))

    def init(self):
        self.task2executorid = "get_task2executorid()"
        self.task2worker = "get_task2worker()"

task_master = TaskMaster('task_master')


class GetCore(Element):
    this = Persistent(TaskMaster)
    def states(self): self.this = task_master

    def configure(self):
        self.inp = Input("struct tuple*")
        self.out = Output("struct tuple*", Size)

    def impl(self):
        self.run_c(r'''
    struct tuple* t = inp();
    int id = this->task2executorid[t->task];
#ifdef DEBUG_MP
    printf("\nreceive: task %d, id %d\n", t->task, id);
#endif
    output { out(t, id); }
        ''')


class LocalOrRemote(Element):
    this = Persistent(TaskMaster)
    def states(self): self.this = task_master

    def configure(self):
        self.inp = Input("struct tuple*")
        self.out_send = Output("struct tuple*")
        self.out_local = Output("struct tuple*")

    def impl(self):
        self.run_c(r'''
    (struct tuple* t) = inp();
    bool local;
    if(t != NULL) {
        local = (state.worker == state.myworker);
#ifdef DEBUG_MP
        if(local) printf("send to myself!\n");
#endif
    }
    output switch { case (t && local): out_local(t); case (t && !local): out_send(t, worker); }
        ''')


class PrintTuple(Element):
    def configure(self):
        self.inp = Input("struct tuple*")
        self.out = Output("struct tuple*")

    def impl(self):
        self.run_c(r'''
    (struct tuple* t) = inp();

#ifdef DEBUG_MP
    if(t != NULL) {
        printf("TUPLE[0] -- task = %d, fromtask = %d, str = %s, integer = %d\n", t->task, t->fromtask, t->v[0].str, t->v[0].integer);
        //printf("TUPLE[1] -- task = %d, fromtask = %d, str = %s, integer = %d\n", t->task, t->fromtask, t->v[1].str, t->v[1].integer);
        fflush(stdout);
    }
#endif
    output switch { case t: out(t); }
        ''')



############################### DCCP #################################
class DccpInfo(State):
    header = Field("struct pkt_dccp_headers")
    connections = Field(Array("struct connection", n_workers))
    retrans_timeout = Field(Uint(64))
    link_rtt = Field(Uint(64))
    global_lock = Field("rte_spinlock_t")
    acks_sent = Field(Size)
    tuples = Field(Size)

    def init(self):
        self.header = lambda(x): "init_header_template(&{0})".format(x)
        self.connections = lambda(x): "init_congestion_control({0})".format(x)
        self.retrans_timeout = "LINK_RTT"
        self.link_rtt = "LINK_RTT"
        self.global_lock = lambda(x): "rte_spinlock_init(&{0})".format(x)
        self.acks_sent = 0
        self.tuples = 0

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
        self.run_c(r'''
        (int worker) = inp();

        if(rdtsc() >= dccp->retrans_timeout) {
            dccp->connections[worker].pipe = 0;
            __sync_fetch_and_add(&dccp->link_rtt, dccp->link_rtt);
        }
        if(dccp->connections[worker].pipe >= dccp->connections[worker].cwnd)
            worker = -1;

        output switch { case (worker >= 0): send(worker); else: drop(); }
        ''')


class DccpSeqTime(Element):
    dccp = Persistent(DccpInfo)

    def states(self):
        self.dccp = dccp_info

    def configure(self):
        self.inp = Input("void*", Int)
        self.out = Output("void*")

    def impl(self):
        self.run_c(r'''
        (void* p, int worker) = inp();
        struct pkt_dccp_headers* header = p;
        rte_spinlock_lock(&dccp->global_lock);
        dccp->retrans_timeout = rdtsc() + dccp->link_rtt * PROC_FREQ_MHZ;
        dccp->link_rtt = LINK_RTT;
        uint32_t seq = __sync_fetch_and_add(&dccp->connections[worker].seq, 1);
        header->dccp.seq_high = seq >> 16;
        header->dccp.seq_low = htons(seq & 0xffff);
#ifdef DEBUG_DCCP
        printf("Send to worker %d: seq = %x, seq_high = %x, seq_low = %x\n", worker, seq, header->dccp.seq_high, header->dccp.seq_low);
#endif
        rte_spinlock_unlock(&dccp->global_lock);

        __sync_fetch_and_add(&dccp->connections[worker].pipe, 1);
        output { out(p); }
        ''')


class DccpSendAck(Element):  # TODO
    dccp = Persistent(DccpInfo)

    def states(self):
        self.dccp = dccp_info

    def configure(self):
        self.inp = Input("struct pkt_dccp_ack_headers *", "struct pkt_dccp_headers*")
        self.out = Output("void *")

    def impl(self):
        self.run_c(r'''
        (struct pkt_dccp_ack_headers* ack, struct pkt_dccp_headers* p) = inp();
        memcpy(ack, &dccp->header, sizeof(struct pkt_dccp_headers));
        ack->eth.dest = p->eth.src;
        ack->dccp.hdr.src = p->dccp.dst;
        ack->dccp.hdr.res_type_x = DCCP_TYPE_ACK << 1;
        uint32_t seq = (p->dccp.seq_high << 16) | ntohs(p->dccp.seq_low);
        ack->dccp.ack = htonl(seq);
        ack->dccp.hdr.data_offset = 4;

        dccp->acks_sent++;
        __sync_synchronize();

        output { out(ack); }
        ''')

class DccpRecvAck(Element):
    dccp = Persistent(DccpInfo)

    def configure(self):
        self.inp = Input("struct pkt_dccp_headers*")
        self.out = Output("struct pkt_dccp_headers*")
        self.dccp = dccp_info

    def impl(self):
        self.run_c(r'''
        (struct pkt_dccp_headers* p) = inp();
        struct pkt_dccp_ack_headers *ack = (void *)p;
        int srcworker = ntohs(p->dccp.src);
        assert(srcworker < MAX_WORKERS);
        assert(ntohl(ack->dccp.ack) < (1 << 24));

        struct connection* connections = dccp->connections;

    // Wraparound?
	if((int32_t)ntohl(ack->dccp.ack) < connections[srcworker].lastack &&
	   connections[srcworker].lastack - (int32_t)ntohl(ack->dccp.ack) > connections[srcworker].pipe &&
	   connections[srcworker].lastack > (1 << 23)) {
	  connections[srcworker].lastack = -((1 << 24) - connections[srcworker].lastack);
	}

	if(connections[srcworker].lastack < (int32_t)ntohl(ack->dccp.ack)) {
	  int32_t oldpipe = __sync_sub_and_fetch(&connections[srcworker].pipe,
						 (int)ntohl(ack->dccp.ack) - connections[srcworker].lastack);
	  if(oldpipe < 0) {
	    connections[srcworker].pipe = 0;
	  }

	  // Reset RTO
	  dccp->retrans_timeout = rdtsc() + dccp->link_rtt * PROC_FREQ_MHZ;
	  dccp->link_rtt = LINK_RTT;
	}

	if((int32_t)ntohl(ack->dccp.ack) > connections[srcworker].lastack + 1) {
#if 1
	  printf("Congestion event for %d! ack %u, lastack + 1 = %u\n",
	 	 srcworker, ntohl(ack->dccp.ack),
	 	 connections[srcworker].lastack + 1);
#endif
	  // Congestion event! Shrink congestion window
	  uint32_t oldcwnd = connections[srcworker].cwnd, newcwnd;
	  do {
	    newcwnd = oldcwnd;
	    if(oldcwnd >= 2) {
	      newcwnd = __sync_val_compare_and_swap(&connections[srcworker].cwnd, oldcwnd, oldcwnd / 2);
	    } else {
	      break;
	    }
	  } while(oldcwnd != newcwnd);
	} else {
#ifdef DEBUG_DCCP
	  printf("Increasing congestion window for %d\n", srcworker);
#endif
	  // Increase congestion window
	  /* __sync_fetch_and_add(&connections[srcworker].cwnd, 1); */
	  connections[srcworker].cwnd++;
	}

	connections[srcworker].lastack = MAX(connections[srcworker].lastack, (int32_t)ntohl(ack->dccp.ack));
	connections[srcworker].acks++;
	output { out(p); }
        ''')

################################################

class SaveWorkerID(Element):
    this = Persistent(TaskMaster)

    def states(self):
        self.this = task_master

    def configure(self):
        self.inp = Input("struct tuple*")
        self.out = Output("struct tuple*")

    def impl(self):
        self.run_c(r'''
        (struct tuple* t) = inp();
        state.worker = this->task2worker[t->task];
        state.myworker = this->task2worker[t->fromtask];
        output { out(t); }
        ''')

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
        self.run_c(r'''
        (void* p) = inp();
        output { out(p, state.worker); }
        ''')


class Tuple2Pkt(Element):
    dccp = Persistent(DccpInfo)

    def states(self):
        self.dccp = dccp_info

    def configure(self):
        self.inp = Input(Size, "void*", "void*")
        self.out = Output("void*")

    def impl(self):
        self.run_c(r'''
        (size_t size, void* p, void* b) = inp();
        struct pkt_dccp_headers* header = p;
        state.tx_net_buf = b;
        struct tuple* t = state.q_buf.entry;
        memcpy(header, &dccp->header, sizeof(struct pkt_dccp_headers));
        memcpy(&header[1], t, sizeof(struct tuple));

        header->dccp.dst = htons(state.worker);
        header->dccp.src = htons(state.myworker);
        header->eth.dest = workers[state.worker].mac;
        header->eth.src = workers[state.myworker].mac;
        
        //printf("PREPARE PKT: task = %d, worker = %d\n", t->task, state.worker);
        output { out(p); }
        ''')


class Pkt2Tuple(Element):
    dccp = Persistent(DccpInfo)

    def states(self): self.dccp = dccp_info

    def configure(self):
        self.inp = Input("struct pkt_dccp_headers*")
        self.out = Output("struct tuple*")

    def impl(self):
        self.run_c(r'''
        (struct pkt_dccp_headers* p) = inp();
        struct tuple* t= (struct tuple*) &p[1];
        __sync_fetch_and_add(&dccp->tuples, 1);
        output { out(t); }
        ''')


class SizePkt(Element):
    def configure(self, len):
        self.inp = Input()
        self.out = Output(Size)
        self.len = len

    def impl(self):
        self.run_c(r'''
        output { out(%s); }
        ''' % self.len)

class GetBothPkts(Element):
    def configure(self):
        self.inp = Input(Size, "void*", "void*")
        self.out = Output("struct pkt_dccp_ack_headers*", "struct pkt_dccp_headers*")

    def impl(self):
        self.run_c(r'''
        (size_t size, void* tx_pkt, void* tx_buf) = inp();
        state.tx_net_buf = tx_buf;
        void* rx_pkt = state.rx_pkt;
        output { out(tx_pkt, rx_pkt); }
        ''')

class GetTxBuf(Element):
    def configure(self, len):
        self.inp = Input("void *")
        self.out = Output(Size, "void *", "void *")
        self.len = len

    def impl(self):
        self.run_c(r'''
        (void* p) = inp();
        void* net_buf = state.tx_net_buf;
        output { out(%s, p, net_buf); }
        ''' % self.len)

class GetRxBuf(Element):
    def configure(self):
        self.inp = Input()
        self.out = Output("void *", "void *")

    def impl(self):
        self.run_c(r'''
        void* pkt = state.rx_pkt;
        void* pkt_buf = state.rx_net_buf;
        output { out(pkt, pkt_buf); }
        ''')


############################### Queue #################################
class BatchInfo(State):
    core = Field(Int)
    batch_size = Field(Int)
    start = Field(Uint(64))

    def init(self):
        self.core = 0
        self.batch_size = 0
        self.start = 0

batch_info = BatchInfo()

class BatchScheduler(Element):
    this = Persistent(BatchInfo)
    def states(self, batch_info): self.this = batch_info

    def configure(self):
        self.out = Output(Size)

    def impl(self):
        self.run_c(r'''
    if(this->batch_size >= BATCH_SIZE || rdtsc() - this->start >= BATCH_DELAY) {
        this->core = (this->core + 1) %s %d;
        this->batch_size = 0;
        this->start = rdtsc();
    }
    output { out(this->core); }
        ''' % ('%', n_cores))

class BatchInc(Element):
    this = Persistent(BatchInfo)

    def states(self, batch_info): self.this = batch_info

    def configure(self):
        self.inp = Input("struct tuple*")
        #self.out = Output("struct tuple*")

    def impl(self):
        self.run_c(r'''
        (struct tuple* t) = inp();
        if(t) this->batch_size++;
        // output switch { case t: out(t); };
        ''')

################## Queue addr ####################
class DropAddr(Element):
    def configure(self):
        self.inp = Input("struct tuple*", "uintptr_t")
        self.out = Output("struct tuple*")

    def impl(self):
        self.run_c(r'''
    (struct tuple* t, uintptr_t addr) = inp();
    output { out(t); }
        ''')

class AddNullAddr(Element):
    def configure(self):
        self.inp = Input("struct tuple*")
        self.out = Output("struct tuple*", "uintptr_t")

    def impl(self):
        self.run_c(r'''
    (struct tuple* t) = inp();
    output { out(t, 0); }
        ''')

class SaveBuff(Element):
    def configure(self):
        self.inp = Input(queue2.q_buffer)
        self.out = Output("struct tuple*")

    def impl(self):
        self.run_c(r'''
    (q_buffer buff) = inp();
    state.q_buf = buff;
    output { out((struct tuple*) buff.entry); }
        ''')

class GetBuff(Element):
    def configure(self):
        self.inp = Input()
        self.out = Output(queue2.q_buffer)

    def impl(self):
        self.run_c(r'''
    q_buffer buff = state.q_buf;
    output { out(buff); }
        ''')

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
    queue2.queue_custom_owner_bit("rx_queue", "struct tuple", MAX_ELEMS, n_cores, "task",
                                  enq_atomic=True, deq_blocking=True, enq_output=True)

tx_enq_creator, tx_deq_creator, tx_release_creator = \
    queue2.queue_custom_owner_bit("tx_queue", "struct tuple", MAX_ELEMS, n_cores, "task")


class RxState(State):
    rx_pkt = Field("struct pkt_dccp_headers*")
    rx_net_buf = Field("void *")
    tx_net_buf = Field("void *")


class NicRxPipeline(Pipeline):
    state = PerPacket(RxState)

    def impl(self):
        from_net = net_real.FromNet()
        from_net_free = net_real.FromNetFree()
        class nic_rx(InternalLoop):

            def impl_basic(self):
                # Notice that it's okay to connect non-empty port to an empty port.
                rx_enq = rx_enq_creator()
                from_net >> Save() >> Pkt2Tuple() >> GetCore() >> rx_enq >> GetRxBuf() >> from_net_free
                from_net.nothing >> Drop()

            def impl(self):
                network_alloc = net_real.NetAlloc()
                to_net = net_real.ToNet(configure=["alloc", True])
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
                network_alloc.oom >> rx_buf
                rx_buf >> from_net_free

        nic_rx('nic_rx', process='dpdk')
        #nic_rx('nic_rx', device=target.CAVIUM, cores=[0,1,2,3])


class inqueue_get(API):
    def configure(self):
        self.inp = Input(Size)
        self.out = Output(queue2.q_buffer)

    def impl(self): self.inp >> rx_deq_creator() >> self.out


class inqueue_advance(API):
    def configure(self):
        self.inp = Input(queue2.q_buffer)

    def impl(self): self.inp >> rx_release_creator()


class outqueue_put(API):
    def configure(self):
        self.inp = Input("struct tuple*", Size)

    def impl(self): self.inp >> tx_enq_creator()

class get_dccp_stat(API):
    def configure(self):
        self.inp = Input()
        self.out = Output(Pointer(DccpInfo))

    def impl(self): self.inp >> DccpGetStat() >> self.out

class TxState(State):
    worker = Field(Int)
    myworker = Field(Int)
    tx_net_buf = Field("void *")
    q_buf = Field(queue2.q_buffer)

class NicTxPipeline(Pipeline):
    state = PerPacket(TxState)

    def impl(self):
        tx_release = tx_release_creator()
        network_alloc = net_real.NetAlloc()
        to_net = net_real.ToNet(configure=["alloc", True])

        tx_buf = GetTxBuf(configure=['sizeof(struct pkt_dccp_headers) + sizeof(struct tuple)'])
        size_pkt = SizePkt(configure=['sizeof(struct pkt_dccp_headers) + sizeof(struct tuple)'])

        queue_schedule = BatchScheduler(states=[batch_info])
        batch_inc = BatchInc(states=[batch_info])

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

                dccp_check.send >> size_pkt >> network_alloc >> tuple2pkt >> GetWorkerIDPkt() >> DccpSeqTime() \
                >> tx_buf >> to_net

                dccp_check.drop >> nop
                network_alloc.oom >> nop
                tuple2pkt >> nop
                nop >> self.out


        class nic_tx(InternalLoop):
            def impl(self):
                tx_deq = tx_deq_creator()
                rx_enq = rx_enq_creator()
                local_or_remote = LocalOrRemote()
                save_buff = SaveBuff()
                get_buff = GetBuff()

                queue_schedule >> tx_deq >> save_buff >> PrintTuple() >> SaveWorkerID() >> local_or_remote
                save_buff >> batch_inc
                # send
                local_or_remote.out_send >> PreparePkt() >> get_buff
                # local
                local_or_remote.out_local >> GetCore() >> rx_enq >> get_buff

                get_buff >> tx_release

        nic_tx('nic_tx', process='dpdk')
        # nic_tx('nic_tx', device=target.CAVIUM, cores=[4,5,6,7])


inqueue_get('inqueue_get', process='dpdk')
inqueue_advance('inqueue_advance', process='dpdk')
outqueue_put('outqueue_put', process='dpdk')
get_dccp_stat('get_dccp_stat', process='dpdk')


c = Compiler(NicRxPipeline, NicTxPipeline)
c.include = r'''
#include <rte_memcpy.h>
#include "worker.h"
#include "storm.h"
#include "dccp.h"
'''
c.depend = {"test_storm": ['list', 'hash', 'hash_table', 'spout', 'count', 'rank', 'worker', 'dpdk']}
c.generate_code_as_header("dpdk")
c.compile_and_run([("test_storm", workerid[test])])

