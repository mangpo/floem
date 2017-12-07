from dsl import *
import net_real
from compiler import Compiler

class DisplayPacket(Element):
    def configure(self):
        self.inp = Input(Size, "void *", "void *")
        self.out = Output("void *", "void *")

    def impl(self):
        self.run_c(r'''
        (size_t len, void *pkt, void *buf) = inp();
        if (pkt != NULL) {
            printf("Got packet\n");
            uint8_t* x = (uint8_t*) pkt;
            for(int i=0; i<len; i++) {
              if(i%16==0) printf("\n");
              printf("%x ", x[i]);
            }
            printf("\n\n");
        }
        output { out(pkt, buf); }
        ''')

class Drop(Element):
    def configure(self):
        self.inp = Input()

    def impl(self):
        self.run_c(r'''while (0); ''')

class test(InternalLoop):
    def impl(self):
        from_net = net_real.FromNet('from_net')
        from_net.out >> DisplayPacket('print_packet') >> \
                net_real.FromNetFree('from_net_free')
        from_net.nothing >> Drop('drop')

test('test', process='dpdk')

c = Compiler()
c.testing = 'while (1) pause();'
c.generate_code_and_compile()
