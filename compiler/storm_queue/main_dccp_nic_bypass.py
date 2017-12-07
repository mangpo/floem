import queue, net_real
from dsl import *
from compiler import Compiler

nic = 'CAVIUM' #'dpdk'
test = "spout"
inject_func = "random_" + test
workerid = {"spout": 0, "count": 1, "rank": 2}

n_cores = 7
n_workers = 'MAX_WORKERS'
n_nic_rx = 3
n_nic_tx = 5

class DccpInfo(State):
    header = Field("struct pkt_dccp_headers")
    connections = Field(Array("struct connection", n_workers))
    retrans_timeout = Field(Uint(64))
    link_rtt = Field(Sint(64))
    global_lock = Field("spinlock_t")  # TODO: Cavium doesn't lock inside strct.
    acks_sent = Field(Sint(64))
    tuples = Field(Sint(64))

    def init(self):
        self.header = lambda(x): "init_header_template(&{0})".format(x)
        self.connections = lambda(x): "init_congestion_control({0})".format(x)
        self.retrans_timeout = "LINK_RTT"
        self.link_rtt = "LINK_RTT"
        self.global_lock = lambda(x): "spinlock_init(&{0})".format(x)
        self.acks_sent = 0
        self.tuples = 0

        self.packed = False

dccp_info = DccpInfo()

class CountTuple(Element):
    dccp = Persistent(DccpInfo)
    def states(self): self.dccp = dccp_info

    def configure(self):
        self.inp = Input("struct tuple*")
        self.out = Output("struct tuple*")

    def impl(self):
        self.run_c(r'''
        struct tuple *t = inp();
        if(t) __sync_fetch_and_add64(&dccp->tuples, 1);
        output { out(t); }''')

class CountPacket(Element):
    dccp = Persistent(DccpInfo)
    def states(self): self.dccp = dccp_info

    def configure(self):
        self.inp = Input("void*")
        self.out = Output("void*")

    def impl(self):
        self.run_c(r'''
        void *t = inp();
        if(t) __sync_fetch_and_add64(&dccp->tuples, 1);
        output { out(t); }''')


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
    executors = Field('struct executor*')

    def init(self):
        self.task2executorid = "get_task2executorid()"
        self.task2worker = "get_task2worker()"
        self.executors = "get_executors()"

task_master = TaskMaster('task_master')
task_master_cpu = TaskMaster('task_master_cpu')


class GetCore(Element):
    this = Persistent(TaskMaster)
    def states(self): self.this = task_master

    def configure(self):
        self.inp = Input("struct tuple*")
        self.out = Output("struct tuple*", Size)

    def impl(self):
        self.run_c(r'''
    struct tuple* t = inp();
    int id = this->task2executorid[nic_htonl(t->task)];
#ifdef DEBUG_MP
    printf("\nget_core: task %d, qid %d\n", nic_htonl(t->task), id);
#endif
    output { out(t, id); }
        ''')

class GetCoreCPU(Element):
    this = Persistent(TaskMaster)
    def states(self): self.this = task_master_cpu

    def configure(self):
        self.inp = Input("struct tuple*")
        self.out = Output("struct tuple*", Size)

    def impl(self):
        self.run_c(r'''
    struct tuple* t = inp();
    int id = this->task2executorid[nic_htonl(t->task)];
#ifdef DEBUG_MP
    printf("\nget_core: task %d, qid %d\n", nic_htonl(t->task), id);
#endif
    output { out(t, id); }
        ''')

class LocalOrRemote(Element):
    this = Persistent(TaskMaster)
    def states(self): self.this = task_master_cpu

    def configure(self):
        self.inp = Input("struct tuple*", Size)
        self.out_send = Output("struct tuple*", Size)
        self.out_local = Output("struct tuple*")

    def impl(self):
        self.run_c(r'''
    (struct tuple* t, size_t qid) = inp();
    int worker = this->task2worker[nic_htonl(t->task)];
    int myworker = this->task2worker[nic_htonl(t->fromtask)];
    bool local;
    local = (worker == myworker);
    if(local && nic_htonl(t->task) == 30) printf("30: send to myself!\n");
#ifdef DEBUG_MP
    //if(local) printf("send to myself!\n");
    //else printf("remote!\n");
#endif

    output switch { case local: out_local(t); else: out_send(t, qid); }
        ''')


class PrintTuple(Element):
    dccp = Persistent(DccpInfo)

    def configure(self):
        self.dccp = dccp_info
        self.inp = Input("struct tuple*")
        self.out = Output("struct tuple*")

    def impl(self):
        self.run_c(r'''
    (struct tuple* t) = inp();

#ifdef DEBUG_MP
  if(t) {
    uint32_t task = nic_htonl(t->task);
    if(task == 10 && strcmp(t->v[0].str, "golda")) {
      printf("print: task = %d, str = %s\n", task, t->v[0].str);
      assert(strcmp(t->v[0].str, "golda") == 0);
    }
    if(task == 11 && strcmp(t->v[0].str, "nathan")) {
      printf("print: task = %d, str = %s\n", task, t->v[0].str);
      assert(strcmp(t->v[0].str, "nathan") == 0);
    }
    if(task == 12 && strcmp(t->v[0].str, "jackson")) {
      printf("print: task = %d, str = %s\n", task, t->v[0].str);
      assert(strcmp(t->v[0].str, "jackson") == 0);
    }
    if(task == 13 && strcmp(t->v[0].str, "bertels")) {
      printf("print: task = %d, str = %s\n", task, t->v[0].str);
      assert(strcmp(t->v[0].str, "berterls") == 0);
    }
  }
#endif

#ifdef DEBUG_MP
    if(t != NULL) {
        printf("TUPLE[0] -- task = %d, fromtask = %d, str = %s, integer = %d\n", nic_htonl(t->task), nic_htonl(t->fromtask), t->v[0].str, t->v[0].integer);
        //printf("TUPLE[1] -- task = %d, fromtask = %d, str = %s, integer = %d\n", nic_htonl(t->task), nic_htonl(t->fromtask), t->v[1].str, t->v[1].integer);
        fflush(stdout);
    }
#endif
    output switch { case t: out(t); }
        ''')



############################### DCCP #################################

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


class DccpPrintStat(Element):
    info = Persistent(DccpInfo)

    def states(self):
        self.info = dccp_info

    def impl(self):
        self.run_c(r'''
#ifndef CAVIUM
        sleep(1);
#else
        __cvmx_wait_usec_internal__(1000000);
#endif
        static size_t lasttuples = 0;
        static int round = 0;
        size_t tuples;
        __SYNC;

        round++;
        if(round == 10) {
        tuples = info->tuples - lasttuples;
        lasttuples = info->tuples;
        printf("acks sent %zu, rtt %" PRIu64 "\n", info->acks_sent, info->link_rtt);
        printf("Tuples/s: %zu, Gbits/s: %.2f\n\n",
           tuples/round, (tuples * (sizeof(struct tuple) + sizeof(struct pkt_dccp_headers)) * 8) / (1000000000.0 * round));
        round = 0;
        }
        ''')

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

#ifndef CAVIUM
        if(rdtsc() >= dccp->retrans_timeout) {
#else
        if(core_time_now_us() >= dccp->retrans_timeout) {
#endif
            dccp->connections[worker].pipe = 0;
            __sync_fetch_and_add64(&dccp->link_rtt, dccp->link_rtt);
        }

        static __thread size_t count = 0;
        if(count == 200000) {
          printf("worker = %d, pipe = %d, cwnd = %d\n", worker,dccp->connections[worker].pipe,dccp->connections[worker].cwnd);
          count = 0;
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
        spinlock_lock(&dccp->global_lock);
#ifndef CAVIUM
        dccp->retrans_timeout = rdtsc() + dccp->link_rtt * PROC_FREQ_MHZ;
#else
        dccp->retrans_timeout = core_time_now_us() + dccp->link_rtt;
#endif
        dccp->link_rtt = LINK_RTT;
        uint32_t seq = __sync_fetch_and_add32(&dccp->connections[worker].seq, 1);
        header->dccp.seq_high = seq >> 16;
        header->dccp.seq_low = htons(seq & 0xffff);
#ifdef DEBUG_DCCP
        printf("Send to worker %d: seq = %x, seq_high = %x, seq_low = %x\n", worker, seq, header->dccp.seq_high, header->dccp.seq_low);
#endif
        spinlock_unlock(&dccp->global_lock);

        __sync_fetch_and_add32(&dccp->connections[worker].pipe, 1);
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
        ack->eth.src = p->eth.dest;
        ack->ip.dest = p->ip.src;
        ack->ip.src = p->ip.dest;

        ack->dccp.hdr.src = p->dccp.dst;
        ack->dccp.hdr.res_type_x = DCCP_TYPE_ACK << 1;
        uint32_t seq = (p->dccp.seq_high << 16) | ntohs(p->dccp.seq_low);
        ack->dccp.ack = htonl(seq);
        ack->dccp.hdr.data_offset = 4;

        __sync_fetch_and_add64(&dccp->acks_sent, 1);

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
          __sync_fetch_and_sub32(&connections[srcworker].pipe, (int)ntohl(ack->dccp.ack) - connections[srcworker].lastack);
	  //int32_t oldpipe = __sync_sub_and_fetch(&connections[srcworker].pipe,
			//			 (int)ntohl(ack->dccp.ack) - connections[srcworker].lastack);
	  if(connections[srcworker].pipe < 0) {
	    connections[srcworker].pipe = 0;
	  }

	  // Reset RTO
#ifndef CAVIUM
    dccp->retrans_timeout = rdtsc() + dccp->link_rtt * PROC_FREQ_MHZ;
#else
    dccp->retrans_timeout = core_time_now_us() + dccp->link_rtt;
#endif
	  dccp->link_rtt = LINK_RTT;
	}

	if((int32_t)ntohl(ack->dccp.ack) > connections[srcworker].lastack + 1) {
#ifdef DEBUG_DCCP
	  printf("Congestion event for %d! ack %u, lastack + 1 = %u\n",
	 	 srcworker, ntohl(ack->dccp.ack),
	 	 connections[srcworker].lastack + 1);
#endif
	  // Congestion event! Shrink congestion window
	  uint32_t oldcwnd, success = 0;
          size_t count = 0;
	  do {
            oldcwnd = connections[srcworker].cwnd;
	    if(oldcwnd >= 2) {
              success = __sync_bool_compare_and_swap32((uint32_t*) &connections[srcworker].cwnd, oldcwnd, oldcwnd / 2);
	      //newcwnd = __sync_val_compare_and_swap(&connections[srcworker].cwnd, oldcwnd, oldcwnd / 2);
	    } else {
	      break;
	    }
            count++;
            if(count%1000==0) printf("congestion loop (%d): cwnd = %d, count = %ld\n", cvmx_get_core_num(),connections[srcworker].cwnd,count);

	  } while(!success);
#ifdef DEBUG_DCCP
          printf("cwnd = %d\n", connections[srcworker].cwnd);
#endif

	} else {
#ifdef DEBUG_DCCP
	  printf("Increasing congestion window for %d\n", srcworker);
#endif
	  // Increase congestion window
	  __sync_fetch_and_add32(&connections[srcworker].cwnd, 1);
	  //connections[srcworker].cwnd++;
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
        state.worker = this->task2worker[nic_htonl(t->task)];
        state.myworker = this->task2worker[nic_htonl(t->fromtask)];
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
        struct tuple* t = (struct tuple*) state.q_buf.entry;
        memcpy(header, &dccp->header, sizeof(struct pkt_dccp_headers));
        memcpy(&header[1], t, sizeof(struct tuple));

        struct worker *workers = get_workers();
        header->dccp.dst = htons(state.worker);
        header->dccp.src = htons(state.myworker);
        header->eth.dest = workers[state.worker].mac;
        header->eth.src = workers[state.myworker].mac;
        
        //printf("PREPARE PKT: task = %d, worker = %d\n", nic_hotnl(t->task), state.worker);

#ifdef DEBUG_MP
        t = (struct tuple*) &header[1];
    uint32_t task = nic_htonl(t->task);                                                              
    if(task == 10 && strcmp(t->v[0].str, "golda")) {                                           
      printf("pkt: task = %d, str = %s\n", task, t->v[0].str);                                     
      assert(strcmp(t->v[0].str, "golda") == 0);                                                     
    }                                                                                                
    if(task == 11 && strcmp(t->v[0].str, "nathan")) {                                                
      printf("pkt: task = %d, str = %s\n", task, t->v[0].str);                                     
      assert(strcmp(t->v[0].str, "nathan") == 0);                                                    
    }                                                                                                
    if(task == 12 && strcmp(t->v[0].str, "jackson")) {                                               
      printf("pkt: task = %d, str = %s\n", task, t->v[0].str);                                     
      assert(strcmp(t->v[0].str, "jackson") == 0);                                                   
    }                                                                                                
    if(task == 13 && strcmp(t->v[0].str, "bertels")) {                                               
      printf("pkt: task = %d, str = %s\n", task, t->v[0].str);                                     
      assert(strcmp(t->v[0].str, "berterls") == 0);                                                  
    }   
#endif

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
        __sync_fetch_and_add64(&dccp->tuples, 1);
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
class BatchScheduler(Element):
    this = Persistent(TaskMaster)

    def states(self): self.this = task_master

    def configure(self):
        self.inp = Input(Size)
        self.out = Output(Size)

    def impl(self):
        self.run_c(r'''
    (size_t core_id) = inp();
        //printf("schedele begin: core_id = %s\n", core_id);
    int n_cores = %d;
    static __thread int core = -1;
    static __thread int batch_size = 0;
    static __thread size_t start = 0;
        
    if(core == -1) {
        //core = (core_id * n_cores)/%d;
        core = core_id/2;
        while(this->executors[core].execute == NULL){
            core = (core + 1) %s n_cores;
        }  
#ifndef CAVIUM
            start = rdtsc();
#else
            start = core_time_now_us();
#endif
    }

#ifndef CAVIUM
    if(core >= 2 && (batch_size >= BATCH_SIZE || rdtsc() - start >= BATCH_DELAY * PROC_FREQ_MHZ)) {
#else
    if(core >= 2 && (batch_size >= BATCH_SIZE || core_time_now_us() - start >= BATCH_DELAY)) {
#endif
        do {
            core = (core + 1) %s n_cores;
        } while(this->executors[core].execute == NULL);
        if(core < 2) core = 2;
        batch_size = 0;
        //printf("======================= Dequeue core = %s, thread = %s\n", core, core_id);
#ifndef CAVIUM
        start = rdtsc();
#else
        start = core_time_now_us();
#endif
    }

#ifdef DEBUG_MP
    assert(core < n_cores);
#endif
    batch_size++;
    //printf("schedule: core = %s\n", core);
    output { out(core); }
        ''' % ('%d', n_cores, n_nic_tx, '%', '%', '%d', '%d', '%d'))

# class BatchInc(Element):
#     this = Persistent(BatchInfo)
#
#     def states(self): self.this = batch_info
#
#     def configure(self):
#         self.inp = Input("struct tuple*")
#
#     def impl(self):
#         self.run_c(r'''
#         (struct tuple* t) = inp();
#         if(t) this->batch_size++;
#         ''')

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
        self.inp = Input(queue.q_buffer)
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
        self.out = Output(queue.q_buffer)

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

MAX_ELEMS = 256 #(4 * 1024)

rx_enq_creator, rx_deq_creator, rx_release_creator = \
    queue.queue_custom("rx_queue", "struct tuple", MAX_ELEMS, n_cores, "status", enq_blocking=False,
                       deq_blocking=False, enq_atomic=True, enq_output=True)

tx_enq_creator, tx_deq_creator, tx_release_creator = \
    queue.queue_custom("tx_queue", "struct tuple", MAX_ELEMS, n_cores, "status", checksum="checksum",
                       enq_blocking=True, deq_atomic=True)

BypassEnq, BypassDeq, BypassRelease = \
    queue.queue_custom("bypass_queue", "struct tuple", MAX_ELEMS, n_cores, "status", enq_blocking=True,
                       deq_blocking=False, enq_atomic=True)  # TODO: enq_blocking?


class RxState(State):
    rx_pkt = Field("struct pkt_dccp_headers*")
    rx_net_buf = Field("void *")
    tx_net_buf = Field("void *")


class NicRxFlow(Flow):
    state = PerPacket(RxState)

    def impl(self):
        from_net = net_real.FromNet()
        from_net_free = net_real.FromNetFree()
        class nic_rx(Pipeline):

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
                network_alloc.oom >> Drop()
                # process
                pkt2tuple = Pkt2Tuple()
                classifier.pkt >> pkt2tuple >> GetCore() >> rx_enq >> rx_buf

                # CASE 2: ack
                classifier.ack >> DccpRecvAck() >> rx_buf

                # Exception
                classifier.drop >> rx_buf
                rx_buf >> from_net_free
                
        if nic == 'dpdk':
            nic_rx('nic_rx', process='dpdk', cores=[n_nic_tx + x for x in range(n_nic_rx)])
        else:
            nic_rx('nic_rx', device=target.CAVIUM, cores=[n_nic_tx + x for x in range(n_nic_rx)])


class inqueue_get(CallablePipeline):
    def configure(self):
        self.inp = Input(Size)
        self.out = Output(queue.q_buffer)
        self.default_return = "{NULL, 0}"

    def impl(self): self.inp >> rx_deq_creator() >> self.out


class bypass_get(CallablePipeline):
    def configure(self):
        self.inp = Input(Size)
        self.out = Output(queue.q_buffer)
        self.default_return = "{NULL, 0}"

    def impl(self): self.inp >> BypassDeq() >> self.out

class inqueue_advance(CallablePipeline):
    def configure(self):
        self.inp = Input(queue.q_buffer)

    def impl(self): self.inp >> rx_release_creator()

class bypass_advance(CallablePipeline):
    def configure(self):
        self.inp = Input(queue.q_buffer)

    def impl(self): self.inp >> BypassRelease()

class outqueue_put(CallablePipeline):
    def configure(self):
        self.inp = Input("struct tuple*", Size)

    def impl(self):
        local_or_remote = LocalOrRemote()
        self.inp >> local_or_remote
        # local
        local_or_remote.out_local >> GetCoreCPU() >> BypassEnq()
        # remote
        local_or_remote.out_send >> tx_enq_creator()


class TxState(State):
    worker = Field(Int)
    myworker = Field(Int)
    tx_net_buf = Field("void *")
    q_buf = Field(queue.q_buffer)

class NicTxFlow(Flow):
    state = PerPacket(TxState)

    def impl(self):
        tx_release = tx_release_creator()
        network_alloc = net_real.NetAlloc()
        to_net = net_real.ToNet(configure=["alloc", True])

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
                save_buff = SaveBuff()
                get_buff = GetBuff()

                self.core_id >> queue_schedule >> tx_deq >> save_buff >> PrintTuple() >> SaveWorkerID() \
                >> PreparePkt() >> get_buff >> tx_release

        if nic == 'dpdk':
            nic_tx('nic_tx', process='dpdk', cores=range(n_nic_tx))
        else:
            nic_tx('nic_tx', device=target.CAVIUM, cores=range(n_nic_tx))

if nic == 'dpdk':
    class dccp_print_stat(CallablePipeline):
        def impl(self):
            DccpPrintStat()
    dccp_print_stat('dccp_print_stat', process='dpdk') 
else:
    class dccp_print_stat(Pipeline):
        def impl(self):
            DccpPrintStat()
    dccp_print_stat('dccp_print_stat', device=target.CAVIUM, cores=[8])

inqueue_get('inqueue_get', process='app')
inqueue_advance('inqueue_advance', process='app')
bypass_get('bypass_get', process='app')
bypass_advance('bypass_advance', process='app')
outqueue_put('outqueue_put', process='app')
master_process('app')


c = Compiler(NicRxFlow, NicTxFlow)
c.include = r'''
#include "worker.h"
#include "storm.h"
#include "dccp.h"
'''
c.init = r'''
int workerid = atoi(argv[1]);
struct worker* workers = get_workers();
init_task2executor(workers[workerid].executors);
'''
c.generate_code_as_header()

if nic == 'dpdk':
    c.depend = {"test_storm_nic": ['hash', 'worker', 'dummy', 'dpdk'],
                "test_storm_bypass_app": ['list', 'hash', 'hash_table', 'spout', 'count', 'rank', 'worker', 'app']}
    c.compile_and_run([("test_storm_bypass_app", workerid[test]), ("test_storm_nic", workerid[test])])
else:
    c.depend = {"test_storm_bypass_app": ['list', 'hash', 'hash_table', 'spout', 'count', 'rank', 'worker', 'app']}
    c.compile_and_run([("test_storm_bypass_app", workerid[test])])
