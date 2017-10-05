from dsl2 import *

class FromNet(Element):
    def configure(self, batch_size=32):
        self.out = Output(Size, "void *", "void *") # packet, buffer
        self.nothing = Output()
        self.special = 'from_net'
        self.batch_size = batch_size

    def impl(self):
        self.run_c(r'''
    static uint32_t count = 0;
    void *data, *buf;
    size_t size;
    dpdk_from_net(&size, &data, &buf, %d);

    output switch {
        case data != NULL: out(size, data, buf);
        case data == NULL: nothing();
    }
        ''' % self.batch_size)

    def impl_cavium(self):
        self.run_c(r'''
    void* p = cvmx_phys_to_ptr(wqe->packet_ptr.s.addr);
    size_t size = 0;
    if(p) size = cvmx_wqe_get_len(wqe);
    output switch {
        case p != NULL: out(size, p, wqe);
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
        self.out = Output(Size, "void *", "void *")  # packet, buffer
        self.oom = Output()

    def impl(self):
        self.run_c(r'''
    (size_t len) = inp();
    void *data, *buf;
    dpdk_net_alloc(len, &data, &buf);
    output switch {
        case data != NULL: out(len, data, buf);
        else: oom();
    }
        ''')

    def impl_cavium(self):
        self.run_c(r'''
    (size_t len) = inp();
    void *p = (void *)cvmx_fpa_alloc(CVM_FPA_DMA_CHUNK_POOL);

    output switch {
        case p != NULL: out(len, p, NULL);
        else: oom();
    }
        ''')


class ToNet(Element):
    def configure(self, buffer="from_net", has_output=False, batch_size=32):
        self.inp = Input(Size, "void *", "void *")  # size, packet, buffer
        self.buffer = buffer
        self.has_output = False
        self.batch_size = batch_size
        # self.has_output = has_output
        # if has_output:
        #     self.out = Output("void *", "void *")

    def impl(self):
        out = r'''
    output { out(p, buf); }
    ''' if self.has_output else ""
        self.run_c(r'''
    (size_t len, void* p, void* buf) = inp();
    dpdk_to_net(len, p, buf, %d);
        ''' % self.batch_size + out)

    def impl_cavium(self):
        out = r'''
    output { out(p, buf); }
    ''' if self.has_output else ""
        free = "" if self.buffer == "from_net" else "cvmx_fpa_free(p, CVM_FPA_DMA_CHUNK_POOL, 0);\n"

        self.run_c(r'''
    (size_t len, void* p, void* buf) = inp();
    network_send(len, p, 2560);
    ''' + free + out)


# class NetAllocFree(Element):
#     def configure(self):
#         self.inp = Input("void *", "void *")  # packet, buffer
#
#     def impl(self):
#         self.run_c(r'''
#     (void* p, void* buf) = inp();
#     dpdk_net_free(p, buf);
#         ''')
#
#     def impl_cavium(self):
#         # Do nothing
#         self.run_c(r'''
#     (void* p, void* buf) = inp();
#     free(p);
#         ''')


class HTON(Element):
    def configure(self, state_name):
        self.inp = Input(Size, "void *", "void *")
        self.out = Output(Size, "void *", "void *")
        self.special = ('hton', state_name)

    def impl(self):
        self.run_c(r'''
        (size_t size, void* pkt, void* buf) = inp();
        output { out(size, pkt, buf); }
        ''')
