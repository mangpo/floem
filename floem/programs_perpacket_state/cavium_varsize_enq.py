from dsl import *
import queue_smart, net
from compiler import Compiler

class MyState(State):
    qid = Field(Int)
    keylen = Field(Int)
    key = Field(Pointer(Uint(8)), size='state.keylen')
    p = Field(Pointer(Int), shared='data_region')

class Count(State):
    count = Field(Int)
    def init(self):
        self.count = 0

class main(Flow):
    state = PerPacket(MyState)

    class Save(Element):
        this = Persistent(Count)

        def configure(self):
            self.inp = Input(SizeT, 'void*', 'void*')
            self.out = Output()
            self.this = Count()

        def impl(self):
            self.run_c(r'''
    inp();
    this->count++;
    printf("inject = %d\n", this->count);
    state.qid = 0;
    state.key = (uint8_t *) malloc(this->count);
    state.keylen = this->count;
    int i;
    for(i=0; i<this->count ; i++)
        state.key[i] = this->count;

    int* p = data_region;
    p[this->count] = 100 + this->count;
    state.p = &p[this->count];
    output { out(); }
            ''')

        def impl_cavium(self):
            self.run_c(r'''
    inp();
    this->count++;
    printf("inject = %d\n", this->count);
    state.qid = 0;
    state.key = (uint8_t *) malloc(this->count);
    state.keylen = this->count;
    int i;
    for(i=0; i<this->count ; i++)
        state.key[i] = this->count;

    int* p = data_region;
    void* addr = &p[Count0->count];
    int* x;
    dma_buf_alloc((void**) &x);
    *x = nic_ntohl(100 + Count0->count);
    dma_write((uintptr_t) addr, sizeof(int), x);
    dma_free(x);
    _state->p = addr;

    output { out(); }
            ''')

    class Display(Element):
        def configure(self):
            self.inp = Input()

        def impl(self):
            self.run_c(r'''
            printf("%d %d %d %d\n", state.keylen, state.key[0], state.key[state.keylen-1], *state.p);
            fflush(stdout);
            ''')

    class Drop(Element):
        def configure(self):
            self.inp = Input()

        def impl(self):
            self.run_c(r'''while (0); ''')

    class DisplayPacket(Element):
        def configure(self):
            self.inp = Input(SizeT, "void *", "void *")
            self.out = Output("void *", "void *")

        def impl(self):
            self.run_c(r'''
            (size_t len, void *pkt, void *buf) = inp();
            if (pkt != NULL)
                printf("Got packet\n");
            output { out(pkt, buf); }
            ''')

    Enq, Deq, Scan = queue_smart.smart_queue("queue", 256, 2, 1, enq_blocking=False)

    class push(Segment):
        def impl(self):
            from_net = net.FromNet()
            from_net_free = net.FromNetFree()

            from_net.out >> main.Save() >> main.Enq()
            from_net.out >> main.DisplayPacket() >> from_net_free

            from_net.nothing >> main.Drop()

    class pop(Segment):

        def impl(self):
            self.core_id >> main.Deq() >> main.Display()

    def impl(self):
        MemoryRegion("data_region", 4 * 100)
        main.push('push', device=target.CAVIUM)
        main.pop('pop', process="varsize_enq")

master_process("varsize_enq")

c = Compiler(main)
c.generate_code_as_header()
c.depend = ["varsize_enq"]
c.compile_and_run("cavium_varsize_enq_test")
