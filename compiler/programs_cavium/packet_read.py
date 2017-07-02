import net_cavium, target
from dsl2 import *
from compiler import Compiler

class Display(Element):
    def configure(self):
        self.inp = Input('void *', 'void *')

    def impl(self):
        self.run_c(r'''
{
    int i;
    (void* p, void* dummy) = inp();
    uint8_t* pkt = (uint8_t*) p;

    for (i = 0; i < 16; i++) {
        printf("%x ", pkt[i]);
    }
    printf("\n");
}
        ''')

class test(InternalLoop):
    def impl(self):
        net_cavium.FromNet() >> Display()

test('test', device=target.CAVIUM, cores=[0,1,2,3])

c = Compiler()
c.generate_code_as_header()