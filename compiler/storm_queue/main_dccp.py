import queue2
import net2
import library_dsl2
from dsl2 import *
from compiler import Compiler

test = "spout"
inject_func = "random_" + test
workerid = {"spout": 0, "count": 1, "rank": 2}

n_cores = 5
n_workers = 4

# TODO: change this to DPDK
# from_net = net2.from_net_fixed_size_instance("tuple", "struct tuple", n_workers, 8192, "workers[atoi(argv[1])].port")
# to_nets = []
# for i in range(n_workers):
#     to_net = net2.to_net_fixed_size_instance("tuple" + str(i), "struct tuple",
#                                              "workers[%d].hostname" % i, "workers[%d].port" % i, output=True)
#     to_nets.append(to_net)

from_net = dpdk.from_net("struct pkt_dccp_headers")
to_net = dpdk.to_net()


class TaskMaster(State):
    task2executorid = Field(Pointer(Int))
    task2worker = Field(Pointer(Int))

    def init(self):
        self.task2executorid = "get_task2executorid()"
        self.task2worker = "get_task2worker()"

task_master = TaskMaster('task_master')


class GetCore(Element):
    this = Persistent(TaskMaster)
    def states(self, task_master): self.this = task_master

    def configure(self):
        self.inp = Input("struct tuple*")
        self.out = Output("struct tuple*", Size)

    def impl(self):
        self.run_c(r'''
    struct tuple* t = inp();
    int id = this->task2executorid[t->task];
    printf("receive: task %d, id %d\n", t->task, id);
    output { out(t, id); }
        ''')

get_core = GetCore(states=[task_master])
get_core2 = GetCore(states=[task_master])


class Choose(Element):
    this = Persistent(TaskMaster)
    def states(self, task_master): self.this = task_master

    def configure(self):
        self.inp = Input("struct tuple*")
        self.out_send = Output("struct tuple*")
        self.out_local = Output("struct tuple*")
        #self.out_nop = Output()

    def impl(self):
        self.run_c(r'''
    struct tuple* t = inp();
    bool local;
    if(t != NULL) {
        local = (this->task2worker[t->task] == this->task2worker[t->fromtask]);
        if(local) printf("send to myself!\n");
    }
    output switch { case (t && local): out_local(t); case (t && !local): out_send(t); } // else: out_nop(); }
        ''')

choose = Choose(states=[task_master])


class PrintTuple(Element):
    def configure(self):
        self.inp = Input("struct tuple*")
        self.out = Output("struct tuple*")

    def impl(self):
        self.run_c(r'''
    (struct tuple* t) = inp();

    //printf("TUPLE = null\n");
    if(t != NULL) {
        printf("TUPLE[0] -- task = %d, fromtask = %d, str = %s, integer = %d\n", t->task, t->fromtask, t->v[0].str, t->v[0].integer);
        //printf("TUPLE[1] -- task = %d, fromtask = %d, str = %s, integer = %d\n", t->task, t->fromtask, t->v[1].str, t->v[1].integer);
        fflush(stdout);
    }
    output { out(t); }
        ''')

print_tuple = PrintTuple()


class SteerWorker(Element):
    this = Persistent(TaskMaster)
    def states(self, task_master): self.this = task_master

    def configure(self):
        self.inp = Input("struct tuple*")
        self.out = [Output("struct tuple*") for i in range(n_workers)]
        #self.out_nop = Output()

    def impl(self):
        src = ""
        for i in range(n_workers):
            src += "case (id == {0}): out{0}(t); ".format(i)
        self.run_c(r'''
    (struct tuple* t) = inp();
    int id = -1;
    if(t != NULL) {
        id = this->task2worker[t->task];
        printf("send to worker %d\n", id);
    }
    output switch { ''' + src + "}") # else: out_nop(); }")


steer_worker = SteerWorker(states=[task_master])


############################### DCCP #################################
class DccpInfo(State):
    header = Field("struct pkt_dccp_headers")
    connections = Field(Array("struct connection", n_workers))
    retrans_timeout = Field(Uint(64))
    link_rtt = Field(Uint(64))
    global_lock = Field("rte_spinlock_t")

    def init(self):
        self.header = lambda(x): "init_header_template(&{0})".format(x)
        self.connections = lambda(x): "init_congestion_control({0})".format(x)
        self.retrans_timeout = "LINK_RTT"
        self.link_rtt = "LINK_RTT"
        self.global_lock = "RTE_SPINLOCK_INITIALIZER"

dccp_info = DccpInfo()


class DccpCheckCongestion(Element):
    dccp = Persistent(DccpInfo)

    def states(self):
        self.dccp = dccp_info

    def configure(self):
        self.inp = Input("void*", Int)
        self.out = Output("void*", Int)

    def impl(self):
        self.run_c(r'''
        (struct void* t, int worker) = inp();

        if(rdtsc() >= dccp->retrans_timeout) {
            dccp->connections[worker].pipe = 0;
            __sync_fetch_and_add(&dccp->link_rtt, dccp->link_rtt);
        }
        if(dccp->connections[worker].pipe <= dccp->connections[worker].cwnd) t = NULL;

        output switch { case t: out(t, worker); }
        ''')


class DccpSeqTime(Element):
    dccp = Persistent(DccpInfo)

    def states(self):
        self.dccp = dccp_info

    def configure(self):
        self.inp = Input("struct pkt_dccp_headers*", Int)
        self.out = Output("struct pkt_dccp_headers*")

    def impl(self):
        self.run_c(r'''
        (struct pkt_dccp_headers* header, int worker) = inp();
        rte_spinlock_lock(&dccp->global_lock);
        dccp->retrans_timeout = rdtsc() + link_rtt * PROC_FREQ_MHZ;
        dccp->link_rtt = LINK_RTT;
        uint32_t seq = __sync_fetch_and_add(&dccp->connections[worker].seq, 1);
        header->dccp.seq_high = seq >> 16;
        header->dccp.seq_low = htons(seq & 0xffff);
        /* printf("seq = %x, seq_high = %x, seq_low = %x\n", seq, header->dccp.seq_high, header->dccp.seq_low); */
        /* printf("%s: Sending to worker %d, task %d\n", progname, worker, i); */
        rte_spinlock_unlock(&dccp->global_lock);

        __sync_fetch_and_add(&dccp->connections[worker].pipe, 1);
        output { out(header); }
        ''')


class DccpSendAck(Element):
    dccp = Persistent(DccpInfo)

    def states(self):
        self.dccp = dccp_info

    def configure(self):
        self.inp = Input("struct pkt_dccp_headers*")
        self.out = Output("struct pkt_dccp_ack_headers *")

    def impl(self):  # TODO: reserve pkt buffer instead of malloc
        self.run_c(r'''
        (struct pkt_dccp_headers* p) = inp();
        struct pkt_dccp_ack_headers *ack = (struct pkt_dccp_ack_headers *) malloc(sizeof(struct pkt_dccp_ack_headers));
        memcpy(ack, &dccp->header, sizeof(struct pkt_dccp_headers));
        ack->eth.dest = p->eth.src;
        ack->dccp.hdr.src = p->dccp.dst;
        ack->dccp.hdr.res_type_x = DCCP_TYPE_ACK << 1;
        uint32_t seq = (p->dccp.seq_high << 16) | ntohs(p->dccp.seq_low);
        ack->dccp.ack = htonl(seq);
        ack->dccp.hdr.data_offset = 4;

        output { out(ack); }
        ''')

class DccpRecvAck(Element):
    dccp = Persistent(DccpInfo)

    def configure(self):
        self.inp = Input("struct pkt_dccp_headers*")

    def impl(self):
        self.run_c(r'''
        (struct pkt_dccp_headers* p) = inp();
        struct pkt_dccp_ack_headers *ack = (void *)p;
        int srcworker = ntohs(p->dccp.src);
        assert(srcworker < MAX_WORKERS);
        assert(ntohl(ack->dccp.ack) < (1 << 24));

        struct connections* = dccp->connections;

    // Wraparound?
	if((int32_t)ntohl(ack->dccp.ack) < connections[srcworker].lastack &&
	   connections[srcworker].lastack - (int32_t)ntohl(ack->dccp.ack) > connections[srcworker].pipe &&
	   connections[srcworker].lastack > (1 << 23)) {
	  connections[srcworker].lastack = -((1 << 24) - connections[srcworker].lastack);
	}

	if(connections[srcworker].lastack < (int32_t)ntohl(ack->dccp.ack)) {
	  int32_t oldpipe = __sync_sub_and_fetch(&connections[srcworker].pipe,
						 (int32_t)ntohl(ack->dccp.ack) - connections[srcworker].lastack);
	  if(oldpipe < 0) {
	    connections[srcworker].pipe = 0;
	  }

	  // Reset RTO
	  dccp->retrans_timeout = rdtsc() + dccp->link_rtt * PROC_FREQ_MHZ;
	  dccp->link_rtt = LINK_RTT;
	}

	if((int32_t)ntohl(ack->dccp.ack) > connections[srcworker].lastack + 1) {
	  /* printf("Congestion event for %d! ack %u, lastack + 1 = %u\n", */
	  /* 	 srcworker, ntohl(ack->dccp.ack), */
	  /* 	 connections[srcworker].lastack + 1); */
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
	  /* printf("Increasing congestion window for %d\n", srcworker); */
	  // Increase congestion window
	  /* __sync_fetch_and_add(&connections[srcworker].cwnd, 1); */
	  connections[srcworker].cwnd++;
	}

	connections[srcworker].lastack = MAX(connections[srcworker].lastack, (int32_t)ntohl(ack->dccp.ack));
	connections[srcworker].acks++;
        ''')

################################################

class GetWorkerID(Element):
    this = Persistent(TaskMaster)

    def states(self):
        self.this = task_master

    def configure(self):
        self.inp = Input("struct tuple*")
        self.out = Output("void*", Int)

    def impl(self):
        self.run_c(r'''
        (struct tuple* t) = inp();
        output { out(t, this->task2worker[t->task]); }
        ''')

class Tuple2Pkt(Element):    # TODO: reserve pkt buffer instead of malloc
    dccp = Persistent(DccpInfo)

    def states(self):
        self.dccp = dccp_info

    def configure(self):
        self.inp = Input("void*", Int)
        self.out = Output("struct pkt_dccp_headers*", Int)

    def impl(self):
        self.run_c(r'''
        (void* t, worker) = inp();
        struct pkt_dccp_headers *header = (struct pkt_dccp_headers *) malloc(sizeof(struct pkt_dccp_headers) + sizeof(struct tuple));
        memcpy(header, &dccp->header, sizeof(struct pkt_dccp_headers));
        memcpy(&header[1], t, sizeof(struct tuple));

        header->dccp.dst = htons(worker);
        header->eth.dest = workers[worker].mac;

        output { out(header, worker); }
        ''')


class Pkt2Tuple(Element):
    def configure(self):
        self.inp = Input("struct pkt_dccp_headers*")
        self.out = Output("struct tuple*")

    def impl(self):
        self.run_c(r'''
        (struct pkt_dccp_headers* p) = inp();
        output { out((struct tuple*) &p[1]); }
        ''')


class Classifier(Element):
    def configure(self):
        self.inp = Input("struct pkt_dccp_headers*")
        self.pkt = Output("struct pkt_dccp_headers*")
        self.ack = Output("struct pkt_dccp_ack_headers*")

    def impl(self):
        self.run_c(r'''
        (struct pkt_dccp_headers* p) = inp();
        int type = 0;
        if (ntohs(p->eth.type) == ETHTYPE_IP && p->ip._proto == IP_PROTO_DCCP) {
            if(((p->dccp.res_type_x >> 1) & 15) == DCCP_TYPE_ACK) type = 1;
            else type = 2;
        }
        output switch {
            case type==1: ack((struct pkt_dccp_ack_headers*) p);
            case type==2: pkt(p);
        }
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

queue_schedule = BatchScheduler(states=[batch_info])
batch_inc = BatchInc(states=[batch_info])

MAX_ELEMS = (4 * 1024)

rx_enq_creator, rx_deq_creator, rx_release_creator, scan = \
    queue2.queue_custom_owner_bit("rx_queue", "struct tuple", MAX_ELEMS, n_cores, "task", blocking=True,
                                  enq_output=True)

tx_enq_creator, tx_deq_creator, tx_release_creator, scan = \
    queue2.queue_custom_owner_bit("tx_queue", "struct tuple", MAX_ELEMS, n_cores, "task", blocking=False)

class nic_rx(InternalLoop):
    def configure(self): self.process = 'flexstorm'

    def spec(self):
        # TODO: without DCCP
        pass

    def impl(self):
        # TODO: from_net -> network_free
        # TODO: network_buf_alloc -> to_net
        classifier = Classifier()
        from_net >> classifier

        classifier.pkt >> Pkt2Tuple() >> get_core >> rx_enq_creator() >> library_dsl2.Drop(configure=["struct tuple*"])
        classifier.pkt >> DccpSendAck() >> to_net

        classifier.ack >> DccpRecvAck()

class inqueue_get(API):
    def configure(self):
        self.process = 'flexstorm'
        self.inp = Input(Size)
        self.out = Output("struct tuple*")

    def impl(self): self.inp >> rx_deq_creator() >> self.out

class inqueue_advance(API):
    def configure(self):
        self.process = 'flexstorm'
        self.inp = Input("struct tuple*")

    def impl(self): self.inp >> rx_release_creator()

class outqueue_put(API):
    def configure(self):
        self.process = 'flexstorm'
        self.inp = Input("struct tuple*", Size)

    def impl(self): self.inp >> tx_enq_creator()

class nic_tx(InternalLoop):
    def configure(self):
        self.process = 'flexstorm'

    def spec(self):
        # TODO: without DCCP
        pass

    # Cleaner version
    def impl(self):
        tx_deq = tx_deq_creator()
        tx_release = tx_release_creator()
        rx_enq = rx_enq_creator()
        get_worker_id = GetWorkerID()

        queue_schedule >> tx_deq >> print_tuple >> choose
        tx_deq >> batch_inc

        # send
        choose.out_send >> steer_worker
        for i in range(n_workers):
            steer_worker.out[i] >> get_worker_id
        get_worker_id >> DccpCheckCongestion() >> Tuple2Pkt() >> DccpSeqTime() >> to_net >> tx_release

        # local
        choose.out_local >> get_core2 >> rx_enq >> tx_release


nic_rx('nic_rx')
inqueue_get('inqueue_get')
inqueue_advance('inqueue_advance')  # TODO: signature change
outqueue_put('outqueue_put')
nic_tx('nic_tx')


c = Compiler()
c.include = r'''
#include <rte_memcpy.h>
#include "worker.h"
#include "storm.h"
#include "dccp.h"
#include "../net.h"
'''
c.depend = {"test_storm": ['list', 'hash', 'hash_table', 'spout', 'count', 'rank', 'worker', 'flexstorm']}
c.generate_code_as_header("flexstorm")
c.compile_and_run([("test_storm", workerid[test])])
