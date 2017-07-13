from dsl2 import *

class FromNet(Element):
    def configure(self):
        self.out = Output(Size, "void *", "void *") # packet, buffer
        self.nothing = Output()
        self.special = 'from_net'

    def impl(self):
        self.run_c(r'''
    void *data, *buf;
    size_t size;
    dpdk_from_net(&size, &data, &buf);
    output switch {
        case data != NULL: out(size, data, buf);
        case data == NULL: nothing();
    }
        ''')

    def impl_cavium(self):
        self.run_c(r'''
    void* p = cvmx_phys_to_ptr(wqe->packet_ptr.s.addr);
    output switch {
        case p != NULL: out(0, p, wqe);
        case p == NULL: nothing();
    }
        ''')

class FromNetFree(Element):
    def configure(self):
        self.inp = Input("void *", "void *")  # packet, buffer

    def impl(self):
        self.run_c(r'''
    (void* p, void* buf) = inp();
    dpdk_net_free(p, buf);
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
        self.oom = Output()

    def impl(self):
        self.run_c(r'''
    (size_t len) = inp();
    void *data, *buf;
    dpdk_net_alloc(len, &data, &buf);
    output switch {
        case data != NULL: out(data, buf);
        case data == NULL: oom();
    }
        ''')

    def impl_cavium(self):
        self.run_c(r'''
    (size_t len) = inp();
    void* p = malloc(sizeof(uint8_t) * len);
    output switch {
        case p != NULL: out(p, NULL);
        case p == NULL: oom();
    }
        ''')


class ToNet(Element):
    def configure(self, has_output=False):
        self.inp = Input(Size, "void *", "void *")  # size, packet, buffer
        self.has_output = has_output
        if has_output:
            self.out = Output("void *", "void *")

    def impl(self):
        out = r'''
    output { out(p, buf); }
    ''' if self.has_output else ""
        self.run_c(r'''
    (size_t len, void* p, void* buf) = inp();
    dpdk_to_net(len, p, buf);

    if (
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
        self.run_c(r'''
    (void* p, void* buf) = inp();
    dpdk_net_free(p, buf);
        ''')

    def impl_cavium(self):
        # Do nothing
        self.run_c(r'''
    (void* p, void* buf) = inp();
    free(p);
        ''')

