from dsl2 import *

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

class FromNetFree(Element):
    def configure(self):
        self.inp = Input("void *", "void *")  # packet, buffer

    def impl(self):
        self.run_c(r'''
    (void* p, void* buf) = inp();
    rte_pktmbuf_free(buf);
        ''')

    def impl_cavium(self):
        # Do nothing
        self.run_c(r'''
    (void* p, void* buf) = inp();
        ''')


class NetAlloc(Element):
    def configure(self):
        self.inp = Input(Size)
        self.out = Output("void *", "void *")  # packet, buffer

    def impl(self):
        # TODO: dpdk
        self.run_c(r'''
    (size_t len) = inp();
    output { out(NULL, NULL); }
        ''')

    def impl_cavium(self):
        self.run_c(r'''
    (size_t len) = inp();
    void* p = malloc(sizeof(uint8_t) * len);
    output { out(p, NULL); }
        ''')


class ToNet(Element):
    def configure(self, has_output=False):
        self.inp = Input(Size, "void *", "void *")  # size, packet, buffer
        self.has_output = has_output
        if has_output:
            self.out = Output("void *", "void *")

    def impl(self):
        # TODO: dpdk
        out = r'''
    output { out(p, buf); }
    ''' if self.has_output else ""
        self.run_c(r'''
    (size_t len, void* p, void* buf) = inp();
        ''' + out)

    def impl_cavium(self):
        out = r'''
    output { out(p, buf); }
    ''' if self.has_output else ""
        self.run_c(r'''
    (size_t len, void* p, void* buf) = inp();
    network_send(len, p, 2560);
        ''' + out)

class NetAllocFree(Element):
    def configure(self):
        self.inp = Input("void *", "void *")  # packet, buffer

    def impl(self):
        # TODO: dpdk
        self.run_c(r'''
    (void* p, void* buf) = inp();
        ''')

    def impl_cavium(self):
        # Do nothing
        self.run_c(r'''
    (void* p, void* buf) = inp();
    free(p);
        ''')

