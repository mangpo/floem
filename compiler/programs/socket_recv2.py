from dsl import *
import net

Item = create_state("item", "int x; int y;")
from_net = net.create_from_net_fixed_size("item", "item", 2, 8192, 7001)

display = create_element_instance("display", [Port("in", ["item*"])], [],
                                  r'''
    (item* t) = in();
    printf("item %d %d\n", t->x, t->y);
                                  ''')

to_net = net.create_to_net_fixed_size("item", "item", "127.0.0.1", 7001)


@internal_trigger("print_item")
def print_item():
    display(from_net())  # TODO: from_net_save is not assigned to this thread.

@API("send_item")
def send_item(t):
    to_net(t)


c = Compiler()
c.include = r'''
#include "../net.h"
'''

c.testing = r'''
  item data[4];
  for(int i=0; i<4; i++) {
    data[i].x = i;
    data[i].y = 100 + i;
    send_item(&data[i]);
  }
'''
c.generate_code_and_run()