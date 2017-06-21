from dsl2 import *
import net2
from compiler import Compiler

class Item(State):
    x = Field(Int)
    y = Field(Int)

class Display(Element):
    def configure(self):
        self.inp = Input(Pointer(Item))

    def impl(self):
        self.run_c(r'''
        (Item* t) = inp();
        printf("item %d %d\n", t->x, t->y);
        ''')

class PrintItem(InternalLoop):
    def impl(self):
        from_net = net2.from_net_fixed_size_instance('item', Item, 1, 64, 7001)
        display = Display()
        from_net >> display

class SendItem(API):
    def configure(self):
        self.inp = Input(Pointer(Item))

    def impl(self):
        to_net = net2.to_net_fixed_size_instance('item', Item, "127.0.0.1", 7001)
        self.inp >> to_net

PrintItem('print_item')
SendItem('send_item')

c = Compiler()
c.include = r'''
#include "../net.h"
'''

c.testing = r'''
  Item data[4];
  for(int i=0; i<4; i++) {
    data[i].x = i;
    data[i].y = 100 + i;
    send_item(&data[i]);
  }
'''
c.generate_code_and_run()