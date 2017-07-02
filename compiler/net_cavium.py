from dsl2 import *

# Signature
# FromNet: Output(void *, struct rte_mbuf *)
# NetworkFree: Input(struct rte_mbuf *)

# NetworkAlloc: Input(Size), Output(void *, struct rte_mbuf *)
# ToNet: Input(Size, header_type *, struct rte_mbuf *)


class FromNet(Element):
    def configure(self):
        self.out = Output("void *", "void *") # packet, buffer
        self.special = 'from_net'

    def impl(self):
        # TODO: dpdk
        self.run_c(r'''
    output { out(NULL, NULL); }
        ''')

    def impl_cavium(self):
        self.run_c(r'''
    void* p = cvmx_phys_to_ptr(wqe->packet_ptr.s.addr);
    output { out(p, wqe); }
        ''')