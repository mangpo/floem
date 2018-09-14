from floem import *

class Filter(Element):

    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.out = Output(SizeT, "void*", "void*")
        self.other = Output("void*", "void*")

    def impl(self):
        self.run_c(r'''
(size_t size, void* pkt, void* buff) = inp();
bool disgard = pkt_filter(pkt);

output switch {
    case disgard: other(pkt, buff);
    else: out(size, pkt, buff);
}
        ''')

class Classify(Element):

    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.hash = Output(SizeT, "void*", "void*")
        self.flow = Output(SizeT, "void*", "void*")
        self.seq = Output(SizeT, "void*", "void*")
        self.other = Output("void*", "void*")

    def impl(self):
        self.run_c(r'''
(size_t size, void* pkt, void* buff) = inp();
PKT_TYPE mytype;

mytype = pkt_parser(pkt);
//printf("type = %d\n", mytype);

output switch {
  case mytype==HASH: hash(size, pkt, buff);
  case mytype==FLOW: flow(size, pkt, buff);
  case mytype==SEQU: seq(size, pkt, buff);
  else: other(pkt, buff);
}
        ''')

class Hash(Element):

    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.out = Output(SizeT, "void*", "void*")

    def impl(self):
        self.run_c(r'''
(size_t pkt_len, void* pkt_ptr, void* buff) = inp();
//compute_3des(pkt_ptr, pkt_len);
compute_aes(pkt_ptr, pkt_len);
//printf("AES\n");

output { out(pkt_len, pkt_ptr, buff); }
        ''')


class Flow(Element):
    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.out = Output(SizeT, "void*", "void*")

    def impl(self):
        self.run_c(r'''
(size_t pkt_len, void* pkt_ptr, void* buff) = inp();

int i;
uint64_t flow_id, processed_bytes = UINT64_MAX;
            flow_id = get_flow_id(pkt_ptr);
            flow_id += rand() % 1024;

            for (i = 0; i < CM_ROW_NUM; i++) {
                processed_bytes = MIN(processed_bytes, cm_sketch_read(i, flow_id));
            }
            processed_bytes += pkt_len;
            for (i = 0; i < CM_ROW_NUM; i++) {
                cm_sketch_update(i, flow_id, processed_bytes);
            }

output { out(pkt_len, pkt_ptr, buff); }
        ''')


class SeqState(State):
    n = 32
    seq_num = Field(Uint(64))
    lock_group = Field(Array('spinlock_t', n))

    def init(self):
        self.seq_num = 0
        self.lock_group = lambda x: "lock_group_init({0}, {1})".format(x, self.n)
        self.packed = False

class Seq(Element):
    this = Persistent(SeqState)

    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.out = Output(SizeT, "void*", "void*")
        self.this = SeqState()

    def impl(self):
        self.run_c(r'''
(size_t pkt_len, void* pkt_ptr, void* buff) = inp();

    int i;
    uint32_t lock_bitmap;
            lock_bitmap = *(uint32_t *)(pkt_ptr + UDP_PAYLOAD + 5);
            uint64_t myseq;

            for (i = 0; i < 32; i++) {
                if (lock_bitmap & (1 << i)) {
                    spinlock_lock(&this->lock_group[i]);
                }
            }

            // no sync?
            while (!__sync_bool_compare_and_swap64(&this->seq_num,
                                                           myseq,
                                                           myseq + 1)) {
                myseq = this->seq_num;
            }
        //printf("seq: %ld  size: %ld\n", myseq, pkt_len);
            myseq = htonp(myseq);
            memcpy(pkt_ptr + UDP_PAYLOAD + 5, &myseq, sizeof(int64_t));

            for (i = 0; i < 32; i++) {
                if (lock_bitmap & (1 << i)) {
                    spinlock_unlock(&this->lock_group[i]);
                }
            }

output { out(pkt_len, pkt_ptr, buff); }
        ''')

class Reply(Element):
    def configure(self):
        self.inp = Input(SizeT, "void*", "void*")
        self.out = Output(SizeT, "void*", "void*")

    def impl(self):
        self.run_c(r'''
(size_t pkt_len, void* pkt_ptr, void* buff) = inp();
recapsulate_pkt(pkt_ptr, pkt_len);

output { out(pkt_len, pkt_ptr, buff); }
        ''')

class nic_rx(Segment):
    def impl(self):
        from_net = net.FromNet()
        to_net = net.ToNet()
        net_free = net.FromNetFree()
        filter = Filter()
        classify = Classify()
        reply = Reply()

        from_net.nothing >> library.Drop()

        from_net >> filter
        filter.other >> net_free
        filter.out >> classify

        classify.hash >> Hash() >> reply
        classify.flow >> Flow() >> reply
        classify.seq >> Seq() >> reply
        classify.other >> net_free

        reply >> to_net


nic_rx('nic_rx', process='dpdk', cores=range(1))
#nic_rx('nic_rx', device=target.CAVIUM, cores=range(1))
c = Compiler()
c.include = r'''
#include "pkt-utils.h"
#include "nic-compute.h"
#include "count-min-sketch.h"
'''
c.init = r'''
cm_sketch_init();
'''
c.testing = 'while (1) pause();'
c.depend = ['pkt-utils', 'count-min-sketch', 'nic-compute', 'tdes', 'aes', 'aes_ni']
#c.generate_code_as_header()
c.generate_code_and_run()
